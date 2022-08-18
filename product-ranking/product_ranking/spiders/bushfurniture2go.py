from __future__ import division, absolute_import, unicode_literals

from urlparse import urljoin
import traceback

from scrapy.log import WARNING

from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.items import Price, SiteProductItem
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.bushfurniture2go_variants import Bushfurniture2goVariants

class BushFurniture2goProductSpider(BaseProductsSpider):
    name = 'bushfurniture2go_products'
    allowed_domains = ['bushfurniture2go.com']

    SEARCH_URL = "http://www.bushfurniture2go.com/search.aspx?keywords={search_term}"

    def __init__(self, *args, **kwargs):
        super(BushFurniture2goProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                page=1),
            *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        if categories:
            product['department'] = categories[-1]

        product['locale'] = "en-US"

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1[@class="h1_itemdetail" or @itemprop="name"]/text()').extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        brand = response.xpath('//span[@id="ctl00_ContentPlaceHolder1_laDetailsBrand"]/a/text()').extract()
        if not brand:
            title = self._parse_title(response)
            return guess_brand_from_first_words(title)
        return brand[0] if brand else None

    def _parse_sku(self, response):
        sku = response.xpath('//span[@itemprop="sku"]/text()').extract()
        return sku[0] if sku else None

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//a[@href="javascript:showEnlargeImage()"]/img/@src').extract()
        if not image_url:
            image_url = response.xpath('//div[@class="gallery"]//div[@class="picture"]'
                                       '//img[@id="myFancyCloudZoom"]/@src').extract()
        return image_url[0] if image_url else None

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//span[@id="ctl00_ContentPlaceHolder_PageNavigation_laBreadcrumbsItem"]'
                                    '/a/text()').extract()
        if not categories:
            categories = response.xpath('//div[@class="product-page-breadcrumb"]//ul'
                                        '//li//span[@itemprop="title"]/text()').extract()
        return categories[1:] if categories else None

    def _parse_price(self, response):
        price = response.xpath('//span[@id="ctl00_ContentPlaceHolder1_laSellPrice"]'
                               '/text()').re(FLOATING_POINT_RGEX)
        if not price:
            price = response.xpath('//div[@itemprop="offers"]/div[@class="product-price"]'
                                   '/span[@itemprop="price"]/text()').re(FLOATING_POINT_RGEX)
        try:
            price = float(price[0])
            return Price(price=price, priceCurrency='USD')
        except:
            self.log('Error Parsing Price:{}'.format(traceback.format_exc()), WARNING)

    def _parse_variants(self, response):
        bv = Bushfurniture2goVariants()
        bv.setupSC(response)
        return bv._variants()

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//div[@class="category-title-block"]//strong/text()').re('\d+')
        return int(total_matches[-1]) if total_matches else None

    def _scrape_next_results_page_link(self, response):
        next_link = response.xpath('//a[text()="Next"]/@href').extract()
        if next_link:
            return urljoin(response.url, next_link[0])

    def _scrape_product_links(self, response):
        links = response.xpath('//div[contains(@class, "product-grid")]'
                               '//h2[@class="product-title"]/a/@href').extract()
        if not links:
            self.log('There is no product links: {}'.format(response.url))
        for link in links:
            yield link, SiteProductItem()
