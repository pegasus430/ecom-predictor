from __future__ import absolute_import, division, unicode_literals

import json
import re
import time
import traceback
from itertools import islice

from scrapy.conf import settings
from scrapy.http import Request
from scrapy.log import ERROR, INFO, WARNING

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value)
from product_ranking.utils import SharedCookies


class PeapodProductsSpider(BaseProductsSpider):
    name = "peapod_products"
    allowed_domains = ["peapod.com", "2captcha.com", "api.bazaarvoice.com"]

    start_url = "https://www.peapod.com/"

    TWOCAPTCHA_API_KEY = settings.get('TWOCAPTCHA_APIKEY')
    DEFAULT_ZIP = '60047'
    DEFAULT_CITY_ID = "27022"
    API_VERSION = 'v3.0'

    SOLVE_RECAPTCHA_URL = "http://2captcha.com/in.php?key={}&method=userrecaptcha&googlekey={}&pageurl={}"
    GET_SOLVED_RECAPTCHA_URL = "http://2captcha.com/res.php?key={}&action=get&id={}"
    SUBMIT_CAPTCHA_URL = "https://www.peapod.com/cdn-cgi/l/chk_captcha?id=340cbc7dda0a5996&g-recaptcha-response={}"
    SET_ZIP_URL = "https://www.peapod.com/api/{api_version}/user/guest?cityId={city_id}&customerType=C&zip={zipcode}"

    SEARCH_URL = "https://www.peapod.com/api/{api_version}/user/products?" \
                 "facet=singleRootCat,brands,nutrition,specials,newArrivals&facetExcludeFilter=true" \
                 "&filter=&flags=true&keywords={search_term}&nutrition=true&rows=120&sort=bestMatch+asc&start=0"

    PRODUCT_URL = "https://www.peapod.com/api/{api_version}/user/products/{product_id}" \
                  "?extendedInfo=true&flags=true&nutrition=true&substitute=true"

    PRODUCT_URL_OUTPUT = "https://www.peapod.com/modal/item-detail/{product_id}"

    REVIEW_URL = "https://api.bazaarvoice.com/data/reviews.json?apiVersion=5.4" \
                 "&filter=ProductId:{review_id}&include=Products&limit=10&method=reviews.json&offset=0" \
                 "&passKey=74f52k0udzrawbn3mlh3r8z0m&sort=SubmissionTime:desc&stats=Reviews"

    handle_httpstatus_list = [401, 403, 404]

    def __init__(self, disable_shared_cookies=False, zip_code=DEFAULT_ZIP, *args, **kwargs):
        # settings.overrides['USE_PROXIES'] = True
        self.br = BuyerReviewsBazaarApi(called_class=self)
        self.zip_code = zip_code
        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        super(PeapodProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(api_version=self.API_VERSION),
            site_name=self.allowed_domains[0], *args, **kwargs
        )
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3325.181 Safari/537.36"
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.shared_cookies = SharedCookies('peapod') if not disable_shared_cookies else None

    def start_requests(self):
        cookies = self.shared_cookies.get() if self.shared_cookies else None
        if not cookies and self.shared_cookies:
            self.shared_cookies.lock()
        yield Request(
            self.start_url,
            callback=self.solve_recaptcha,
            headers={'User-Agent': self.user_agent}
        )

    def solve_recaptcha(self, response):
        meta = {
            'captcha_retry_after_zipcode': response.meta.get('captcha_retry_after_zipcode', 0)
        }

        googlekey = self._recaptcha(response)

        if googlekey:
            if self.shared_cookies:
                self.shared_cookies.lock()
            googlekey = googlekey[0].split("k=")[-1]
            self.log('Sent captcha key: {}'.format(googlekey))

            return Request(
                self.SOLVE_RECAPTCHA_URL.format(
                    self.TWOCAPTCHA_API_KEY,
                    googlekey,
                    self.start_url
                ),
                callback=self.get_captcha_id,
                meta=meta,
                dont_filter=True
            )
        elif self._zipcode_needed(response):
            if self.shared_cookies:
                self.shared_cookies.lock()
            return self.enter_zipcode(response)
        else:
            return self.after_zipcode(response)

    def get_captcha_id(self, response):
        meta = {
            'captcha_retry_after_zipcode': response.meta.get('captcha_retry_after_zipcode', 0)
        }

        if "OK" in response.body:
            code = response.body.split("|")[-1]
            self.log('Got captcha id: {}'.format(code))
            time.sleep(30)
            self.log('Requesting solved captcha with id: {}'.format(code))
            yield Request(
                self.GET_SOLVED_RECAPTCHA_URL.format(
                    self.TWOCAPTCHA_API_KEY,
                    code
                ),
                callback=self.submit_captcha,
                meta=meta,
                dont_filter=True
            )

    def submit_captcha(self, response):
        meta = {
            'captcha_retry_after_zipcode': response.meta.get('captcha_retry_after_zipcode', 0)
        }
        if "OK" in response.body:
            solved_code = response.body.split("|")[-1]
            headers = {
                "referer": "https://www.peapod.com/",
                ":authority:": "www.peapod.com"
            }
            yield Request(
                self.SUBMIT_CAPTCHA_URL.format(solved_code),
                callback=self.enter_zipcode,
                dont_filter=True,
                headers=headers,
                meta=meta
            )
        else:
            retries_number = response.meta.get('retries_number', 0)
            if retries_number < 10:
                self.log('Error getting solved captcha: {}'.format(response.body))
                self.log('Retrying after 20 seconds')
                time.sleep(20)

                meta['retries_number'] = retries_number + 1
                yield Request(
                    response.url,
                    callback=self.submit_captcha,
                    dont_filter=True,
                    meta=meta
                )

    def enter_zipcode(self, response):
        meta = {
            'captcha_retry_after_zipcode': response.meta.get('captcha_retry_after_zipcode', 0)
        }

        payload = {
            "customerType": "C",
            "cityId": self.DEFAULT_CITY_ID,
            "zip": self.zip_code
        }

        yield Request(
            self.SET_ZIP_URL.format(
                zipcode=self.zip_code,
                city_id=self.DEFAULT_CITY_ID,
                api_version=self.API_VERSION
            ),
            callback=self.after_zipcode,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'User-Agent': self.user_agent
            },
            body=json.dumps(payload),
            meta=meta,
            dont_filter=True
        )

    def after_zipcode(self, response):
        if self.shared_cookies:
            self.shared_cookies.unlock()

        if self._retry_recaptcha(response):
            yield self.solve_recaptcha(response)
        else:
            for req in super(PeapodProductsSpider, self).start_requests():
                if self.product_url:
                    self.product_url = self.PRODUCT_URL.format(
                        product_id=self._extract_product_id(self.product_url),
                        api_version=self.API_VERSION
                    )
                    req.meta.get('product', {}).pop('url', None)
                    req = req.replace(url=self.product_url)
                    req = req.replace(headers={'User-Agent': self.user_agent})
                yield req.replace(dont_filter=True)

    def _scrape_product_links(self, response):
        all_products = json.loads(response.body_as_unicode()).get("response", {}).get("products", [])
        sponsored_links = self._scrape_sponsored_links(all_products)
        for product_json in all_products:
            prod = self._parse_single_product(response, product_json)
            if sponsored_links:
                prod.meta["product"]["sponsored_links"] = sponsored_links

            if isinstance(prod, Request):
                yield prod, prod.meta.get("product")
            else:
                yield None, prod

    def _scrape_sponsored_links(self, products):
        sponsored_links = []
        for prod in products:
            if prod.get('flags', {}).get('specialCode') == '*':
                sponsored_links.append(self._build_product_url(prod.get('prodId')))

        return sponsored_links

    def _get_products(self, response):
        # Need to override, because all products are parsed from search page
        # There are no single-product urls on peapod
        remaining = response.meta['remaining']
        search_term = response.meta['search_term']
        prods_per_page = response.meta.get('products_per_page')
        total_matches = response.meta.get('total_matches')
        scraped_results_per_page = response.meta.get('scraped_results_per_page')

        prods = self._scrape_product_links(response)

        if prods_per_page is None:
            # Materialize prods to get its size.
            prods = list(prods)
            prods_per_page = len(prods)
            response.meta['products_per_page'] = prods_per_page

        if scraped_results_per_page is None:
            scraped_results_per_page = self._scrape_results_per_page(response)
            if scraped_results_per_page:
                self.log(
                    "Found %s products at the first page" %scraped_results_per_page
                    , INFO)
            else:
                scraped_results_per_page = prods_per_page
                if hasattr(self, 'is_nothing_found'):
                    if not self.is_nothing_found(response):
                        self.log(
                            "Failed to scrape number of products per page", WARNING)
            response.meta['scraped_results_per_page'] = scraped_results_per_page

        if total_matches is None:
            total_matches = self._scrape_total_matches(response)
            if total_matches is not None:
                response.meta['total_matches'] = total_matches
                self.log("Found %d total matches." % total_matches, INFO)
            else:
                if hasattr(self, 'is_nothing_found'):
                    if not self.is_nothing_found(response):
                        self.log(
                            "Failed to parse total matches for %s" % response.url, WARNING)

        if total_matches and not prods_per_page:
            # Parsing the page failed. Give up.
            self.log("Failed to get products for %s" % response.url, ERROR)
            return

        for i, (reviews_req, prod_item) in enumerate(islice(prods, 0, remaining)):
            # Initialize the product as much as possible.
            prod_item['site'] = self.site_name
            prod_item['search_term'] = search_term
            prod_item['total_matches'] = total_matches
            prod_item['results_per_page'] = prods_per_page
            prod_item['scraped_results_per_page'] = scraped_results_per_page
            # The ranking is the position in this page plus the number of
            # products from other pages.
            prod_item['ranking'] = (i + 1) + (self.quantity - remaining)
            if self.user_agent_key not in ["desktop", "default"]:
                prod_item['is_mobile_agent'] = True
            if isinstance(reviews_req, Request):
                yield reviews_req
            else:
                yield prod_item

    @staticmethod
    def _scrape_total_matches(response):
        all_products = json.loads(response.body_as_unicode())
        total = all_products.get("response", {}).get("pagination", {}).get("total", 0)
        return int(total)

    def _scrape_next_results_page_link(self, response):
        return

    def _parse_single_product(self, response, product_json=None):
        product = response.meta.get('product', SiteProductItem())

        if response.status == 404:
            cond_set_value(product, 'no_longer_available', True)
            product_id = self._extract_product_id(response.url)
            url = self._build_product_url(product_id)
            cond_set_value(product, 'url', url)
            return product

        try:
            if not product_json:
                product_json = json.loads(response.body_as_unicode()).get('response').get('products')[0]
        except:
            self.log(traceback.format_exc())
            # Needed enter zip_code and city_id
            if response.status == 401:
                return self.enter_zipcode(response)
        else:

            title = product_json.get("name")
            cond_set_value(product, 'title', title)

            brand = product_json.get('brand')
            if not brand:
                brand = guess_brand_from_first_words(title)
            cond_set_value(product, 'brand', brand)

            price = Price(price=float(product_json.get("price", 0)), priceCurrency="USD")
            cond_set_value(product, 'price', price)

            cond_set_value(product, 'upc', product_json.get('upc', '').zfill(12))

            product_id = product_json.get('prodId')
            cond_set_value(product, 'reseller_id', str(product_id))

            url = self._build_product_url(product_id)
            cond_set_value(product, 'url', url)

            cond_set_value(product, 'image_url', product_json.get('image', {}).get('xlarge'))

            cond_set_value(
                product,
                'is_out_of_stock',
                product_json.get('flags', {}).get('outOfStock', True)
            )

            review_id = product_json.get('reviewId')

            if review_id:
                return Request(
                    self.REVIEW_URL.format(review_id=review_id),
                    callback=self._parse_review_data,
                    meta={
                        'product': product,
                        'product_id': review_id
                    }
                )
            else:
                return product

    def _build_product_url(self, product_id):
        return self.PRODUCT_URL_OUTPUT.format(product_id=product_id)

    @staticmethod
    def _extract_product_id(url):
        product_id = re.search(r'/(\d+)', url)
        return product_id.group(1) if product_id else None

    def _parse_review_data(self, response):
        product = response.meta.get('product')
        product['buyer_reviews'] = BuyerReviews(**self.br.parse_buyer_reviews_single_product_json(response))
        return product

    @staticmethod
    def _recaptcha(response):
        return response.xpath("//div/div/div/iframe/@src").extract()

    def _retry_recaptcha(self, response):
        captcha_retry_after_zipcode = response.meta.get('captcha_retry_after_zipcode', 0)
        if self._recaptcha(response) and captcha_retry_after_zipcode < 3:
            self.log('2captcha returned wrong value, retry number: {}'.format(captcha_retry_after_zipcode))
            response.meta['captcha_retry_after_zipcode'] = captcha_retry_after_zipcode + 1
            return True

    def _zipcode_needed(self, response):
        enter_zipcode = response.xpath('//input[@id="zipInput"]').extract()
        return bool(enter_zipcode)