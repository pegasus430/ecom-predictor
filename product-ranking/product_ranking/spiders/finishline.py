import re
import base64
import string
import urllib

from scrapy.conf import settings
from scrapy.http import Request

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX


class FinishlineProductSpider(BaseProductsSpider):
    name = 'finishline_products'
    allowed_domains = [
        'www.finishline.com',
        'finishline.ugc.bazaarvoice.com',
    ]

    CURRENCY = 'USD'

    SEARCH_URL = 'http://www.finishline.com/store/_/N-/Ntt-{search_term}'

    PAGINATION_URL = 'http://www.finishline.com/store/_/N-/?No={offset}&Ntt={search_term}'

    CART_PRICE_URL = 'http://www.finishline.com/store/browse/gadgets/addtocartmodal.jsp?skuId={sku}&newProductId={prod_id}'

    REVIEWS_URL = 'http://finishline.ugc.bazaarvoice.com/9345-ns/{prod_id}/reviews.djs?format=embeddedhtml'

    results_per_page = 40

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(FinishlineProductSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args, **kwargs
        )

        settings.overrides['USE_PROXIES'] = True

        self.user_agent = ('Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:53.0) Gecko/20100101 Firefox/53.0', )

        DEFAULT_REQUEST_HEADERS = settings.get('DEFAULT_REQUEST_HEADERS')
        DEFAULT_REQUEST_HEADERS['Accept-Language'] = 'en-US,en;q=0.5'

    def start_requests(self):
        if not self.searchterms:
            for request in super(FinishlineProductSpider, self).start_requests():
                yield request

        for st in self.searchterms:
            yield Request(
                url=self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote(st.encode('utf-8')),
                ),
                meta={
                    'search_term': st,
                    'remaining': self.quantity,
                    'offset': 0
                }
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
        department = self._parse_department(response)
        cond_set_value(product, 'department', department, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse stock status
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Parse "no longer available"
        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        # Parse price
        price = self._parse_price(response)
        if isinstance(price, Request):
            return price
        else:
            cond_set_value(product, 'price', price)

        # Parse reviews
        product_id = self._parse_product_id(response)
        if product_id:
            return Request(
                self.REVIEWS_URL.format(prod_id=product_id),
                self.br.parse_buyer_reviews,
                meta={'product': product},
            )

        return product

    def _scrape_total_matches(self, response):
        # It is impossible to parse total_matches
        pass

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//*[contains(@class, "product-container")]'
            '//a[contains(@id, "imgLink")][1]'
            '/@href'
        ).extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        offset = response.meta['offset'] + self.results_per_page
        pages = response.xpath(
            '//*[contains(@class, "downPagination")]'
            '//*[contains(@class, "count")]'
            '/a'
            '/text()'
        ).re(r'(\d+)')
        if pages:
            if offset < int(pages[0]) * self.results_per_page:
                st = response.meta['search_term']
                return Request(
                    url=self.url_formatter.format(
                        self.PAGINATION_URL,
                        search_term=urllib.quote_plus(st.encode('utf-8')),
                        offset=offset,
                    ),
                    meta={
                        'search_term': st,
                        'remaining': self.quantity,
                        'offset': offset,
                    }
                )

    @staticmethod
    def _parse_product_id(response):
        product_id = response.xpath(
            '//input[contains(@class, "bVProductName")]'
            '/@value'
        ).extract()
        if product_id:
            # some magic to convert all non-alpha symbols to their ascii-codes with 'char' appendix
            # original product id is looks like 'Boys_char39__Air_Jordan_Pure_Money_T_char45_Shirt'
            product_id = ''.join([
                ch if ch.isalnum() else
                    ('_char' + str(ord(ch)) + '_') if ch !=' ' else '_'
                for ch in product_id[0]
            ])
            return product_id

    @staticmethod
    def _parse_title(response):
        title = response.xpath(
            '//h1[@id="title"]'
            '/text()'
        ).extract()
        if title:
            return title[0]

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath(
            '//script[contains(text(), "FL.setup.brand")]'
            '/text()'
        ).re(r'FL.setup.brand = "(.+?)";')
        if brand:
            return brand[0]

    @staticmethod
    def _parse_department(response):
        department = response.xpath(
            '//*[contains(@class, "breadcrumbs")]'
            '/li[@itemprop="itemListElement"]'
            '//*[@itemprop="name"]'
            '/text()'
        ).extract()
        if len(department) > 2:
            return department[-1]

        department = response.xpath(
            '//script[contains(text(), "s.eVar4")]'
            '/text()'
        ).re(r's.eVar4="(.+?)";')
        if department:
            department = department[0].split(' > ')
            if len(department) > 2:
                return department[-2]

    @staticmethod
    def _parse_description(response):
        description = response.xpath(
            '//*[@id="productDescription"]'
            '/p[@itemprop="description"]'
            '/following-sibling::*'
        ).extract()
        if description:
            return ''.join(description)

    def _parse_price(self, response):
        price = response.xpath(
            '//*[@id="productPrice"]'
            '//*[contains(@class, "fullPrice")]'
            '/text()'
        ).re(FLOATING_POINT_RGEX)
        if price:
            return Price(
                priceCurrency=self.CURRENCY,
                price=float(price[0].replace(',', ''))
            )

        price = response.xpath(
            '//*[@id="productPrice"]'
            '//*[contains(@class, "nowPrice")]'
            '/text()'
        ).re(FLOATING_POINT_RGEX)
        if price:
            return Price(
                priceCurrency=self.CURRENCY,
                price=float(price[0].replace(',', ''))
            )

        price = response.xpath(
            '//*[@id="productPrice"]'
            '//*[contains(@class, "maskedFullPrice")]'
            '/text()'
        ).re(FLOATING_POINT_RGEX)
        if price:
            return Price(
                priceCurrency=self.CURRENCY,
                price=float(price[0].replace(',', ''))
            )

        cart_price = response.xpath(
            '//*[@id="productPrice"]'
            '//*[contains(@class, "maskedPriceMessage")]'
            '[contains(text(), "See price in cart")]'
            '/text()'
        ).extract()
        if cart_price:
            sku = response.xpath(
                '//*[@id="productSizes"]'
                '/*[@data-val]'
                '/@data-sku'
            ).extract()
            print(sku)
            if sku:
                sku = base64.decodestring(sku[0])
            prod_id = self._parse_reseller_id(response)
            if prod_id:
                prod_id = 'prod' + prod_id
            print(sku, prod_id)
            if sku and prod_id:
                product = response.meta['product']
                return Request(
                    url=self.url_formatter.format(
                        self.CART_PRICE_URL,
                        sku=sku,
                        prod_id=prod_id,
                    ),
                    callback=self.parse_cart_price,
                    meta={
                        'product': product
                    }
                )


    def parse_cart_price(self, response):
        product = response.meta['product']

        # TODO: Add "add to cart" request before for working properly
        price = response.xpath(
            '//*[contains(@class, "namePrice")]'
            '//*[contains(@class, "nowPrice")]'
            '/text()'
        ).re(FLOATING_POINT_RGEX)
        if price:
            price = Price(
                priceCurrency=self.CURRENCY,
                price=float(price[0].replace(',', ''))
            )
            cond_set_value(product, 'price', price)

        return product


    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.search(r'prod(\d+)', response.url)
        if reseller_id:
            return reseller_id.group(1)

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath(
            '//img[@itemprop="image"]'
            '/@src'
        ).extract()
        if image_url:
            return image_url[0]

    @staticmethod
    def _parse_is_out_of_stock(response):
        in_stock = response.xpath(
            '//*[@id="instorePickup"]'
            '/*[contains(@class, "info")]'
            '[contains(text(), "Buy Online")]'
        ).extract()
        if not in_stock:
            return True

    @staticmethod
    def _parse_no_longer_available(response):
        # Not presented
        pass