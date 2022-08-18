import re
import urllib
import traceback
import urlparse

from scrapy.conf import settings

from product_ranking.items import Price, SiteProductItem
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders import (BaseProductsSpider, cond_set_value, FormatterWithDefaults)


class FootlockerProductsSpider(BaseProductsSpider):

    name = 'footlocker_products'

    allowed_domains = [
        'www.footlocker.com'
    ]

    SEARCH_URL = "http://www.footlocker.com/_-_/keyword-{search_term}?Nao={current_page}&cm_PAGE={current_page}"

    def __init__(self, *args, **kwargs):
        self.current_page = 0
        settings.overrides['USE_PROXIES'] = True
        formatter = FormatterWithDefaults(current_page=self.current_page)
        super(FootlockerProductsSpider, self).__init__(
            formatter,
            url=self.SEARCH_URL,
            site_name=self.allowed_domains[0],
            *args, **kwargs
        )
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _parse_single_product(self, response):

        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en_GB"

        title = self._parse_title(response)
        if title:
            brand = guess_brand_from_first_words(title)
            cond_set_value(product, 'title', title)
            cond_set_value(product, 'brand', brand)

        cond_set_value(product, 'is_out_of_stock', False)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        return product

    def _parse_title(self, response):
        title = response.xpath(
                '//h1[@id="product_title"]/text()'
            ).extract()

        return title[0] if title else None

    def _parse_price(self, response):
        price = response.xpath('//div[@id="product_price"]')

        if price:
            price = Price('GBP', price.extract()[0])

        return price

    def _parse_image_url(self, response):
        image_url = response.body.split('var dtm_img_url = "";')
        if len(image_url) >= 2:
            image_url = image_url[1]
            image_url = re.search('dtm_img_url = "(.*?)";', image_url, re.DOTALL)
            if image_url:
                image_url = image_url.group(1)
            else:
                image_url = None
        else:
            image_url = None

        return image_url

    def _parse_description(self, response):
        descriptions = response.xpath('//div[@id="pdp_description"]/node()[normalize-space()]').extract()

        descriptions = ''.join(descriptions)

        return descriptions if descriptions else None

    def _parse_sku(self, response):
        sku = response.body.split('var dtm_sku = "";')
        if len(sku) >= 2:
            sku = sku[1]
            sku = re.search('var dtm_sku = "(.*?)";', sku, re.DOTALL)
            if sku:
                sku = sku.group(1)
            else:
                sku = None
        else:
            sku = None

        return sku

    def _parse_reseller_id(self, response):
        reseller_id = response.body
        reseller_id = re.search('"productid","(.*?)"', reseller_id, re.DOTALL)
        if reseller_id:
            reseller_id = reseller_id.group(1)
        else:
            reseller_id = None

        return reseller_id

    def _scrape_total_matches(self, response):

        try:
            total_matches = response.xpath('//div[@id="searchResultsInfo"]//span/text()').extract()[0]
            total_matches = re.search('(.*?) result for:', total_matches, re.DOTALL).group(1)
            return int(total_matches)

        except Exception as e:
            self.log("Exception looking for total_matches, Exception Error: {}".format(traceback.format_exc()))
            return

    def _scrape_product_links(self, response):

        self.product_links = response.xpath('//div[@id="endeca_search_results"]//ul//li//a[@class="quickviewEnabled"]/@href').extract()
        for link in self.product_links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):

        if not self.product_links:
            return

        next_page = response.xpath('//a[contains(@class, "next")]/@href').extract()
        return  urlparse.urljoin('http://'+self.allowed_domains[0], next_page[0]) if next_page else None
