import json
import string
import traceback
import urllib

import re
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import (Price, SiteProductItem)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.utils import SharedCookies
from scrapy.http import Request, FormRequest
from scrapy.log import WARNING, ERROR
from scrapy.conf import settings


class VonsProductsSpider(BaseProductsSpider):
    name = 'vons_products'

    zip = '92154'

    allowed_domains = ["safeway.com", "shop.vons.com", "www.vons.com", "vons.com"]

    SEARCH_URL = "https://shop.{domain}.com/bin/safeway/product/results?key=search&value={search_term}&brand="

    PRICE_URL = 'https://shop.{domain}.com/bin/safeway/product/price?id={id}'

    IMAGE_URL = 'http://s7d2.scene7.com/is/image/ABS/{}'

    CMS_LOGIN = 'https://www.{domain}.com/CMS/account/login/?FullSite=Y&goto=http://www.{domain}.com/'

    AUTH_LOGIN = 'https://www.{domain}.com/iaaw/service/authenticate'

    SHOP_LOGIN = 'https://shop.{domain}.com/bin/safeway/login'

    START_URL = 'http://www.{domain}.com'

    HOME_URL = 'http://www.{domain}.com/?FullSite=Y'

    ZIP_URL = 'https://shop.{domain}.com/bin/safeway/store?zipcode={zip}&banner={banner}'

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': "Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0",
    }

    def __init__(self, disable_shared_cookies=True, *args, **kwargs):
        self.domain = self.name.split('_')[0]
        super(VonsProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                domain=self.domain),
            site_name=self.allowed_domains[1], *args, **kwargs)

        self.ACCOUNT = {
            self.zip: ('laurebaltazar@gmail.com', '12345678')
        }

        self.payload = {
            "password": self.ACCOUNT[self.zip][1],
            "rememberMe": True,
            "source": "WEB",
            "userId": self.ACCOUNT[self.zip][0]
        }

        self.shared_cookies = SharedCookies(self.domain) if not disable_shared_cookies else None

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        if self.shared_cookies:
            self.shared_cookies.lock()

        yield Request(
            self.url_formatter.format(self.START_URL),
            callback=self.cms_login,
            headers=self.headers
        )

    def cms_login(self, response):

        yield Request(
            self.url_formatter.format(self.CMS_LOGIN),
            callback=self.autenticate,
            headers=self.headers
        )

    def autenticate(self, response):
        headers = self.headers.copy()
        headers.update({
            'Host': "www.{}.com".format(self.domain),
            'Accept': "application/json, text/plain, */*",
            'Accept-Language': "en-US,en;q=0.5",
            'Accept-Encoding': "gzip, deflate, br",
            "Content-Type": "application/json;charset=utf-8",
            'Referer': response.url,
            'Connection': "keep-alive",
        })
        yield Request(
            self.url_formatter.format(self.AUTH_LOGIN),
            method="POST",
            body=json.dumps(self.payload),
            callback=self.start_login,
            headers=headers,
            meta={'headers': headers}
        )

    def start_login(self, response):
        headers = response.meta['headers']
        headers.pop('Content-Type')
        headers.update({
            'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            'Accept-Encoding': "gzip, deflate",
            'Connection': "keep-alive",
        })
        yield Request(self.url_formatter.format(self.HOME_URL),
                      callback=self._shop_login,
                      headers=headers,
                      meta={'headers': headers}
                      )

    def _shop_login(self, response):
        headers = response.meta['headers']
        headers.update({
            'Host': "shop.{}.com".format(self.domain),
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept-Encoding': "gzip, deflate, br",
            'Referer': 'https://shop.{}.com/welcome.html'.format(self.domain),
            'Upgrade-Insecure-Requests': "1"
        })

        url = self.ZIP_URL.format(domain=self.domain, zip=self.zip, banner=self.domain)
        r = Request(url=url,
                    callback=self._check_zip,
                    headers=headers,
                    meta={'headers': headers})
        yield r

    def _check_zip(self, response):
        r = FormRequest(url=self.SHOP_LOGIN.format(domain=self.domain),
                        formdata={'zipcode': self.zip,
                                  'resourcePath': '/content/shop/{}/en/welcome/jcr:content/root'
                                                  '/responsivegrid/column_control/par_0'
                                                  '/two_column_zip_code_'.format(self.domain)}
                       )
        r = r.replace(callback=self._start_requests,
                      meta=response.meta)
        return r

    def _start_requests(self, response):
        if self.shared_cookies:
            self.shared_cookies.unlock()

        headers = response.meta['headers']
        for st in self.searchterms:
            headers.update({
                'Accept': "application/json, text/plain, */*",
                'Referer': "http://shop.vons.com/home.html",
            })
            yield Request(
                self.url_formatter.format(self.SEARCH_URL, search_term=urllib.quote_plus(st.encode('utf-8'))),
                headers=headers,
                meta={'search_term': st, 'remaining': self.quantity},
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''

            yield Request(
                url=self.product_url,
                callback=self._parse_single_product,
                headers=self.headers,
                meta={'product': prod},
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        title = response.xpath('//*[@id="productTitle"]/text()').extract()
        if title:
            cond_set_value(product, 'title', title[0], conv=string.strip)

            brand = guess_brand_from_first_words(title[0])
            cond_set_value(product, 'brand', brand)

        product['locale'] = 'en_US'
        product['zip_code'] = self.zip
        product['is_out_of_stock'] = False

        headers = self.headers.copy()
        headers.update({'X-Requested-With': 'XMLHttpRequest'})
        reseller_id = re.findall("detail\.(\d+)\.", product['url'])
        if reseller_id:
            cond_set_value(product, 'image_url', self.IMAGE_URL.format(reseller_id[0]), conv=string.strip)
            cond_set_value(product, 'reseller_id', reseller_id[0], conv=string.strip)
            return Request(
                url=self.url_formatter.format(self.PRICE_URL, id=reseller_id[0]),
                callback=self._parse_price,
                headers=headers,
                meta=meta
            )
        self.log("Cannot continue due to missing reseller ID", WARNING)
        return product

    def _parse_price(self, response):
        product = response.meta['product']
        try:
            price = json.loads(response.body)
            price = float(price.get('productsinfo')[0].get('price'))
        except:
            self.log("Failed to parse price: {}".format(traceback.format_exc()), ERROR)
            price = 0.00
        finally:
            cond_set_value(product, 'price', Price(price=price, priceCurrency='USD'))
            return product

    def _load_search_results(self, response):
        try:
            data = json.loads(response.body)
            return data['products']
        except:
            self.log("Failed to load search results from JSON: {}".format(traceback.format_exc()))
            return []

    def _scrape_total_matches(self, response):
        return len(self._load_search_results(response))

    def _scrape_product_links(self, response):
        products = self._load_search_results(response)

        for product in products:
            yield None, self._fill_product(product)

    def _fill_product(self, product):
        result = SiteProductItem()
        result['locale'] = 'en_US'
        result['zip_code'] = self.zip
        result['is_out_of_stock'] = False
        result['title'] = product.get('name')
        result['brand'] = guess_brand_from_first_words(product.get('name'))
        result['reseller_id'] = product.get('id')
        result['image_url'] = product.get('image')
        result['categories'] = filter(lambda x: x is not None, [product.get('departmentName'), product.get('aisleName'),
                                                                product.get('shelfName')])
        result['department'] = product.get('shelfName')
        result['price'] = Price(price=product.get('price') or 0.00, priceCurrency='USD')

        return result

    def _scrape_next_results_page_link(self, response):
        return None
