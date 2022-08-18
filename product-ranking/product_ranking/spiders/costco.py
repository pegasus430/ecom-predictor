from __future__ import absolute_import, division, unicode_literals

import base64
import re
import traceback
from future_builtins import filter, map

from scrapy import Request
from scrapy.conf import settings
from scrapy.log import ERROR, WARNING

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, cond_set,
                                     cond_set_value)
from product_ranking.guess_brand import guess_brand_from_first_words


class CostcoProductsSpider(BaseProductsSpider):
    name = "costco_products"
    allowed_domains = ["costco.com"]
    start_urls = []

    SEARCH_URL = "https://www.costco.com/CatalogSearch?pageSize=96" \
        "&catalogId=10701&langId=-1&storeId=10301" \
        "&currentPage=1&keyword={search_term}"
    DEFAULT_CURRENCY = u'USD'
    use_proxies = False

    REVIEW_URL = 'http://api.bazaarvoice.com/data/products.json?passkey=bai25xto36hkl5erybga10t99&apiversion=5.5' \
                 '&filter=id:{product_id}&stats=reviews'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(CostcoProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                      'Chrome/61.0.3163.100 Safari/537.36'}
        settings.overrides['USE_PROXIES'] = True

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.custom_middlewares.IncapsulaRequestMiddleware'] = 3
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

    def parse(self, response):
        # call the appropriate method for the code. It'll only work if you set
        #  `handle_httpstatus_list = [502, 503, 504]` in the spider
        if hasattr(self, 'handle_httpstatus_list'):
            for _code in self.handle_httpstatus_list:
                if response.status == _code:
                    _callable = getattr(self, 'parse_'+str(_code), None)
                    if callable(_callable):
                        yield _callable()

        if self._search_page_error(response):
            if self.not_a_product(response):
                remaining = response.meta['remaining']
                search_term = response.meta['search_term']

                self.log("For search term '%s' with %d items remaining,"
                         " failed to retrieve search page: %s"
                         % (search_term, remaining, response.request.url),
                         WARNING)
            else:
                prod = SiteProductItem()
                prod['is_single_result'] = True
                prod['url'] = response.url
                prod['search_term'] = response.meta['search_term']

                yield Request(
                    prod['url'],
                    callback=self._parse_single_product,
                    meta={'product': prod},
                    dont_filter=True
                )

        else:
            prods_count = -1  # Also used after the loop.
            for prods_count, request_or_prod in enumerate(
                    self._get_products(response)):
                yield request_or_prod
            prods_count += 1  # Fix counter.

            request = self._get_next_products_page(response, prods_count)
            if request is not None:
                yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        # TODO: refactor it
        prod = response.meta['product']

        meta = response.meta.copy()
        reqs = []
        meta['reqs'] = reqs

        price = self._extract_price(response)
        if price:
            cond_set_value(prod,
                           'price',
                           Price(priceCurrency=self.DEFAULT_CURRENCY,
                                 price=price))
        else:
            prod['price'] = None

        # not longer available
        no_longer_available = response.xpath(
            '//*[@class="server-error" and contains(text(),'
            '"out of stock and cannot be added to your cart at this time")]')
        cond_set_value(prod, 'no_longer_available', 1 if no_longer_available else 0)

        if not no_longer_available and response.xpath('//h1[text()="Product Not Found"]'):
            prod['not_found'] = True
            return prod

        model = response.xpath('//div[@id="product-tab1"]//text()').re(
            'Model[\W\w\s]*')
        if len(model) > 0:
            cond_set(prod, 'model', model)
            if 'model' in prod:
                prod['model'] = re.sub(r'Model\W*', '', prod['model'].strip())

        title = response.xpath('//h1[@itemprop="name"]/text()').extract()
        cond_set(prod, 'title', title)

        # Title key must be present even if it is blank
        cond_set_value(prod, 'title', "")

        brand = self._parse_brand(response, prod['title'])
        cond_set_value(prod, 'brand', brand)

        img_url = response.xpath('//img[@itemprop="image"]/@src').extract()
        cond_set(prod, 'image_url', img_url)

        cond_set_value(prod, 'locale', 'en-US')
        prod['url'] = response.url

        # Categories
        categorie_filters = ['home']
        # Clean and filter categories names from breadcrumb
        categories = list(filter((lambda x: x.lower() not in categorie_filters),
                                 map((lambda x: x.strip()), response.xpath('//*[@class="crumbs"]//a/text()').extract())))

        category = categories[-1] if categories else None

        cond_set_value(prod, 'categories', categories)
        cond_set_value(prod, 'category', category)

        # Minimum Order Quantity
        try:
            minium_order_quantity = re.search('Minimum Order Quantity: (\d+)', response.body_as_unicode()).group(1)
            cond_set_value(prod, 'minimum_order_quantity', minium_order_quantity)
        except:
            pass

        shipping = response.xpath(
            '//*[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ",'
            ' "abcdefghijklmnopqrstuvwxyz"), "shipping & handling:")]'
        ).re('[\d\.\,]+')

        if shipping:
            cond_set_value(prod, 'shipping_cost', Price(priceCurrency=self.DEFAULT_CURRENCY,
                                                        price=shipping[0].strip().replace(',', '')))

        shipping_included = ''.join(response.xpath(
            '//*[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ",'
            ' "abcdefghijklmnopqrstuvwxyz"),"shipping & handling included")]'
        ).extract()).strip().replace(',', '') or \
                            response.xpath(
                                '//*[@class="merchandisingText" and '
                                'contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
                                '"abcdefghijklmnopqrstuvwxyz"), "free shipping")]') or \
                            ''.join(response.xpath(
                                '//p[contains(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ",'
                                ' "abcdefghijklmnopqrstuvwxyz"),"shipping and handling included")]'
                            ).extract()).strip().replace(',', '')

        cond_set_value(prod, 'shipping_included', 1 if shipping_included or shipping == "0.00" else 0)

        sku = response.xpath('//span[@itemprop="sku"]/text()').extract()
        cond_set_value(prod, 'sku', sku[0] if sku else None)

        not_available_store = re.search('Not available for purchase on Costco.com', response.body_as_unicode())
        cond_set_value(prod, 'available_online', 0 if not_available_store else 1)

        available_store = re.search('Item may be available in your local warehouse', response.body_as_unicode())
        if available_store:
            cond_set_value(prod, 'available_store', 1)
        else:
            available_store = re.search('"inventory" : "IN_STOCK"', response.body_as_unicode())
            if available_store:
                cond_set_value(prod, 'available_store', 1)
            else:
                cond_set_value(prod, 'available_store', 0)

        if str(prod.get('available_online', None)) == '0' and str(prod.get('available_store', None)) == '0':
            prod['is_out_of_stock'] = True

        count_review = response.xpath('//meta[contains(@itemprop, "reviewCount")]/@content').extract()
        product_id = re.findall(r'\.(\d+)\.', response.url)
        cond_set_value(prod, 'reseller_id', product_id[0] if product_id else None)
        cond_set_value(prod, 'secondary_id', product_id[0] if product_id else None)

        if product_id and count_review:
            meta['dont_proxy'] = True
            reqs.append(
                Request(
                    url=self.REVIEW_URL.format(product_id=product_id[0], index=0),
                    dont_filter=True,
                    callback=self.parse_buyer_reviews,
                    meta=meta
                ))

        if reqs:
            return self.send_next_request(reqs, response)

        return prod

    @staticmethod
    def _parse_brand(response, title):
        def parse_brand_xpath(resp):
            brand = response.xpath(
                '//div[contains(@class, "product-info-specs")]//div[text()="Brand"]/following-sibling::div/text()'
            ).extract()
            return brand[0] if brand else None

        def parse_brand_regexp(resp):
            brand = re.search('(?:Collection\sName:|Brand)</span>\s*(.*?)\s*<', response.body, re.DOTALL)
            return brand.group(1) if brand else None

        brand = parse_brand_xpath(response) or parse_brand_regexp(response) or guess_brand_from_first_words(title)
        return brand

    def parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        product = response.meta['product']
        reqs = meta.get('reqs', [])

        product['buyer_reviews'] = self.br.parse_buyer_reviews_products_json(response)

        if reqs:
            return self.send_next_request(reqs, response)
        else:
            return product

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs

        return req.replace(meta=new_meta)

    def _search_page_error(self, response):
        if not self._scrape_total_matches(response):
            self.log("Costco: unable to find a match", ERROR)
            return True
        return False

    def _scrape_total_matches(self, response):
        count = response.xpath(
            '//*[@id="secondary_content_wrapper"]/div/p/span/text()'
        ).re('(\d+)')
        count = int(count[-1]) if count else None
        if not count:
            count = response.xpath(
                '//*[@id="secondary_content_wrapper"]'
                '//span[contains(text(), "Showing results")]/text()'
            ).extract()
            count = int(count[0].split(' of ')[1].replace('.', '').strip()) if count else None
        if not count:
            count = response.css(".table-cell.results.hidden-xs.hidden-sm.hidden-md>span").re(
                r"Showing\s\d+-\d+\s?of\s?([\d.,]+)")
            count = int(count[0].replace('.', '').replace(',', '')) if count else None
        return count

    def _scrape_product_links(self, response):
        links = response.xpath('//div[contains(@class, "product-list")]'
                               '//p[@class="description"]/a/@href').extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        links = response.xpath(
            "//*[@class='pagination']"
            "/ul[2]"  # [1] is for the Items Per Page section which has .active.
            "/li[@class='active']"
            "/following-sibling::li[1]"  # [1] is to get just the next sibling.
            "/a/@href"
        ).extract()
        if links:
            link = links[0]
        else:
            link = None

        return link

    def not_a_product(self, response):
        page_type = self._find_between(response.body, 'pageType : ', ',').strip().replace("'", "")
        if page_type.lower() == 'product':
            return False
        return True

    def _extract_price(self, response):
        price = re.search(r'"price"\s*:\s*"(.+?)"', response.body_as_unicode())

        if price:
            try:
                return base64.b64decode(price.group(1))
            except TypeError:
                self.log('Unable to decode price value, {}', traceback.format_exc())

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
