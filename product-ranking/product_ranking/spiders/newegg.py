# -*- coding: utf-8 -*-#

import json
import re
import traceback
from lxml import html
import urllib
import urlparse
from scrapy.conf import settings

from scrapy.http import Request, FormRequest
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from scrapy.log import ERROR, INFO, WARNING
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.utils import is_empty


class NeweggProductSpider(BaseProductsSpider):
    name = 'newegg_products'
    allowed_domains = ["www.newegg.com"]

    PAGINATE_URL = "https://www.newegg.com/Product/ProductList.aspx" \
                 "?Submit=ENE&N=-1" \
                 "&IsNodeId=1" \
                 "&Description={search_term}" \
                 "&page={page_num}" \
                 "&bop=And" \
                 "&PageSize=36" \
                 "&order=BESTMATCH"

    SEARCH_URL = "https://www.newegg.com/Product/ProductList.aspx" \
                 "?Submit=ENE&DEPA=0&Order=BESTMATCH" \
                 "&Description={search_term}&N=-1&isNodeId=1"

    CATEGORY_SEARCH_URL = "https://www.newegg.com/Product/ProductList.aspx" \
                          "?Submit=StoreIM&IsNodeId=1&bop=And&Depa=3" \
                          "&Category={category_id}&Page={page_num}&PageSize=36&order=BESTMATCH"

    REVIEW_URL = "https://www.newegg.com/Common/Ajax/ProductReview2016.aspx" \
                 "?action=Biz.Product.ProductReview.switchReviewTabCallBack" \
                 "&callback=Biz.Product.ProductReview.switchReviewTabCallBack&" \
                 "&Item={product_id}&review=0&SummaryType=0" \
                 "&PurchaseMark=false&SelectedRating=-1&VideoOnlyMark=false&VendorMark=false" \
                 "&Type=Seller&ItemOnlyMark=true&chkItemOnlyMark=on&Keywords=(keywords)&SortField=0&DisplaySpecificReview=1"

    CAPTCHA_URL = 'https://www.newegg.com/areyouahuman?referer={referer}&why=8'

    def __init__(self, *args, **kwargs):
        super(NeweggProductSpider, self).__init__(*args, **kwargs)
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.middlewares.twocaptcha.TwoCaptchaMiddleware'] = 500
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
        settings.overrides['CAPTCHA_SOLVER'] = 'product_ranking.middlewares.captcha.solvers.recaptcha.RecaptchaSolver'
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36'

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for request in super(NeweggProductSpider, self).start_requests():
            request = request.replace(dont_filter=True)
            if not request.meta.get('product'):
                request = request.replace(callback=self._parse_search)
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _parse_search(self, response):
        totals = re.findall(r' itemCount:\s*(\d+)\s*,', response.body)
        if totals:
            return self.parse(response)
        else:
            url = is_empty(response.xpath('//a[@class="link-more"]/@href').extract())
            if not url:
                self.log('can not extract the search_url')
                return
            st = response.meta.get('search_term')
            if st:
                return Request(
                    self.url_formatter.format(
                        url,
                        search_term=urllib.quote_plus(st.encode('utf-8')),
                    ),
                    meta={'search_term': st, 'remaining': self.quantity},
                    dont_filter=True
                )

    def parse_product(self, response):
        meta = response.meta
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self.parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self.parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse model
        model = self.parse_model(response)
        cond_set_value(product, 'model', model)

        # Parse price
        price = self.parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self.parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse description
        description = self.parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse stock status
        is_out_of_stock = self.parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse variants
        variants = self.parse_variant(response)
        cond_set_value(product, 'variants', variants)

        # Parse review
        product_id = self.parse_product_id(response)
        cond_set_value(product, 'reseller_id', product_id)

        if product_id:
            url = self.REVIEW_URL.format(product_id=product_id)
            return Request(
                url=url,
                callback=self._parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    @staticmethod
    def parse_product_id(response):
        product_id = response.xpath('//input[@id="mboParentItemNumber"]/@value').extract()
        return product_id[0] if product_id else None

    def parse_variant(self, response):
        product_property = re.findall(r'properties: (.*?)\],', response.body)
        if not product_property:
            return []
        try:
            variants = json.loads(product_property[0] + ']')
            key = variants[0]['description']
            return [{key: value['description']} for value in variants[0]['data']]
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            return []

    @staticmethod
    def parse_price(response):
        currency = "USD"
        price = is_empty(response.xpath('//*[@itemprop="price"]/@content').extract())

        if price:
            price = Price(price=price, priceCurrency=currency)
        return price

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            review_text = response.body.replace('Biz.Product.ProductReview.switchReviewTabCallBack(', '')
            review_text = review_text.replace('});', '}')
            review_json = json.loads(review_text)
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE
            review_json = None
        try:
            review_html = html.fromstring(review_json['ReviewList'])
            sum = 0
            for i in range(1, 6):
                review_count = review_html.xpath('//span[@id="reviewNumber{0}" and @class="count"]/text()'.format(i))
                if review_count:
                    review_count = int(review_count[0].replace(',', ''))
                    buyer_review_values['rating_by_star'][str(i)] = review_count
                    buyer_review_values['num_of_reviews'] += review_count
                    sum += review_count * i
                else:
                    buyer_review_values['rating_by_star'][str(i)] = 0
            buyer_review_values['average_rating'] = round(float(sum) / buyer_review_values['num_of_reviews'], 1)
            buyer_reviews = BuyerReviews(**buyer_review_values)
            product['buyer_reviews'] = buyer_reviews
        except:
            self.log('Error while parsing review: {}'.format(traceback.format_exc()), INFO)
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE
        return product

    def parse_stock_status(self, response):
        stock_status = re.findall(r"product_instock:\['(.*?)'\],", response.body)
        other_stock_status = response.xpath('//*[@itemprop="availability"]/@href').extract()

        in_stock = False
        if stock_status and stock_status[0] == '1':
            in_stock = True
        if other_stock_status and 'InStock' in other_stock_status[0]:
            in_stock = True

        return not in_stock

    def parse_description(self, response):
        descriptions = response.xpath('//div[@class="grpBullet"]').extract()
        desc = ""
        for i in descriptions:
            desc += self._clean_text(i)
        return desc if descriptions else None

    @staticmethod
    def parse_title(response):
        title = is_empty(response.xpath('//h1/span[@itemprop="name"]/text()').extract())
        return title if title else None

    @staticmethod
    def parse_brand(response):
        brand = is_empty(response.xpath('//dl[contains(dt/text(), "Brand")]/dd/text()').extract())
        return brand if brand else None

    @staticmethod
    def parse_model(response):
        model = is_empty(response.xpath('//dl[contains(dt/text(), "Model")]/dd/text()').extract())
        return model if model else None

    @staticmethod
    def parse_image_url(response):
        image = is_empty(response.xpath('//div[@class="objImages"]'
                                        '//span[@class="mainSlide"]'
                                        '/img/@src').extract())
        if image:
            return urlparse.urljoin(response.url, image)

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        total_matches = re.findall(r' itemCount:\s*(\d+)\s*,', response.body)
        return int(total_matches[0]) if total_matches else 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        links = response.xpath(
            '//div[contains(@class, "item-container")]'
            '/a[contains(@class, "item-img")]/@href'
        ).re('.+/Product/.+')

        if links:
            for link in links:
                yield link, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_link = response.xpath('//link[@rel="next"]/@href').extract()
        total_matches = self._scrape_total_matches(response)
        meta = response.meta
        current_page = meta.get('current_page')
        if not current_page:
            current_page = 1
        if current_page * 36 >= total_matches:
            return
        current_page += 1
        url = None
        if next_link:
            url = next_link[0]
        elif 'Category' in response.url:
            category_id = re.findall(r"Category:'(.*?)'", response.body)
            if not category_id:
                return None
            url = self.CATEGORY_SEARCH_URL.format(category_id=category_id[0], page_num=current_page)
        else:
            st = response.meta['search_term']
            url = self.PAGINATE_URL.format(search_term=st, page_num=current_page)
        meta['current_page'] = current_page
        if url:
            return Request(
                url=url,
                meta=meta,
                dont_filter=True
            )

    @staticmethod
    def get_captcha_key(response):
        captcha_key = response.xpath('//div[@id="g-recaptcha"]/@data-sitekey').extract()
        return captcha_key[0] if captcha_key else None

    def is_captcha_page(self, response):
        return bool(self.get_captcha_key(response))

    def get_captcha_form(self, response, solution, referer, callback):
        return FormRequest(
            url=self.CAPTCHA_URL.format(referer=urllib.quote_plus(referer)),
            formdata={
                "t": solution,
                "cookieEnabled": 'true',
                "why": "8"
            },
            headers={
                'Referer': referer,
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://www.newegg.com'
            },
            callback=callback,
            meta=response.meta
        )