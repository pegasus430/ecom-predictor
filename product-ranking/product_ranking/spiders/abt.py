import re
import string
import traceback

from scrapy import Request
from scrapy.log import INFO
from scrapy.conf import settings

from product_ranking.items import (Price, SiteProductItem)
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from product_ranking.powerreviews import parse_powerreviews_buyer_reviews


class AbtProductsSpider(BaseProductsSpider):

    name = 'abt_products'
    allowed_domains = ["abt.com", "readservices.powerreviews.com"]

    SEARCH_URL = "http://www.abt.com/resources/pages/search.php?keywords={search_term}"

    REVIEW_URL = "http://readservices-b2c.powerreviews.com/m/{pwr_group_id}" \
                 "/l/en_US/product/{pwr_product_id}/reviews?apikey={api_key}"

    def __init__(self, *args, **kwargs):
        super(AbtProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse out of stock
        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse model
        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        # Parse buyer reviews
        pwr_api_key = self._find_between(response.body, "api_key: '", "',")
        pwr_group_id = self._find_between(response.body, "merchant_id: '", "',")
        product_id = self._find_between(response.body, "page_id: '", "',")
        cond_set_value(product, 'reseller_id', product_id)

        if pwr_api_key and pwr_group_id and product_id:
            return Request(
                self.REVIEW_URL.format(pwr_group_id=pwr_group_id, pwr_product_id=product_id, api_key=pwr_api_key),
                callback=self._parse_buyer_reviews,
                dont_filter=True,
                meta=meta
            )
        else:
            return product

    def _parse_title(self, response):
        title = response.xpath(
            '//h1[@id="product_title"]'
            '/descendant::text()').extract()

        if title:
            title = ''.join(title)
            return title

    def _parse_brand(self, response):
        brand = is_empty(response.xpath('//meta[@itemprop="brand"]/@content').extract())
        return brand

    def _parse_categories(self, response):
        categories = response.xpath(
            "//div[@class='bread_crumbs']"
            "//a[@itemprop='url']//span/text()").extract()

        return categories[1:] if categories else None

    @staticmethod
    def _parse_out_of_stock(response):
        oos = True
        oos_info = response.xpath("//span[@id='availability_desc']/text()").extract()
        if oos_info:
            if 'in stock' in oos_info[0].lower():
                oos = False

        return oos

    def _parse_price(self, response):
        try:
            price = response.xpath("//span[@id='price'] | "
                                   "//div[@class='package_summary_price']").re('\d+(?:[\d,.]*\d)')
            if price:
                price = price[0]
            else:
                price = re.search(r'Regular Price \$(\d*\.\d+|\d+)', response.body).group(1)
            return Price(price=price, priceCurrency='USD')
        except:
            self.log('Price error {}'.format(traceback.format_exc()))

    def _parse_image_url(self, response):
        image_url = is_empty(response.xpath('//a[@id="main_std_anchor"]/@href').extract())
        return image_url

    def _parse_description(self, response):
        desc = response.xpath(
            "//div[@class='pane-content']"
        ).extract()

        if desc:
            description = self._exclude_javascript_from_description(desc[0])
            return self._clean_text(description)

    def _parse_buyer_reviews(self, response):
        meta = response.meta
        product = meta.get('product')
        cond_set_value(product, 'buyer_reviews', parse_powerreviews_buyer_reviews(response))

        return product

    def _parse_model(self, response):
        model = is_empty(response.xpath("//div[@class='abt_model']/text()").extract())
        if model:
            model = model.replace('Abt Model:', '').strip()
            return model

    def _parse_upc(self, response):
        upc = is_empty(
            response.xpath("//div[@class='abt_model']"
                           "//span[@id='product-bottom-info-and-pricegrabber-upc']"
                           "/text()").extract()
        )
        if upc:
            upc = upc.strip()
            return upc

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        total_matches = is_empty(
            response.xpath('//div[@class="hawk-searchView"]//a[contains(@class, "hawk-viewOptionInner")]/text()').re(r'\d+'), 0
        )
        if not total_matches:
            total_matches = is_empty(
                response.xpath('//div[@class="paging_summary"]/text()').re(r'of (\d+) product'), 0
            )

        if total_matches:
            return int(total_matches)
        else:
            return 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//ul[@class='category_list']"
            "//li//div[@class='cl_title']"
            "//a[@class='productPageLink']/@href"
        ).extract()

        if not links:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        links = response.xpath(
            "//*[@class='hawk-paging']"
            "/span[@class='hawk-pageActive']"
            "/following-sibling::a[@class='hawk-pageLink'][1]/@href"
        ).extract()

        if not links:
            links = response.xpath(
                "//div[@id='category_paging1']"
                "/span[@class='paging_current']"
                "/following-sibling::a[1]/@href"
            ).extract()

        if links:
            link = links[0]
        else:
            link = None

        return link

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _find_between(self, s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _exclude_javascript_from_description(self, description):
        description = re.subn(r'<(script).*?</\1>(?s)', '', description)[0]
        description = re.subn(r'<(style).*?</\1>(?s)', '', description)[0]
        description = re.subn("(<!--.*?-->)", "", description)[0]

        return description
