# -*- coding: utf-8 -*-#

import re
import json
import string
import urllib
import traceback

from scrapy.conf import settings
from scrapy import Request, FormRequest
from scrapy.log import ERROR, INFO, WARNING

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from spiders_shared_code.wayfair_variants import WayfairVariants
from spiders_shared_code.utils import deep_search


class WayfairProductSpider(BaseProductsSpider):
    name = 'wayfair_products'
    allowed_domains = ["wayfair.com"]

    SEARCH_URL = "https://www.wayfair.com/keyword.php?keyword={search_term}"

    CATEGORY_SEARCH_URL = "https://www.wayfair.com/a/quickbrowse/ajax_load?ajax=1&caid={category_id}&clid=0&maid=0&itemsperpage=48&curpage={current_page}&sortby=114&expand=0&is_in_horizontal_test_pages=false&shouldShowGuidedSellingQuestion=true&showGuidedSellingCard=false"

    CAPTCHA_URL = 'https://www.wayfair.com/v/captcha/show?goto={referer}&px=1'

    INVENTORY_URL = "https://www.wayfair.com/a/inventory/load?_txid={}"

    handle_httpstatus_list = [302, 405, 503]

    def __init__(self, *args, **kwargs):
        self.category_id = None
        super(WayfairProductSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.middlewares.twocaptcha.TwoCaptchaMiddleware'] = 500
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['CAPTCHA_SOLVER'] = 'product_ranking.middlewares.captcha.solvers.recaptcha.RecaptchaSolver'

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for request in super(WayfairProductSpider, self).start_requests():
            request = request.replace(dont_filter=True)
            if not request.meta.get('product'):
                request = request.replace(callback=self._parse_search)
            yield request

    def _parse_search(self, response):
        links = response.xpath('//div[@class="BrowseProductGrid"]'
                               '/div[contains(@class, "Grid")]//a/@href').extract()
        category_id = re.findall(r'"category_id":(\d+)', response.body)
        if links or not category_id:
            return self.parse(response)
        else:
            self.category_id = category_id[0]
            meta = response.meta
            meta['current_page'] = 1
            url = self.CATEGORY_SEARCH_URL.format(category_id=self.category_id, current_page=1)
            return Request(url, meta=meta)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        main_info = self._get_main_product_info(response)

        if main_info:
            product_sku = main_info.get('sku')
            cond_set_value(product, 'reseller_id', product_sku)

            title = main_info.get('name')
            cond_set_value(product, 'title', title, conv=string.strip)

            brand = main_info.get('brand')
            if not brand and title:
                brand = guess_brand_from_first_words(title)
            cond_set_value(product, 'brand', brand)

            price = self._parse_price(main_info)
            cond_set_value(product, 'price', price)

            image_url = main_info.get('image')
            cond_set_value(product, 'image_url', image_url)

            sku = self._parse_sku(response)
            cond_set_value(product, 'sku', sku)

            # get txid
            txid = self._get_txid(response)

            # Parse categories
            categories = self._parse_categories(response)
            cond_set_value(product, 'categories', categories)
            if categories:
                cond_set_value(product, 'department', categories[-1])

            # Parse stock status
            is_out_of_stock = self._parse_stock_status(response)
            cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

            # Parse buyer reviews
            num_of_reviews = main_info.get('aggregateRating', {}).get('reviewCount')
            if num_of_reviews:
                buyer_reviews = self._parse_buyer_reviews(response)
                if buyer_reviews.num_of_reviews == 0:
                    buyer_reviews = self._parse_buyer_reviews_from_json(response)
                cond_set_value(product, 'buyer_reviews', buyer_reviews)
            else:
                cond_set_value(product, 'buyer_reviews', ZERO_REVIEWS_VALUE)

            # Setup variants
            wayfair_variants = WayfairVariants()
            wayfair_variants.setupSC(response)
            meta['variants_obj'] = wayfair_variants
            options_data = self._get_options_data(response, sku)
            data = {
                'product_data': options_data,
                'postal_code': '',
                'event_id': 0,
                'should_calculate_all_kit_items': 'false'
            }
            if options_data:
                meta['dont_redirect'] = True

                return Request(
                    url=self.INVENTORY_URL.format(txid),
                    callback=self._get_variants,
                    errback=self._variants_failed,
                    meta=meta,
                    headers={
                        'content-type': 'application/json; charset=UTF-8',
                        'x-requested-with': 'XMLHttpRequest',
                        'origin': 'https://www.wayfair.com',
                        'accept-encoding': 'gzip, deflate, br',
                        'accept-language': 'en-US,en;q=0.9,ru;q=0.8',
                        'accept': 'application/json, text/javascript, */*; q=0.01',
                    },
                    body=json.dumps(data),
                    method='POST',
                    dont_filter=True
                )
            else:
                return product

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath("//*[@name='sku']/@value").extract()
        return sku[0] if sku else None

    @staticmethod
    def _get_txid(response):
        txid = re.search('TRANSACTION_ID":"([^"]*)"', response.body)
        if txid:
            return txid.group(1)

    @staticmethod
    def _get_options_data(resposne, sku):
        variants_json = None
        js = re.findall(
            'wf.extend\(({"wf":{"apnData.*})\)',
            resposne.body
        )
        for elem in js:
            try:
                app_data = json.loads(elem).get('wf').get('reactData')
                for key in app_data.keys():
                    if app_data[key]['bootstrap_data'].get('options'):
                        variants_json = app_data[key]['bootstrap_data']['options']['standardOptions']
                break
            except:
                continue
        if variants_json:
            return [
                {'sku': str(sku), 'option_ids': [int(p['option_id'])]}
                for p in variants_json[0].get('options', [])
            ]

    def _get_variants(self, response):
        product =response.meta['product']
        wayfair_variants = response.meta['variants_obj']
        variants = wayfair_variants._variants(json.loads(response.body))
        if variants:
            cond_set_value(product, 'variants', variants)

        return product

    def _variants_failed(self, response):
        return response.request.meta['product']

    def _get_main_product_info(self, response):
        raw_info = response.xpath('//script[@type="application/ld+json"]/text()').extract()
        try:
            raw_info = json.loads(raw_info[0])
            return raw_info
        except:
            self.log("Failed to load main product info", ERROR)

    def _parse_categories(self, response):
        """
        Parse product categories
        """
        categories = response.xpath(
            "//*[contains(@class, 'Breadcrumbs-listItem')]/a//text()"
        ).extract()
        if categories:
            categories = categories[:-1]
        return categories

    def _parse_stock_status(self, response):
        """
        Parse product stock status
        """
        out_of_stock = re.search('"is_out_of_stock":([a-z]+)', response.body)

        if out_of_stock:
            return 'true' in out_of_stock.group(1)
        else:
            self.log('Unable to parse stock status on {url}'.format(
                url=response.url
            ), WARNING)
            return None

    def _parse_buyer_reviews(self, response):
        "[0, 0.0, {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}]"
        try:
            average_rating = response.xpath('//div[@class="ProductDetailReviews-header"]'
                                            '//p[@class="ReviewStars-reviews"]/text()').re('\d\.?\d*')
            if average_rating:
                average_rating = float(average_rating[0])
            reviews = [int(i) for i in response.xpath('//div[@class="ProductReviewsHistogram-count"]/text()').re('\d+')]
            if reviews:
                reviews = reviews[:5]
            rating_by_star = {5-i: review for (i, review) in enumerate(reviews)}
            review_count = sum(reviews)
            buyer_reviews = {
                'average_rating': average_rating,
                'num_of_reviews': review_count,
                'rating_by_star': rating_by_star
            }
            buyer_reviews = BuyerReviews(**buyer_reviews)
        except Exception as exc:
            self.log('Unable to parse star rating from {url}: {exc}'.format(
                url=response.url,
                exc=exc
            ), ERROR)
            buyer_reviews = ZERO_REVIEWS_VALUE

        return buyer_reviews

    def _parse_buyer_reviews_from_json(self, response):
        product_data = None
        reviews = None

        datas = re.findall(r'wf\.extend\((.*)\);', response.body)
        for data in datas:
            if 'customerReviews' in data:
                product_data = data
                break

        try:
            product_json = json.loads(product_data)
            reviews = deep_search('customerReviews', product_json)[0]
        except:
            self.log('Invalid Product Json {}'.format(traceback.format_exc()))

        if not reviews:
            return ZERO_REVIEWS_VALUE

        review_count = reviews.get('ratingCount', 0)
        average_rating = reviews.get('averageRatingValue', 0)
        ratings = reviews.get('histogramStats', [])
        rating_by_star = {rating.get('rating'): rating.get('count') for rating in ratings}

        buyer_reviews = {
            'average_rating': average_rating,
            'num_of_reviews': review_count,
            'rating_by_star': rating_by_star
        }
        buyer_reviews = BuyerReviews(**buyer_reviews)

        return buyer_reviews

    def _parse_price(self, info):
        price = info.get('offers', {}).get('price')
        currency = info.get('offers', {}).get('priceCurrency')
        if not currency:
            currency = 'USD'
        if price:
            return Price(price=price, priceCurrency=currency)
        else:
            self.log('Failed to parse price', WARNING)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        if self.category_id:
            try:
                data = json.loads(response.body)
                total_matches = data.get('number_results')
                return int(total_matches)
            except:
                self.log('Error parsing category products: {}'.format(traceback.format_exc()))
        else:
            total_matches = re.search('product_count":(\d+)', response.body)
            return int(total_matches.group(1)) if total_matches else 0

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        links = []
        if self.category_id:
            try:
                data = json.loads(response.body)
                data = data.get('productGrid').get('product_block_collection', [])
                links = [link.get('product_url') for link in data]
            except:
                self.log('Error parsing category products: {}'.format(traceback.format_exc()))
        else:
            links = response.xpath('//div[@class="BrowseProductGrid"]'
                                   '/div[contains(@class, "Grid")]//a/@href').extract()

        if not links:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page')
        if not current_page:
            current_page = 1
        if self.category_id:
            url = None
            try:
                data = json.loads(response.body)
                total_pages = data.get('paginationBar').get('total_pages')
                if not total_pages:
                    return
                if int(total_pages) <= current_page:
                    return
                current_page += 1
                url = self.CATEGORY_SEARCH_URL.format(category_id=self.category_id, current_page=current_page)
            except:
                self.log('Error parsing category products: {}'.format(traceback.format_exc()))
        else:
            url = is_empty(response.xpath(
                '//a[contains(@class, "js-next-page")]/@href').extract())
            current_page += 1

        if url:
            meta['current_page'] = current_page
            meta['url'] = url
            return Request(url,
                           meta=meta)

    @staticmethod
    def get_captcha_key(response):
        captcha_key = response.xpath('//div[@class="g-recaptcha"]/@data-sitekey').extract()
        if captcha_key:
            return captcha_key[0]

    @staticmethod
    def is_captcha_page(response):
        captcha_page = response.url.startswith('https://www.wayfair.com/v/captcha/')
        return bool(captcha_page)

    def get_captcha_form(self, response, solution, referer, callback):
        return FormRequest(
            url=self.CAPTCHA_URL.format(referer=urllib.quote_plus(referer)),
            formdata={
                "g-recaptcha-response": solution,
                "goto": referer,
                'px': '1'
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded',
                     'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                     'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) '
                                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                                   'Chrome/63.0.3239.132 Safari/537.36'},
            method='POST',
            callback=callback,
            meta=response.meta
        )

