# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import re
import string
import urllib

import traceback

from scrapy import Request, FormRequest
from HTMLParser import HTMLParser
from scrapy.log import INFO, WARNING
from scrapy.conf import settings

from product_ranking.items import (BuyerReviews, SiteProductItem, Price)
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.utils import is_empty


class NeweggcaProductsSpider(BaseProductsSpider):
    name = 'neweggca_products'
    allowed_domains = ["www.newegg.ca", "newegg.ca"]

    SEARCH_URL = "https://www.newegg.ca/Product/ProductList.aspx?Submit=ENE&DEPA=0&Order=BESTMATCH&Description={search_term}&N=-1&isNodeId=1"

    REVIEW_URL = "https://www.newegg.ca/Common/Ajax/ProductReview2016.aspx?" \
                 "action=Biz.Product.ProductReview.switchReviewTabCallBack&" \
                 "callback=Biz.Product.ProductReview.switchReviewTabCallBack&&" \
                 "Item={item_id}&" \
                 "review=0&SummaryType=0&Pagesize=25&" \
                 "PurchaseMark=false&SelectedRating=-1&" \
                 "VideoOnlyMark=false&" \
                 "VendorMark=false&" \
                 "IsFeedbackTab=true&" \
                 "ItemGroupId={group_id}"

    PAGE_URL = "https://www.newegg.ca/Product/ProductList.aspx?" \
               "Submit=ENE&N=-1&" \
               "IsNodeId=1&" \
               "Description={search_term}&" \
               "page={page_num}&" \
               "bop=And&" \
               "PageSize=36&" \
               "order=BESTMATCH"

    CATEGORY_SEARCH_URL = "https://www.newegg.com/Product/ProductList.aspx" \
                          "?Submit=StoreIM&IsNodeId=1&bop=And&Depa=3" \
                          "&Category={category_id}&Page={page_num}&PageSize=36&order=BESTMATCH"

    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/57.0.2987.110 Safari/537.36"}

    CAPTCHA_URL = 'https://www.newegg.ca/Common/CommonReCaptchaValidate.aspx?referer={referer}&why=8'

    def __init__(self, *args, **kwargs):
        super(NeweggcaProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['USE_PROXIES'] = True
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.middlewares.twocaptcha.TwoCaptchaMiddleware'] = 500
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
        settings.overrides['CAPTCHA_SOLVER'] = 'product_ranking.middlewares.captcha.solvers.recaptcha.RecaptchaSolver'
        self.current_page = 1

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for request in super(NeweggcaProductsSpider, self).start_requests():
            request = request.replace(dont_filter=True)
            if not request.meta.get('product'):
                request = request.replace(callback=self._parse_total)
            yield request

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_CA'

        # Parse title
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        out_of_stock = self._parse_out_of_stock(response)
        product['is_out_of_stock'] = out_of_stock

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse reseller id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse buyer reviews
        item_id = response.xpath('//input[@id="hiddenItemNumber"]/@value').extract()

        group_id = response.xpath('//input[@id="hiddenItemGroupId"]/@value').extract()

        if item_id and group_id:
            return Request(self.REVIEW_URL.format(item_id=item_id[0], group_id=group_id[0]),
                           dont_filter=True,
                           meta=response.meta,
                           callback=self._parse_buyer_reviews,
                           headers=self.HEADERS)

        return product

    @staticmethod
    def _parse_brand(response):
        brand = is_empty(response.xpath('//div[@class="objOption"]/a/@title').extract())
        return brand

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//span[@itemprop="name"]/text()').extract())
        return HTMLParser().unescape(title)

    @staticmethod
    def _parse_categories(response):
        categories_sel = response.xpath('//div[contains(@id, "Breadcrumb")]'
                                        '/dl/dd/a/text()').extract()
        categories = [i.strip() for i in categories_sel]
        return categories

    def _parse_price(self, response):
        price = is_empty(response.xpath('//meta[@itemprop="price"]/@content').re(FLOATING_POINT_RGEX))
        currency = is_empty(response.xpath('//meta[@itemprop="priceCurrency"]/@content').extract())
        return Price(price=float(price), priceCurrency=currency) if price else 0

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//span[@class="mainSlide"]/@imgzoompic').re('//(.*)')
        return image_url[0] if image_url else None

    @staticmethod
    def _parse_description(response):
        description = ''
        description_elements = response.xpath('//ul[@class="itemColumn"]/li/text()').extract()
        for desc in description_elements:
            description += desc.strip()
        return description

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        reviews_data = response.body.decode('utf-8')
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            if "reviewCount" not in reviews_data:
                product['buyer_reviews'] = zero_reviews_value
            else:
                rating_by_star = {}

                review_count = re.search('(\d+)', reviews_data.split('reviewCount')[1].split('span')[0], re.DOTALL)
                if review_count:
                    review_count = review_count.group(1)
                else:
                    review_count = 0
                sum = 0

                for i in range(1, 6):
                    rating_by_star['{star}'.format(star=i)] = re.search('(\d+)', reviews_data.split(
                        'reviewNumber{star}'.format(star=i))[1].split('span')[0], re.DOTALL).group(1)
                    sum += i * int(
                        re.search('(\d+)', reviews_data.split('reviewNumber{star}'.format(star=i))[1].split('span')[0],
                                  re.DOTALL).group(1))

                average_rating = round(sum / float(review_count), 1)
                buyer_reviews = {
                    'num_of_reviews': review_count,
                    'average_rating': round(float(average_rating), 1) if average_rating else 0,
                    'rating_by_star': rating_by_star
                }
                product['buyer_reviews'] = buyer_reviews

        except:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            return BuyerReviews(**zero_reviews_value)

        return product

    @staticmethod
    def _parse_out_of_stock(response):
        availability = is_empty(response.xpath('//span[@id="landingpage-stock"]'
                                               '/span/text()').extract())
        return bool(availability == "In stock.")

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = response.xpath('//input[@id="persMainItemNumber"]/@value').extract()
        return reseller_id[0] if reseller_id else None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath('//span[@class="list-tool-pagination-text"][1]/strong/text()').extract()
        return int(totals[1]) if totals else None

    def _parse_total(self, response):
        totals = response.xpath('//span[@class="list-tool-pagination-text"][1]'
                                '/strong/text()').extract()
        if totals:
            return self.parse(response)
        else:
            url = is_empty(response.xpath('//a[@class="link-more"]/@href').extract())
            if not url:
                self.log("Invalid URL".format(url=response.url), INFO)
                return None
            st = response.meta['search_term']
            return Request(
                self.url_formatter.format(
                    url,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                meta={'search_term': st, 'remaining': self.quantity},
                dont_filter=True
            )

    def _scrape_results_per_page(self, response):
        item_count = is_empty(response.xpath('//select[@id="select_top"]'
                                             '/option[@selected="selected"]/@value').extract())
        return int(item_count) if item_count else None

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath('//div[@class="item-info"]'
                               '/a[@class="item-title"]/@href').extract()

        if items:
            for item in items:
                res_item = SiteProductItem()
                yield item, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        next_link = response.xpath('//link[@rel="next"]/@href').extract()
        self.current_page += 1
        if next_link:
            return next_link[0]
        elif 'Category' in response.url:
            category_id = re.findall(r"Category:'(.*?)'", response.body)
            if not category_id:
                return None
            return self.CATEGORY_SEARCH_URL.format(category_id=category_id[0], page_num=self.current_page)
        else:
            st = response.meta['search_term']
            return self.PAGE_URL.format(search_term=st, page_num=self.current_page)

    @staticmethod
    def get_captcha_key(response):
        captcha_key = response.xpath('//div[@id="g-recaptcha"]/@data-sitekey').extract()
        if captcha_key:
            return captcha_key[0]

    @staticmethod
    def is_captcha_page(response):
        return all(
            [
                response.xpath('//p[contains(., "Of course you\'re not, just assure us below.")]'),
                response.url.startswith('https://www.newegg.ca/Common/CommonReCaptchaValidate.aspx')
            ]
        )

    def get_captcha_form(self, response, solution, referer, callback):
        return FormRequest(
            url=self.CAPTCHA_URL.format(referer=urllib.quote_plus(referer)),
            formdata={
                "reCAPTCHAresponse": solution,
                "cookieEnabled": 'true',
                "why": "8"
            },
            headers={
                'Referer': referer,
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://www.newegg.ca'
            },
            callback=callback,
            meta=response.meta
        )