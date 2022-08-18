import re
from urlparse import urljoin

from scrapy import Request, FormRequest
from scrapy.log import ERROR

from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FormatterWithDefaults, FLOATING_POINT_RGEX

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi


class BootsProductsSpider(BaseProductsSpider):
    name = 'boots_products'
    allowed_domains = ["boots.com", "boots.scene7.com"]

    BASE_IMAGE_URL = "https://boots.scene7.com/is/image/"

    SEARCH_URL = "http://www.boots.com/search/{search_term}"

    NEXT_URL = 'http://www.boots.com/ProductListingView?searchType=1002&filterTerm=&langId=-1&' \
               'advancedSearch=&cm_route2Page=Home%3ESearch%3A+{search_term}&sType=SimpleSearch&' \
               'cm_pagename=Search%3A+{search_term}&gridPosition=&metaData=&manufacturer=&' \
               'ajaxStoreImageDir=%2Fwcsstore%2FeBootsStorefrontAssetStore%2F&resultCatEntryType=2&' \
               'searchTerm={search_term}&resultsPerPage=24&emsName=&facet=&' \
               'disableProductCompare=false&filterFacet=&productBeginIndex={begin_index}&beginIndex={begin_index}'

    BUYER_REVIEWS_URL = 'http://api.bazaarvoice.com/data/reviews.json?apiversion=5.5&passkey=324y3dv5t1xqv8kal1wzrvxig&' \
                        'Filter=ProductId:{}&Include=Products&Stats=Reviews'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(BootsProductsSpider, self).__init__(site_name=self.allowed_domains[0],
            url_formatter=FormatterWithDefaults(
                headers={'X-Requested-With': 'XMLHttpRequest'}
            ),
            *args,
            **kwargs)

    def parse_buyer_reviews(self, response):
        buyer_reviews_per_page = self.br.parse_buyer_reviews_single_product_json(response)

        product = response.meta['product']
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews_per_page)
        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        oos = self._is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', oos)

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        cond_set_value(product, 'department', category)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        new_meta = {}
        new_meta['product'] = product
        new_meta['product_id'] = sku
        if sku:
            return Request(self.BUYER_REVIEWS_URL.format(sku),
                           dont_filter=True,
                           callback=self.parse_buyer_reviews,
                           meta=new_meta)
        return product

    @staticmethod
    def _is_out_of_stock(response):
        oos = response.xpath('//div[@id="sold_out_text" and @style="display:none;"]')
        return not bool(oos)

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//div[@id="estore_product_title"]//text()').extract()
        return "".join(title).strip()

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//input[@id="productManufacturerName"]/@value').extract()
        if brand:
            return brand[0].capitalize()

    def _parse_reseller_id(self, response):
        reseller_id = response.xpath('//div[@id="productId"]/text()').extract()
        if reseller_id:
            return reseller_id[0]

    def _parse_sku(self, response):
        sku = response.xpath('//input[@id="product_ID"]/@value').extract()
        if sku:
            return sku[0]

    def _parse_image_url(self, response):
        raw_image_url = response.xpath('//input[@id="s7viewerAsset"]//@value').extract()
        if raw_image_url:
            main_image = urljoin(self.BASE_IMAGE_URL, raw_image_url[0])
            return main_image

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//div[@id="widget_breadcrumb"]/ul/li/a/text()').extract()
        categories = [category.strip() for category in categories if category.strip()]
        if categories:
            return categories

    def _category_name(self, response):
        categories = self._parse_categories(response)
        if categories:
            return categories[-1]

    @staticmethod
    def _parse_description(response):
        description = [item.strip() for item in response.xpath('//div[@id="estore_product_longdesc"]//text()').extract()
                       if item.strip()]
        return "\n".join(description)

    def _parse_price(self, response):
        price = response.xpath('//input[@type="hidden" and contains(@id, "Price")]/@value').re(FLOATING_POINT_RGEX)
        if price:
            return Price(price=float(price[0].replace(',', '')),
                         priceCurrency='GBP')

    def _scrape_total_matches(self, response):
        total = response.xpath('//span[contains(@id, "suggestedSearchTotalCount")]/text() | '
                               '//span[@class="showing_products_total"]/text()').extract()
        return int(total[0]) if total else 0

    def _scrape_product_links(self, response):
        product_links = response.xpath('//div[@class="product_name"]/a/@href | '
                                       '//div[contains(@class, "acol6")]/a/@href').extract()
        for product_url in product_links:
            yield product_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        search_term = response.meta['search_term']
        current_page = response.meta.get('current_page')
        if not current_page:
            current_page = 1
        total = self._scrape_total_matches(response)
        count = total / 24 + 1
        begin_index = current_page * 24
        if current_page < count:
            current_page += 1
            response.meta['current_page'] = current_page
            url = self.NEXT_URL.format(search_term=search_term, begin_index=begin_index)

            return Request(url=url, headers={'X-Requested-With': 'XMLHttpRequest'},
                           meta=response.meta
                           )
