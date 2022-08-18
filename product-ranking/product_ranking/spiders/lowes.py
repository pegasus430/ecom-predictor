# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import re
import json
import string

from scrapy.http import Request
from scrapy import Selector
from urlparse import urljoin

from scrapy.conf import settings


from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import cond_set_value


class LowesProductsSpider(BaseProductsSpider):
    name = 'lowes_products'
    allowed_domains = ["lowes.com", "bazaarvoice.com", "lowes.ugc.bazaarvoice.com"]

    SEARCH_URL = "https://www.lowes.com/search?searchTerm={search_term}"

    RATING_URL = "http://lowes.ugc.bazaarvoice.com/0534/{prodid}"\
        "/reviews.djs?format=embeddedhtml"

    STORES_JSON = "http://www.lowes.com/IntegrationServices/resources/storeLocator/json/v2_0/stores" \
                  "?langId=-1&storeId=10702&catalogId=10051&place={zip_code}&count=25"

    def __init__(self, zip_code='94117', *args, **kwargs):
        self.zip_code = zip_code
        settings.overrides['USE_PROXIES'] = True
        super(LowesProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2

        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3325.181 Safari/537.36"

    def start_requests(self):
        yield Request(self.STORES_JSON.format(zip_code=self.zip_code),
                      headers={'X-Crawlera-Cookies': 'disable'},
                      callback=self.set_zip_code)

    def set_zip_code(self, response):
        stores_json = json.loads(response.body)
        near_store = stores_json['Location'][0]
        if near_store:
            cookies = {'sn': near_store['KEY']}

            for request in super(LowesProductsSpider, self).start_requests():
                if self.searchterms:
                    request = request.replace(callback=self._parse_check_format,
                                              meta={'search_term': self.searchterms[0], 'remaining': self.quantity,
                                                    'cookies': cookies}
                                              )
                else:
                    request = request.replace(cookies=cookies)
                yield request

    def _parse_check_format(self, response):
        if re.search('Product Information', response.body):
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = response.url
            prod['search_term'] = self.searchterms[0]
            return Request(url=response.url, dont_filter=True, callback=self._parse_single_product,
                           meta={'product': prod}, cookies=response.meta['cookies'])
        else:
            return self.parse(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def clear_text(self, str_result):
        return str_result.replace("\t", "").replace("\n", "").replace("\r", "").replace(u'\xa0', ' ').strip()

    def _scrape_total_matches(self, response):
        total_matches = re.search('productCount = (\d+);', response.body)
        total_matches = int(total_matches.group(1)) if total_matches else 0
        return total_matches

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//*[@name="listpage_productname"]/@href').extract()
        if not links:
            links = response.xpath(
                './/*[contains(@id, "product-")]/@data-producturl').extract()

        for link in links:
            product = SiteProductItem()
            response.meta['product'] = product
            if 'http' not in link:
                link = urljoin(response.url, link)

            request = Request(link,
                              callback=self.parse_product,
                              meta=response.meta,
                              cookies=response.meta['cookies'],
                              dont_filter=True)
            yield request, product

    def _scrape_next_results_page_link(self, response):
        next_page_url = response.xpath(
            '(//*[@title="Next Page"]/@href)[1]').extract()
        if not next_page_url:
            next_page_url = response.xpath('.//*[@class="page-next"]/a/@href').extract()

        if next_page_url:
            next_link = urljoin(response.url, next_page_url[0])
            return Request(next_link, meta=response.meta)

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1/text()').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//meta[@itemprop="brand"]/@content').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_model(response):
        arr = response.xpath('//p[contains(@class,"secondary-text")]//text()').extract()
        model = None
        is_model = False
        for item in arr:
            if is_model:
                model = item.strip()
                break
            if "model #" in item.lower():
                is_model = True
        return model

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath("//input[@name='productId']/@value").extract()
        return sku[0] if sku else None

    @staticmethod
    def _parse_categories(response):
        return response.xpath(
            '//li[@itemprop="itemListElement"]//a//text()'
        ).extract() or None

    def _parse_category(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = response.xpath('.//*[contains(text(), "Item #")]/following-sibling::text()[1]').extract()
        reseller_id = reseller_id[0] if reseller_id else None
        return reseller_id

    @staticmethod
    def _parse_price(response):
        price = response.xpath(
            '//*[@class="price"]/text()').re('[\d\.\,]+')
        if not price:
            price = response.xpath('.//*[@itemprop="price"]/@content').re('[\d\.\,]+')

        if not price:
            return None
        price = price[0].replace(',', '')
        return Price(price=price, priceCurrency='USD')

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath(
            '//*[@id="prodPrimaryImg"]/@src').extract()
        if not image_url:
            image_url = response.xpath(
                './/img[contains(@class, "product-image")]/@src').extract()
        return image_url[0] if image_url else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        # this is strange website. ex: on page source, item availability is out of stock but it is in stock.
        if 'Add To Cart' in response.body_as_unicode():
            return False
        return True

    @staticmethod
    def _parse_no_longer_available(response):
        availability = response.xpath('//div[contains(@class, "pd-shipping-delivery")]//div[@class="media-body"]'
                                      '/p/text()').extract()
        return availability and 'unavailable' in availability[0].strip()

    def parse_product(self, response):
        product = response.meta['product']

        # Set locale
        product['locale'] = 'en_US'

        in_store = self._parse_available_in_store(response)
        cond_set_value(product, 'is_in_store_only', in_store)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse model
        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse stock status
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        # Reviews
        bv_product_id = response.xpath('//*[@id="bvProductId"]/@value').extract()
        bv_product_id = bv_product_id[0] if bv_product_id else None
        if not bv_product_id:
            bv_product_id = response.url.split('/')[-1]
        if bv_product_id:
            url = self.RATING_URL.format(prodid=bv_product_id.split('?')[0])
            return Request(url,
                           dont_filter=True,
                           callback=self._parse_bazaarv,
                           meta={'product': product})

        return product

    def _parse_available_in_store(self, response):
        store_info = response.xpath("//div[contains(@class, 'pd-item-map')]//a/text()").extract()
        if self._parse_is_out_of_stock(response) and store_info and store_info[0].lower().strip() == 'in-store map':
            return True
        return False

    def _parse_bazaarv(self, response):
        product = response.meta['product']
        text = response.body_as_unicode().encode('utf-8')
        if response.status == 200:
            x = re.search(
                r"var materials=(.*),\sinitializers=", text, re.M + re.S)
            if x:
                jtext = x.group(1)
                jdata = json.loads(jtext)

                html = jdata['BVRRSourceID']
                sel = Selector(text=html)
                avrg = sel.xpath(
                    "//div[contains(@id,'BVRRRatingOverall')]"
                    "/div[@class='BVRRRatingNormalOutOf']"
                    "/span[contains(@class,'BVRRRatingNumber')]"
                    "/text()").extract()
                if avrg:
                    try:
                        avrg = float(avrg[0])
                    except ValueError:
                        avrg = 0.0
                else:
                    avrg = 0.0
                total = sel.xpath(
                    "//div[@class='BVRRHistogram']"
                    "/div[@class='BVRRHistogramTitle']"
                    "/span[contains(@class,'BVRRNonZeroCount')]"
                    "/span[@class='BVRRNumber']/text()").extract()
                if total:
                    try:
                        total = int(total[0])
                    except ValueError:
                        total = 0
                else:
                    total = 0

                hist = sel.xpath(
                    "//div[@class='BVRRHistogram']"
                    "/div[@class='BVRRHistogramContent']"
                    "/div[contains(@class,'BVRRHistogramBarRow')]")
                distribution = {}
                for ih in hist:
                    name = ih.xpath(
                        "span/span[@class='BVRRHistStarLabelText']"
                        "/text()").re("(\d) star")
                    try:
                        if name:
                            name = int(name[0])
                        value = ih.xpath(
                            "span[@class='BVRRHistAbsLabel']/text()").extract()
                        if value:
                            value = int(value[0])
                        distribution[name] = value
                    except ValueError:
                        pass
                if distribution:
                    reviews = BuyerReviews(total, avrg, distribution)
                    cond_set_value(product, 'buyer_reviews', reviews)

        return product
