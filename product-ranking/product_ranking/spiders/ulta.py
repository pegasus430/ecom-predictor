# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import re
import string
import urllib

from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    FormatterWithDefaults
from product_ranking.spiders import cond_set_value
from product_ranking.utils import is_empty


class UltaProductSpider(BaseProductsSpider):
    """ ulta.com product ranking spider

    Takes `order` argument with following possible values:

    * `bestsellers`
    * `price_asc`, `price_desc`
    * `new_arrivals`
    * `top_rated`

    There are the following caveats:

    * `upc`, `is_out_of_stock`, `sponsored_links`  are not scraped
    * `buyer_reviews` is not always scraped

    """
    name = 'ulta_products'
    allowed_domains = ["ulta.com"]
    start_urls = ["http://www.ulta.com/"]

    OOS_URL = "http://www.ulta.com/browse/inc/productDetail_loadDisplayAddToCart.jsp?skuId={sku}&productId={prod_id}"

    SEARCH_URL = "http://www.ulta.com/ulta/a/_/Ntt-{search_term}" \
                 "{sort_mode}&" \
                 "ciSelector=searchResults"
    SEARCH_URL_DEFAULT = "http://www.ulta.com/ulta/a/_/Ntt-{search_term}/Nty-1?" \
                         "Dy=1&ciSelector=searchResults"
    SORTING = None

    SORT_MODES = {
        "default": "/Nty-1?Dy=1",   # default
        "bestsellers": "?Ns=product.bestseller|1",
        "price_asc": "?Ns=product.price|0",
        "price_desc": "?Ns=product.price|1",
        "new_arrivals": "?Ns=product.startDate|1",
        "top_rated": "?Ns=topRated|1"
    }

    REVIEW_URL = "http://www.ulta.com/reviewcenter/pwr/content/{code}/{product_id}-en_US-meta.js"

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode:
            if sort_mode.lower() not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
            else:
                self.SORTING = self.SORT_MODES[sort_mode.lower()]

        # do not hit 404 multiple times
        #settings.overrides['RETRY_HTTP_CODES'] \
        #    = [c for c in settings['RETRY_HTTP_CODES'] if c != 404]

        super(UltaProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                sort_mode=self.SORTING or self.SORT_MODES['default']),
            *args,
            **kwargs)

    def start_requests(self):
        for st in self.searchterms:
            url = self.url_formatter.format(
                self.SEARCH_URL,
                search_term=urllib.quote_plus(st.encode('utf-8')),
            ).replace('%2F', '/').replace('%3F', '?').replace('%3D', '=')
            yield Request(
                url,
                meta={'search_term': st, 'remaining': self.quantity}, dont_filter=True,
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        prod = response.meta['product']
        prod['url'] = response.url

        if 'is no longer available' in ' '.join(
                response.xpath('//*[contains(@id, "isLive")]//text()').extract()).lower():
            prod['no_longer_available'] = True
            return prod

        cond_set_value(prod, 'locale', 'en-US')
        self._populate_from_html(response, prod)
        try:
            model = response.xpath('//*[@id="itemNumber"]/text()').re('\d{3,20}')[0]
        except:
            model = None
        prod['model'] = model
        prod['reseller_id'] = model
        product_id = re.findall('\?productId=([a-zA-Z0-9]+)', response.url)
        sku = response.xpath('//span[@id="itemNumber"]/text()').re('\d+')

        # Parse price
        price = self._parse_price(response)
        cond_set_value(prod, 'price', price)

        total = response.xpath(
            '//span[@class="count"]/text()'
        ).re('\d+')
        if len(total) == 0:
            prod['buyer_reviews'] = ZERO_REVIEWS_VALUE
            return prod
        else:
            total = int(total[0])
        if total == 0:
            prod['buyer_reviews'] = ZERO_REVIEWS_VALUE
            return prod

        if product_id:
            product_id = product_id[0]
            new_meta = response.meta.copy()
            new_meta['product'] = prod
            new_meta['product_id'] = product_id
            new_meta['sku'] = sku
            new_meta['initial_response'] = response
            new_meta['total_stars'] = total
            new_meta['handle_httpstatus_list'] = [404]
            code = self._get_product_code(product_id)
            return Request(self.REVIEW_URL.format(code=code,
                                                  product_id=product_id),
                           meta=new_meta, callback=self._parse_reviews)
        return prod

    def _populate_from_html(self, response, product):
        if 'title' in product and product['title'] == '':
            del product['title']
        cond_set(
            product,
            'title',
            response.xpath(
                '//div[@class="product-detail-content"]/h3/text()'
            ).extract(),
            conv=string.strip
        )
        if not product.get('title', ''):
            title = response.xpath('//h1[contains(@itemprop, "name")]//text()').extract()
            if title:
                product['title'] = title[0].strip()

        cond_set(
            product,
            'brand',
            response.xpath(
                '//div[@class="product-detail-content"]/h5/a/text()'
            ).extract(),
            conv=string.strip
        )
        if not product.get('brand', ""):
            brand = response.xpath(
                    '//h2[contains(@itemprop, "brand")]/a/text()').extract()
            if brand:
                product['brand'] = brand[0].strip()

        image_url = response.xpath(
            "//meta[@property='og:image']/@content"
        ).extract()

        if image_url:
            image = 'http:'+image_url[0]
            product['image_url'] = image

        in_store_only = response.xpath(
            '//div[@id="productBadge"]/img/@data-blzsrc[contains(.,"instore")]')

        if in_store_only:
            product['is_in_store_only'] = True
        else:
            product['is_in_store_only'] = False

    def _parse_price(self, response):
        currency = is_empty(
            response.xpath(
                '//meta[@property="product:price:currency"]/@content').extract(),
            'USD'
        )

        price = is_empty(
            response.xpath(
                '//meta[@property="product:price:amount"]/@content').extract())
        price = is_empty(
            re.findall(
                r'(\d+\.\d+)',
                price
            ), 0.00
        )
        if price:
            return Price(
                price=float(price),
                priceCurrency=currency
            )

    def _parse_out_of_stock(self, response):
        product = response.meta['product']
        oos = response.xpath("//div[@id='oosSku']//p[@class='text-error']/text()").extract()
        if oos and "we're currently out of stock of this item" in self._clean_text(oos[0]).lower():
            oos = True
        else:
            oos = False

        product['is_out_of_stock'] = oos
        return product

    def _get_product_code(self, product_id):
        # override js function
        cr = 0
        for i in range(0, len(product_id)):
            cp = ord(product_id[i])
            cp = cp * abs(255-cp)
            cr += cp
        cr %= 1023
        cr = str(cr)
        ct = 4
        for i in range(0, ct - len(cr)):
            cr = '0' + cr
        cr = cr[0:2] + "/" + cr[2:4]
        return cr

    def _parse_reviews(self, response):
        new_meta = response.meta.copy()
        product = response.meta['product']
        sku = response.meta['sku']
        prod_id = response.meta['product_id']

        total = response.meta['total_stars']
        initial_response = response.meta['initial_response']
        by_star = {}

        avg = initial_response.xpath(
            '//span[@class="pr-rating pr-rounded average"]/text()'
        ).extract()
        if avg:
            avg = float(avg[0])

        stars = re.findall('rating:(\d+)', response.body)
        for star in stars:
            if star in by_star.keys():
                by_star[star] += 1
            else:
                by_star[star] = 1

        product['buyer_reviews'] = BuyerReviews(num_of_reviews=total,
                                                average_rating=avg,
                                                rating_by_star=by_star)

        new_meta['product'] = product

        if prod_id and sku:
            return Request(
                self.OOS_URL.format(prod_id=prod_id, sku=sku[0]),
                callback=self._parse_out_of_stock,
                meta=new_meta
            )
        return product

    def _scrape_product_links(self, response):
        links = response.xpath('//li/p[@class="prod-desc"]/a/@href').extract()
        if not links:
            links = response.xpath('//*[contains(@id, "search-prod")]'
                                   '//a[contains(@class, "product")]/@href').extract()

        for link in links:
            yield link, SiteProductItem()

    def _scrape_total_matches(self, response):
        if response.xpath('//div[@class="no-result-wrap"]').extract():
            print('Not Found')
            return 0
        else:
            total = response.xpath('//span[@class="search-res-number"]/text()').extract()
            if total:
                total_matches = int(total[0])
            else:
                links = response.xpath('//li/p[@class="prod-desc"]/a/@href').extract()
                total_matches = len(links)
            return total_matches

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(
            '//li[@class="next-prev floatl-span"]/a[contains(text(), "Next")]/@href'
        ).extract()
        if next_page:
            next_page = next_page[0]
            return next_page

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

