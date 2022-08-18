import re
import string
import urllib
from urlparse import urljoin

from scrapy.http import Request
from scrapy.log import WARNING

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import SiteProductItem, Price, RelatedProduct, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty

CURRENCY = 'CAD'


class LowesCaProductsSpider(BaseProductsSpider):
    name = 'lowesca_products'
    allowed_domains = ['lowes.ca']

    SEARCH_URL = 'https://www.lowes.ca/search/{search_term}.html?iterm={search_term}'
    REVIEWS_URL = 'http://api.bazaarvoice.com/data/reviews.json?apiversion=5.4' \
                  '&passkey=pcmuj0pvxpdntavhu70avt4pk&Filter=ProductId:{product_id}&Include=Products&Stats=Reviews'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(LowesCaProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        if not self.searchterms:
            for request in super(LowesCaProductsSpider, self).start_requests():
                yield request

        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8').replace(' ', '-')),
                ),
                meta={'search_term': st, 'remaining': self.quantity},
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse department
        department = self._parse_department(response) # Here we pass categories, not response
        cond_set_value(product, 'department', department, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse model
        model = self._parse_model(response)
        cond_set_value(product, 'model', model, conv=string.strip)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc, conv=string.strip)

        is_in_store_only = self._parse_in_store_only(response)
        cond_set_value(product, 'is_in_store_only', is_in_store_only)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku, conv=string.strip)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        # Parse stock status
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Parse "no longer available"
        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        # Parse related products
        related_products = self._parse_related_products(response)
        cond_set_value(product, 'related_products', related_products)

        if reseller_id:
            return Request(
                url=self.REVIEWS_URL.format(product_id=str(reseller_id).strip()),
                callback=self.parse_buyer_reviews,
                meta={
                    'product': product,
                    'product_id': reseller_id,
                },
                dont_filter=True
            )

        return product

    def parse_buyer_reviews(self, response):
        product = response.meta.get('product')

        reviews = self.br.parse_buyer_reviews_single_product_json(response)
        product['buyer_reviews'] = BuyerReviews(**reviews)

        return product

    def _scrape_total_matches(self, response):
        total_matches = is_empty(response.xpath('//div[@id="divMsgPage"]/text()').extract())
        total_matches = re.search('of(.*)', total_matches, re.DOTALL).group(1)
        if ',' in total_matches:
            total_matches = total_matches.replace(',', '')
        total_matches = re.search('(\d+)', total_matches, re.DOTALL)
        return int(total_matches.group(1)) if total_matches else 0

    def _scrape_product_links(self, response):
        links = response.xpath( # TODO: need some review about xpath
            '//*[contains(@class, "searchImg")]'
            '/a'
            '/@href'
        ).extract()
        for link in links:
            item = SiteProductItem()
            yield link, item

    def _scrape_next_results_page_link(self, response):
        next_page_url = response.xpath(
            '//*[@id="divBtnPageBtm"]'
            '/*[@rel="next"]'
            '/@href'
        ).extract()
        if next_page_url:
            return urljoin(response.url, next_page_url[0])

    @staticmethod
    def _parse_title(response):
        title = response.xpath(
            '//*[@id="prodTitle"]'
            '/*[@id="prodName"]'
            '/text()'
        ).extract()
        return title[0] if title else None

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath(
            '//*[@id="prodTitle"]'
            '//a[contains(@class, "fnts")]'
            '/text()'
        ).extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_department(response):
        departments = response.xpath(
            '//*[@id="breadCrumbs"]'
            '//a'
            '/text()'
        ).extract()
        if departments:
            return departments[-1]

    @staticmethod
    def _parse_description(response):
        description = response.xpath(
            '//*[@id="prodDesc"]'
        ).extract()
        if description:
            return description[0]

    @staticmethod
    def _parse_price(response):

        price = response.xpath(
            '//div[@id="divPrice"]'
            '/text()'
        ).extract()
        if price:
            price = re.findall(r'([0-9]+\.[0-9]{2})', price[0].replace(',', ''))
            if price:
                try:
                    price = float(price[0])
                    return Price(price=price, priceCurrency=CURRENCY)
                except ValueError:
                    pass

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.findall(r'g([0-9]+).html', response.url)
        if reseller_id:
            return reseller_id[0]

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//meta[@itemprop="sku"]/@content').extract()
        if sku:
            return sku[0]

    @staticmethod
    def _parse_model(response):
        model = re.search("model: '(.*?)',", response.body)
        if model:
            return model.group(1)

    @staticmethod
    def _parse_upc(response):
        upc = re.search("upc:'(\d+)',", response.body)
        if upc:
            return upc.group(1).zfill(12)

    @staticmethod
    def _parse_image_url(response):
        img_url = response.xpath(
            '//*[@id="divMainImg"]'
            '//*[@id="imgProduct"]'
            '/@src'
        ).extract()
        if img_url:
            return urljoin(response.url, img_url[0])

    @staticmethod
    def _parse_in_store_only(response):
        if 'In Store Only' in response.body:
            return True
        return False

    @staticmethod
    def _parse_variants(response):
        pass

    @staticmethod
    def _parse_is_out_of_stock(response):
        is_out_of_stock = response.xpath(
            '//*[@id="divPriceBlock"]'
            '//meta[@itemprop="availability"]'
            '[contains(@content, "OutOfStock")]'
        ).extract()
        return True if is_out_of_stock else None

    @staticmethod
    def _parse_no_longer_available(response):
        pass

    @staticmethod
    def _parse_related_products(response):
        related_products = []
        products = response.xpath(
            '//*[@id="ulRelated_Items"]'
            '//a[contains(@class, "txtLink")]'
        )
        for product in products:
            title = product.xpath('text()').extract()
            url = product.xpath('@href').extract()
            if title and url:
                related_products.append(
                    RelatedProduct(
                        title=title[0],
                        url=urljoin(response.url, url[0])
                    )
                )
        return related_products or None