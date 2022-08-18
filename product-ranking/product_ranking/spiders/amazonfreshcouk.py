# -*- coding: utf-8 -*-


from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function

import json
import traceback
import string
import urlparse

import re
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.utils import is_empty
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import cond_set, cond_set_value
from scrapy.http import FormRequest
from scrapy.log import ERROR, WARNING
from .amazonfresh import AmazonFreshProductsSpider


class AmazonFreshCoUkProductsSpider(AmazonFreshProductsSpider):
    name = "amazonfreshcouk_products"
    allowed_domains = ["www.amazon.co.uk", "amazon.com"]

    SEARCH_URL = 'https://www.amazon.co.uk/s/ref=nb_sb_noss?url=search-alias%3Damazonfresh&field-keywords={search_term}'

    CSRF_TOKEN_URL = "https://www.amazon.co.uk/afx/regionlocationselector/"

    ZIP_URL = 'https://www.amazon.co.uk/afx/regionlocationselector/ajax/updateZipcode'

    WELCOME_URL = 'https://www.amazon.co.uk/Amazon-Fresh-UK-Grocery-Shopping/b/ref=topnav_storetab_fresh?ie=UTF8&node=6723205031'

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Host': 'www.amazon.co.uk',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36'
    }

    def __init__(self, *args, **kwargs):
        super(AmazonFreshCoUkProductsSpider, self).__init__(*args, **kwargs)
        self.zip_code = kwargs.get('zip_code', 'EC2R 6AB')

    def login_handler(self, response):
        try:
            data = json.loads(response.body)
            csrf_token = re.search(
                '"freshCSRFToken":"([^"]*?)"',
                data['regionLocationSelectorJsonKey']['html']).group(1)
        except:
            self.log('Error Parsing FreshToken: {}'.format(traceback.format_exc()), WARNING)
        else:
            return FormRequest(
                self.ZIP_URL,
                formdata={
                    'token': csrf_token,
                    'zipcode': self.zip_code
                },
                callback=self.after_login,
                dont_filter=True
            )

    def after_login(self, response):
        for req in super(AmazonFreshProductsSpider, self).start_requests():
            yield req.replace(headers=self.headers)

    def __convert_to_price(self, x):
        price = re.findall(r'(\d+\.?\d*)', x)
        if not price:
            self.log('Error while parse price.', ERROR)
            return None
        return Price(
            priceCurrency='GBP',
            price=float(price[0])
        )

    def parse_product(self, response):

        if self._has_captcha(response):
            return self._handle_captcha(
                response,
                self.parse_product
            )
        elif response.meta.get('captch_solve_try', 0) >= self.captcha_retries:
            product = response.meta['product']
            self.log("Giving up on trying to solve the captcha challenge after"
                     " %s tries for: %s" % (self.captcha_retries, product['url']),
                     level=WARNING)
            return None

        prod = response.meta['product']

        # check if we have a previously scraped product, and we got a 'normal' title this time
        _title = self._scrape_title(response)
        if _title and isinstance(_title, (list, tuple)):
            _title = _title[0]
            if 'Not Available in Your Area' not in _title:
                if getattr(self, 'original_na_product', None):
                    prod = self.original_na_product
                    prod['title'] = _title
                    return prod

        query_string = urlparse.parse_qs(urlparse.urlsplit(response.url).query)
        cond_set(prod, 'model', query_string.get('asin', ''))

        brand = response.xpath('//div[@class="byline"]/a/text()').extract()
        if not brand:
            brand = response.xpath('//div[@id="mbc"]/@data-brand').extract()
        if not brand:
            brand = re.search('brand=(.*?)&', response.body)
            if brand:
                brand = brand.group(1)
                prod['brand'] = brand
        cond_set(prod, 'brand', brand)

        if re.search('Business Price', response.body):
            price = response.xpath('//span[@id="priceblock_businessprice"]/text()').extract()
        else:
            price = response.xpath(
                '//div[@class="price"]/span[@class="value"]/text()').extract()
        cond_set(prod, 'price', price)
        if prod.get('price', None):
            if '$' not in prod['price']:
                self.log('Unknown currency at %s' % response.url, level=ERROR)
            else:
                prod['price'] = Price(
                    price=prod['price'].replace('$', '').replace(
                        ',', '').replace(' ', '').strip(),
                    priceCurrency='GBP'
                )

        seller_all = response.xpath('//div[@class="messaging"]/p/strong/a')

        if seller_all:
            seller = seller_all.xpath('text()').extract()
            if seller:
                prod["marketplace"] = [{
                    "name": seller[0],
                    "price": prod["price"],
                }]
        img_url = response.xpath(
            '//div[@id="mainImgWrapper"]/img/@src').extract()
        cond_set(prod, 'image_url', img_url)
        cond_set(prod, 'locale', ['en_GB'])
        cond_set(
            prod,
            'title',
            response.xpath('//h1[@id="title"]/span/text()').extract(),
            string.strip
        )
        cond_set(
            prod,
            'brand',
            response.xpath('//span[@id="brand"]/text()').extract()
        )
        cond_set(
            prod,
            'price',
            response.xpath(
                '//span[@id="priceblock_ourprice"]/text()').extract(),
            self.__convert_to_price
        )
        cond_set(
            prod,
            'description',
            response.xpath(
                '//div[@id="productDescription"]/p/text()').extract(),
            string.strip
        )

        # Parse price per volume
        price_volume = self._parse_price_per_volume(response)
        if price_volume:
            cond_set_value(prod, 'price_per_volume', price_volume[0])
            cond_set_value(prod, 'volume_measure', price_volume[1])

        save_percent_amount = self._parse_save_percent_amount(response)
        if save_percent_amount:
            cond_set_value(prod, 'save_percent', save_percent_amount[0])
            cond_set_value(prod, 'save_amount', save_percent_amount[1])

        buy_save_amount = self._parse_buy_save_amount(response)
        cond_set_value(prod, 'buy_save_amount', buy_save_amount)

        was_now = self._parse_was_now(response)
        cond_set_value(prod, 'was_now', was_now)

        promotions = any([
            price_volume,
            save_percent_amount,
            buy_save_amount,
            was_now
        ])
        cond_set_value(prod, 'promotions', promotions)

        cond_set(
            prod,
            'image_url',
            response.xpath(
                '//div[@id="imgTagWrapperId"]/img/@data-a-dynamic-image'
            ).extract(),
            self.__parse_image_url
        )
        rating = response.xpath('//span[@class="crAvgStars"]')
        cond_set(
            prod,
            'model',
            rating.xpath(
                '/span[contains(@class, "asinReviewsSummary")]/@name'
            ).extract()
        )
        reviews = self.__parse_rating(response)
        if not reviews:
            cond_set(
                prod,
                'buyer_reviews',
                ZERO_REVIEWS_VALUE
            )
        else:
            prod['buyer_reviews'] = reviews
        prod['is_out_of_stock'] = not bool(response.xpath(
            '//span[@id="freshAddToCartButton"]').extract())

        title = self._scrape_title(response)
        cond_set(prod, 'title', title)

        cond_set_value(prod, 'fresh', 'Fresh')

        return prod

    def __parse_image_url(self, x):
        try:
            images = json.loads(x)
            return images.keys()[0]
        except Exception as e:
            self.log('Error while parse image url. ERROR: %s.' % str(e), ERROR)
            return None

    def __parse_rating(self, response):
        try:
            total_reviews = int(response.xpath(
                '//span[@data-hook="total-review-count"]/text()'
            )[0].extract().replace(',', ''))

            average_rating = response.xpath(
                '//*[@data-hook="average-star-rating"]/span/text()'
            )[0].extract()
            average_rating = float(re.search('(.*) out', average_rating).group(1))
            return BuyerReviews(
                num_of_reviews=total_reviews,
                average_rating=average_rating,
                rating_by_star={}
            )
        except:
            self.log('Error while parse rating: {}'.format(traceback.format_exc()), WARNING)
            return None

    def _scrape_total_matches(self, response):
        count_text = is_empty(response.xpath(
            '//h2[@id="s-result-count"]/text() | '
            '//h1[@id="s-result-count"]/text() |'
            '//span[@id="s-result-count"]'
        ).extract())
        if not count_text:
            return 0
        count = re.findall(r'of\s([\d,]+)', count_text)
        if not count:
            count = re.findall(r'([\d,]+)\sresults', count_text)
        return int(count[0].replace(',', '')) if count else 0

    def _scrape_next_results_page_link(self, response):
        link = is_empty(response.xpath(
            '//a[@id="pagnNextLink"]/@href'
        ).extract())
        if not link:
            return None
        return "https://www.amazon.co.uk" + link \
            if link.startswith('/') else link

    def _get_products(self, response):
        for req in super(AmazonFreshCoUkProductsSpider, self)._get_products(response):
            yield req.replace(headers=self.headers)
