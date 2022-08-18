# -*- coding: utf-8 -*-
import re
import urllib
import string
from scrapy.http import Request
from scrapy.log import ERROR, WARNING
from urlparse import urljoin
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import cond_set, cond_set_value
from product_ranking.spiders.ocado import OcadoProductsSpider


class OcadoMobileProductsSpider(OcadoProductsSpider):
    name = 'ocado_mobile_products'
    allowed_domains = ['ocado.com']
    start_urls = []

    total_matches_requests = []
    total_matches = 0
    auth_token = None

    DEV_ID = 'e1d73a616b00ba5a' # TODO: Investigate how generates the device id (os version, serial, IMEI...?)
    AUTH_URL = 'https://mobile.ocado.com/webservices/mobileDevice/{dev_id}'.format(dev_id=DEV_ID)
    AUTH_FORMAT = 'token:{}'

    # Desktop and mobile product page are same, we use desktop url passing prod_id
    # Also there is product name slug required (e.g. My-Best-Fresh-Milk), can be any string (we pass "none")
    PROD_URL = 'https://www.ocado.com/webshop/product/none/{prod_id}?dnr=y'

    SEARCH_LIMIT = 10000
    SEARCH_URL = 'https://mobile.ocado.com/webservices/catalogue/items/search?q={search_term}&limit={limit}&clustered=1'

    EXTRA_HEADERS = {
        'Accept-Currency': 'GBP',
        'StoreId': 'ocado',
        'User-Agent': 'Ocado-Android-Application/1.39.4.649',
        'Referer': None
    }

    # Overrides method to get auth_token first
    def start_requests(self):
        if self.searchterms:
            yield Request(
                url=self.AUTH_URL,
                callback=self._get_auth_id
            )

        # here is strange behavior, when call super(OcadoMobileProductsSpider, self).start_requests()
        # nothing happens, like base method is empty
        if self.product_url:
            # super(OcadoMobileProductsSpider, self).start_requests() #TODO: investigate behaviour of parent method call
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def parse_product(self, response):
        product = response.meta['product']

        title_list = response.xpath(
            "//h1[@class='productTitle'][1]//text()").extract()

        if len(title_list) >= 2:
            cond_set_value(product, 'title', self.clear_desc(title_list[-2:]))

        price = response.xpath("//div[@id='bopRight']//meta[@itemprop='price']/@content").extract()
        if price:
            price = price[0]
            price = float(price.replace(',',''))
            cond_set_value(product, 'price', Price(priceCurrency="GBP", price=price))
        else:
            cond_set_value(product, 'price', Price(priceCurrency="GBP", price=0))

        img_url = response.xpath("//ul[@id='galleryImages']/li[1]/a/@href").extract()
        if img_url:
            cond_set_value(product, 'image_url', urljoin(response.url, img_url[0]))

        description = self.clear_desc(response.xpath("//div[@id='bopBottom']"
                                                     "//h2[@class='bopSectionHeader' and text()[1]"
                                                     "='Product Description'][1]"
                                                     "/following-sibling::*[@class='bopSection']"
                                                     "//text()").extract())
        cond_set_value(product, 'description', description)

        cond_set_value(product, 'locale', "en_GB")

        is_out_of_stock = self._is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        regex = "\/(\d+)"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        brand = response.xpath("string(//div[@id='bopBottom']//*[@itemprop='brand'])").extract()
        cond_set(product, 'brand', brand, string.strip)

        buyer_reviews = self._parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        return product

    def _get_auth_id(self, response):
        try:
            self.auth_token = str(response.xpath('/device/token/text()').extract()[0])
            if self.auth_token:
                self.EXTRA_HEADERS.update({
                    'Authorization': self.AUTH_FORMAT.format(self.auth_token)
                })
                if self.searchterms:
                    for st in self.searchterms:
                        yield Request(
                            self.url_formatter.format(
                                self.SEARCH_URL,
                                search_term=urllib.quote_plus(st.encode('utf-8')).replace(' ', '+'),
                                limit=self.SEARCH_LIMIT
                            ),
                            meta={
                                'search_term': st,
                                'remaining': self.quantity
                            },
                            headers=self.EXTRA_HEADERS
                        )
        except IndexError:
            self.log('Can\'t get auth_token', level=ERROR)

    @staticmethod
    def _parse_clusters(response):
        return response.xpath('//searchResults/cluster')

    @staticmethod
    def _parse_tags(cluster):
        return cluster.xpath('./tags/tag')

    @staticmethod
    def _parse_items(cluster):
        return cluster.xpath(
            './items/item/@sku'
        )

    @staticmethod
    def _parse_all_items(response):
        return response.xpath(
            '//item/@sku'
        )

    @staticmethod
    def _parse_department(tags):
        if tags and isinstance(tags, list):
            try:
                department = tags[-1].xpath('./@name').extract()[0]
                return department
            except IndexError:
                pass

    def _scrape_product_links(self, response):
        clusters = self._parse_clusters(response)
        for cluster in clusters:
            tags = self._parse_tags(cluster)
            department = self._parse_department(tags)
            if not department:
                self.log(
                    'Can\'t parse department for tags: {}'.format(tags),
                    level=WARNING
                )
            ids = self._parse_items(cluster).extract()

            for _id in ids:
                link = self.PROD_URL.format(prod_id=_id)
                prod = SiteProductItem(
                    department=department or None
                )
                yield link, prod

    def _scrape_total_matches(self, response):
        return len(self._parse_all_items(response))

    # No need to get pagination if there is no pagination
    def _scrape_next_results_page_link(self, response):
        pass