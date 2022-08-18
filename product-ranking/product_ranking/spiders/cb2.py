import json
import urlparse
import traceback
import re
import os
import urllib
import requests
from time import sleep

from scrapy import Request
from scrapy.http import FormRequest
from scrapy.log import WARNING
from scrapy.conf import settings

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty, SharedCookies
from product_ranking.validation import BaseValidator


class Cb2ProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'cb2_products'
    allowed_domains = ["www.cb2.com", "2captcha.com", "google.com"]

    SEARCH_URL = "https://www.cb2.com/search?query={search_term}"
    REVIEWS_URL = "https://api.bazaarvoice.com/data/reviews.json?apiversion=5.4&passkey=m599ivlm5y69fsznu8h376sxj&" \
                  "Filter=ProductId:{product_id}&Sort=SubmissionTime:desc&Limit=10&" \
                  "Include=authors,products&Stats=Reviews"
    VARIANTS_URL = "https://www.cb2.com/Browse/SpecialOrder/GetConfigurationOptions"

    SOLVE_RECAPTCHA_URL = "http://2captcha.com/in.php"
    GET_SOLVED_RECAPTCHA_URL = "http://2captcha.com/res.php?key={}&action=get&id={}"
    SUBMIT_CAPTCHA_URL = "https://www.peapod.com/cdn-cgi/l/chk_captcha?id=340cbc7dda0a5996&g-recaptcha-response={}"

    TWOCAPTCHA_API_KEY = settings.get('TWOCAPTCHA_APIKEY')

    TMP_DIR = '/tmp'

    handle_httpstatus_list = [405]

    def __init__(self, disable_shared_cookies=False, *args, **kwargs):
        super(Cb2ProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        self.shared_cookies = SharedCookies('cb2') if not disable_shared_cookies else None

    def start_reqests(self):
        for req in super(Cb2ProductsSpider, self).start_reqests():
            req = req.replace(
                callback=self.check_captcha
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def check_captcha(self, response):
        retry_count = response.meta.get('retry_count', 0)
        if retry_count > 2:
            return
        captcha = response.xpath('//form[@id="distilCaptchaForm"]')
        if captcha:
            self.log('Captcha found, retry: %i' % retry_count)
            return self.get_captcha_page(response)
        else:
            if self.shared_cookies:
                self.shared_cookies.unlock()
            if response.meta.get('product'):
                return self.parse_product(response)
            else:
                return self.parse(response)

    def get_captcha_page(self, response):
        if self.shared_cookies:
            self.shared_cookies.lock()
        meta = response.meta.copy()
        captcha = response.xpath(
            '//form[@id="distilCaptchaForm"]/@action'
        ).extract()
        captcha_url = response.xpath(
            '//form[@id="distilCaptchaForm"]//iframe/@src'
        ).extract()
        remoteip = response.xpath(
            '//input[@name="remoteip"]/@value'
        ).extract()
        if captcha and captcha_url and remoteip:
            meta['solve_url'] = 'https://www.cb2.com' + captcha[0]
            meta['remoteip'] = remoteip[0]
            return Request(
                url=captcha_url[0],
                meta=meta,
                dont_filter=True,
                callback=self.get_captcha_image
            )

    def get_captcha_image(self, response):
        img = response.xpath('//img/@src').extract()
        chalange_fileld = response.xpath(
            '//input[@id="recaptcha_challenge_field"]/@value'
        ).extract()
        if img and chalange_fileld:
            img_url = 'https://www.google.com/recaptcha/api/' + img[0]
            img_file = os.path.join(self.TMP_DIR, '%s.jpeg' % img[0][-6:])
            urllib.urlretrieve(img_url, img_file)
            data = {
                'key':self.TWOCAPTCHA_API_KEY,
            }
            files = {
                'file':open(img_file, 'rb')
            }
            r = requests.post(self.SOLVE_RECAPTCHA_URL, data=data, files=files)
            if r.text.split('|')[0] == 'OK':
                meta = response.meta.copy()
                meta['captcha_id'] = r.text.split('|')[1]
                meta['chalange_fileld'] = chalange_fileld[0]
                meta['captcha_file'] = img_file
                meta['captcha_url'] = response.url
                self.log('2captcha ID: %s' % meta['captcha_id'])
                sleep(5)
                return Request(
                    url=self.GET_SOLVED_RECAPTCHA_URL.format(
                        self.TWOCAPTCHA_API_KEY,
                        meta['captcha_id']
                    ),
                    meta=meta,
                    dont_filter=True,
                    callback=self.get_captcha_solution
                )

    def get_captcha_solution(self, response):
        meta = response.meta.copy()
        if os.path.isfile(meta['captcha_file']):
            os.remove(meta['captcha_file'])
        answer = response.body.split('|')
        if answer:
            if answer[0] == 'OK':
                data = {
                    'recaptcha_challenge_field':meta['chalange_fileld'],
                    'recaptcha_response_field':answer[1],
                    'submit':'I\'m a human'
                }
                return FormRequest(
                    url=meta['captcha_url'],
                    formdata=data,
                    meta=meta,
                    dont_filter=True,
                    callback=self.send_captcha_solution
                )
            elif answer[0] == 'CAPCHA_NOT_READY':
                sleep(5)
                return Request(
                    url=self.GET_SOLVED_RECAPTCHA_URL.format(
                        self.TWOCAPTCHA_API_KEY,
                        response.meta['captcha_id']
                    ),
                    callback=self.get_captcha_solution,
                    meta=meta,
                    dont_filter=True
                )
            else:
                self.log('Received ERROR from 2captcha: %s' % response.body)

    def send_captcha_solution(self, response):
        meta = response.meta.copy()
        retry_count = response.meta.get('retry_count', 0)
        meta['retry_count'] = retry_count + 1
        recaptcha_key = response.xpath('//textarea/text()').extract()
        if recaptcha_key:
            data = {
                'remoteip':meta['remoteip'],
                'recaptcha_challenge_field':recaptcha_key[0],
                'recaptcha_response_field':'manual_challenge',
            }
            return FormRequest(
                url=response.meta['solve_url'],
                formdata=data,
                callback=self.check_captcha,
                meta=meta,
                dont_filter=True
            )

    def parse(self, response):
        # if there is category page instead of search results page
        # then scrape 'view all' url for that category
        view_all_url = is_empty(
            response.xpath(
                '//a[contains(@class, "categoryPageLink")'
                'and contains(., "view all")]/@href'
            ).extract()
        )
        if not self._parse_links(response) and view_all_url:
            meta = response.meta.copy()
            return Request(
                urlparse.urljoin(response.url, view_all_url),
                meta=meta,
                callback=self.check_captcha
            )

        return super(Cb2ProductsSpider, self).parse(response)

    def parse_product(self, response):
        product = response.meta['product']
        reqs = []
        try:
            data = json.loads(
                response.xpath(
                    "//body/script[@type='application/ld+json'][1]/text()"
                ).extract()[0]
            )
        except:
            if response.meta.get('captcha_check', True):
                response.meta['captcha_check'] = False
                return self.check_captcha(response)
            self.log('JSON not found or invalid JSON: {}'
                     .format(traceback.format_exc()))
            product['not_found'] = True
            return product

        title = data.get('name')
        cond_set_value(product, 'title', title)

        reseller_id = self.parse_resellerId(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        sku = data.get('sku')
        cond_set_value(product, 'sku', sku)

        stock_status = is_empty(
            response.xpath(
                '//meta[@property="og:availability"]/@content'
            ).extract(), ''
        )
        cond_set_value(product, 'is_out_of_stock', 'OutOfStock' in stock_status)

        image_url = data.get('image')
        if image_url:
            image_url += '?hei=2000&wid=2000'
            image_url = urlparse.urljoin(response.url, image_url)
            cond_set_value(product, 'image_url', image_url)

        categories = response.xpath('//*[contains(@id, "_lnkBreadcrumb")]/text()').extract()
        if categories:
            cond_set_value(product, 'categories', categories[1:])
            cond_set_value(product, 'department', categories[-1])

        desc = ''.join(response.xpath(
            "//p[@class='productDescription']//text()").extract()).strip()
        cond_set_value(product, 'description', desc if desc else None)

        price = None

        base_price = data.get('offers', {}).get('price')
        min_price = data.get('offers', {}).get('lowPrice')
        max_price = data.get('offers', {}).get('highPrice')
        currency = data.get('offers', {}).get('priceCurrency', 'USD')
        if base_price:
            price = base_price
        elif min_price:
            price = min_price

        cond_set_value(product, 'price', Price(currency, price))

        product['locale'] = "en-US"

        product_review_id = re.search('Reviews.init(.*?),', response.body)

        if product_review_id:
            meta = {"product": product}
            reqs.append(Request(
                url=self.REVIEWS_URL.format(product_id=product_review_id.group(1).replace('(', '').replace("'", "")),
                callback=self.parse_buyer_reviews,
                dont_filter=True,
                meta=meta,
            ))

        if sku:
            has_variants = response.xpath('//a[@data-choice-attributes]')
            if has_variants and self.scrape_variants_with_extra_requests:
                reqs.append(Request(
                    url=self.VARIANTS_URL,
                    callback=self.parse_variants,
                    method='POST',
                    body='{"sku": %s}' % sku,
                    meta=meta,
                    headers={'Content-Type': 'application/json'},
                ))

        if reqs:
            return self.send_next_request(reqs)

        return product

    def send_next_request(self, reqs):
        req = reqs.pop(0)
        if reqs:
            req.meta["reqs"] = reqs

        return req

    def parse_resellerId(self, response):
        product_url = response.meta.get("product").get('url', '')
        if product_url:
            reseller_id = product_url.split('/')[-1]
            return reseller_id

    def parse_variants(self, response):
        product = response.meta.get("product")
        reqs = response.meta.get('reqs')
        try:
            options = json.loads(response.body_as_unicode())['Options'][0]['OptionChoices']
        except:
            options = []

        variants = []
        for option in options:
            variants.append({
                'properties': {
                    'name': option.get('Name'),
                },
                'in_stock': option.get('IsStock'),
                'image': option.get('ZoomImagePath')
            })

        cond_set_value(product, 'variants', variants)

        if reqs:
            return self.send_next_request(reqs)

        return product

    def parse_buyer_reviews(self, response):
        reqs = response.meta.get('reqs')
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            product = response.meta['product']

            data = json.loads(response.body_as_unicode())

            rew_num = data["TotalResults"]

            if rew_num:
                results = data["Includes"]["Products"]
                result_index = list(data["Includes"]["Products"])[0]
                results = results[result_index]

                data = results["ReviewStatistics"]

                average_rating = data["AverageOverallRating"]

                rating_by_star = {}
                stars = data.get("RatingDistribution", [])

                if stars:
                    for i in range(0, 5):
                        ratingFound = False

                        for star in stars:
                            if star['RatingValue'] == i + 1:
                                rating_by_star[star['RatingValue']] = star['Count']
                                ratingFound = True
                                break

                        if not ratingFound:
                            rating_by_star[i+1] = 0

                buyer_reviews = {
                    'num_of_reviews': rew_num,
                    'average_rating': round(float(average_rating), 1) if average_rating else 0,
                    'rating_by_star': rating_by_star
                }
                product['buyer_reviews'] = buyer_reviews
            else:
                product['buyer_reviews'] = zero_reviews_value
        except Exception as e:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            return BuyerReviews(**zero_reviews_value)

        if reqs:
            return self.send_next_request(reqs)

        return product

    def _parse_links(self, response):
        return response.xpath(
            '//a[contains(@class, "product-miniset-title")]/@href').extract()

    def _scrape_product_links(self, response):
        urls = self._parse_links(response)
        for url in [urlparse.urljoin(response.url, x) for x in urls]:
            yield url, SiteProductItem()

    def _scrape_total_matches(self, response):
        return len(self._parse_links(response))

    def _scrape_results_per_page(self, response):
        # cb2.com does not support pagination on the search page.
        return None

    def _scrape_next_results_page_link(self, response):
        # cb2.com does not support pagination on the search page.
        return None
