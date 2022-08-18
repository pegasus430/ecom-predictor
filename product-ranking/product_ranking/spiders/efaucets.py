import re
import urllib
import urlparse

from scrapy import Request
from scrapy.conf import settings

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from product_ranking.validation import BaseValidator


class EfaucetsProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'efaucets_products'
    allowed_domains = ['efaucets.com']
    handle_httpstatus_list = [404]

    BASE_PRODUCT_URL = 'https://www.efaucets.com/detail.asp?product_id={product_id}'
    SEARCH_URL = 'https://www.efaucets.com/search/go?w={search_term}'
    REVIEWS_URL = 'https://www.efaucets.com/reviews/pwr/content/' \
                  '{page_id_hash}/{page_id}-en_US-rollup.js'

    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.8",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98 Safari/537.36"
    }

    def __init__(self, *args, **kwargs):
        RETRY_HTTP_CODES = settings.get('RETRY_HTTP_CODES')
        if 404 in RETRY_HTTP_CODES:
            RETRY_HTTP_CODES.remove(404)
        settings.overrides['RETRY_HTTP_CODES'] = RETRY_HTTP_CODES
        super(EfaucetsProductsSpider, self).__init__(*args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for search_term in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(search_term.encode('utf-8')),
                ),
                meta={'search_term': search_term, 'remaining': self.quantity},
                callback=self._parse_helper
            )

        if self.product_url:
            cookie = {}
            gclid = None
            product_id = re.search('product_id=(.*)', self.product_url.lower())

            if 'gclid' in self.product_url:
                gclid = re.search('gclid=(.*?)&', self.product_url.lower())
            if gclid and product_id:
                cookie = {'gclid': gclid.group(1), 'Product_ID': product_id.group(1)}

            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          callback=self._parse_single_product,
                          meta={'product': prod},
                          headers=self.HEADERS,
                          dont_filter=True,
                          cookies=cookie
                          )

    def _parse_helper(self, response):
        category_url = response.xpath('//div[@class="heroText"]/a/@href').extract()
        if category_url:
            url = urlparse.urljoin(response.url, category_url[0])
            return Request(url=url, meta=response.meta)
        else:
            return self.parse(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en-US"
        reqs = []

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        price_value = self._parse_price(response)
        if price_value:
            cond_set_value(product, 'price', Price(price=price_value, priceCurrency='USD'))

        brand = self._parse_brand(response, title)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)
        cond_set_value(product, 'reseller_id', sku)

        categories = self._parse_categories(response)
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        variants = self._parse_variants(response, sku)
        cond_set_value(product, 'variants', variants)

        if self.scrape_variants_with_extra_requests:
            for variant in product.get('variants', []):
                if not variant['selected']:
                    req = Request(
                        url=variant['url'],
                        callback=self.parse_variant_price,
                        meta={'product': product},
                        dont_filter=True,
                    )
                    reqs.append(req)
                elif variant.get('selected') and price_value:
                    variant['price'] = price_value

        page_id = re.search("pr_page_id\s*=\s*'(\d+)'", response.body)
        if page_id:
            page_id = page_id.group(1)
            page_id_hash = self._generate_pageid_hash(page_id)
            req = Request(
                self.REVIEWS_URL.format(page_id_hash=page_id_hash, page_id=page_id),
                self.parse_buyer_reviews,
                meta={'product': product},
            )
            reqs.append(req)

        if reqs:
            return self.send_next_request(reqs)

        return product

    def send_next_request(self, reqs):
        req = reqs.pop(0)
        if reqs:
            req.meta['reqs'] = reqs
        return req

    def _generate_pageid_hash(self, page_id):
        # dinamically generated part of reviews url
        a = 0
        for char in page_id:
            b = ord(char)
            b = b * abs(255 - b)
            a += b
        a = a % 1023
        c = list(str(a))
        for i in range(4 - len(c)):
            c.insert(0, '0')
        a = ''.join(c)
        a = a[0:2] + '/' + a[2: 4]
        return a

    @staticmethod
    def _parse_title(response):
        title = is_empty(
            response.xpath('//*[@id="prodname"]/h1/text()').extract()
        )
        return title

    @staticmethod
    def _parse_is_out_of_stock(response):
        is_out_of_stock = bool(
            response.xpath('//div[@id="prodavailability"]').re('Out of Stock')
        )
        return is_out_of_stock

    def _parse_price(self, response):
        price = response.xpath('//div[@class="productdetails"]/div[@id="costbox"]'
                               '/div[@id="productsale"]//text()').extract()

        if price:
            return price[0].replace("$", '')

    @staticmethod
    def _parse_brand(response, title):
        brand = is_empty(
            response.xpath('//*[@id="prodmanufacturer"]/@value').extract()
        )
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    @staticmethod
    def _parse_image_url(response):
        image_url = is_empty(
            response.xpath(
                '//a[@class="MagicZoomPlus"]/@href|'
                '//img[@id="prodimage"]/@src'
            ).extract()
        )
        if image_url:
            image_url = urlparse.urljoin(response.url, image_url)

        return image_url

    @staticmethod
    def _parse_categories(response):
        categories = re.search("content_category: '(.+)'", response.body)
        if categories:
            categories = categories.group(1).split(' > ')

        return categories

    @staticmethod
    def _parse_sku(response):
        sku = is_empty(
            re.findall('product_id=(.+)&?', response.url.lower())
        )
        return sku

    def _parse_variants(self, response, product_sku):
        variants = []
        options = response.xpath('//div[@id="outercontainer"]//select/option')
        key = is_empty(
            response.xpath(
                '//div[@id="outercontainer"]/div/strong/text()'
            ).extract(), 'finish'
        ).strip(':')
        for option in options:
            sku = is_empty(option.xpath('@value').extract())
            value = is_empty(option.xpath('text()').extract())
            selected = product_sku == sku
            variant = {
                'properties': {
                    'sku': sku,
                    key: value,
                },
                'url': self.BASE_PRODUCT_URL.format(product_id=sku),
                'selected': selected
            }
            variants.append(variant)

        return variants

    def parse_variant_price(self, response):
        product = response.meta.get('product')
        reqs = response.meta.get('reqs')
        sku = self._parse_sku(response)
        price = self._parse_price(response)

        for variant in product['variants']:
            if not variant['selected'] and variant['properties']['sku'] == sku:
                variant['price'] = price

        if reqs:
            return self.send_next_request(reqs)

        return product

    def parse_buyer_reviews(self, response):
        product = response.meta.get('product')
        reqs = response.meta.get('reqs')

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {}
        }

        num_of_reviews = re.search('"?n"?:(\d+)', response.body)
        average_rating = re.search('"?d"?:([\d.]+)', response.body)
        if not num_of_reviews or not average_rating or response.status != 200:
            product['buyer_reviews'] = BuyerReviews(**ZERO_REVIEWS_VALUE)
            return product

        buyer_reviews = {
            'num_of_reviews': int(num_of_reviews.group(1)),
            'average_rating': round(float(average_rating.group(1)), 1),
            'rating_by_star': {},
        }
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews)

        if reqs:
            return self.send_next_request(reqs)

        return product

    def _scrape_total_matches(self, response):
        total_matches = is_empty(
            response.xpath(
                '//*[@class="sli_tabs"]//*[@class="sli_count"]/text()'
            ).re('\((\d+)\)'), 0
        )

        return int(total_matches)

    def _scrape_product_links(self, response):
        links = response.xpath('//h2/a[@class="product-link"]/@href').extract()
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = is_empty(
            response.xpath('//a[contains(@class, "sli_page_next")]/@href').extract()
        )

        return next_page
