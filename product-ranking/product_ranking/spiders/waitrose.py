from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
from urlparse import urljoin

from scrapy import Request
from scrapy.log import ERROR, WARNING
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty


class WaitroseProductsSpider(BaseProductsSpider):
    name = 'waitrose_products'
    allowed_domains = ["www.waitrose.com", "waitrose.com"]

    SEARCH_URL = 'https://www.waitrose.com/api/content-prod/v2/cms/publish/productcontent/search/-1?clientType=WEB_APP'
    PRODUCT_URL = "https://www.waitrose.com/api/custsearch-prod/v3/search/-1/{product_id}?orderId=0"
    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?passkey=ixky61huptwfdsu0v9cclqjuj&apiversion=5.5" \
                 "&displaycode=17263-en_gb&resource.q0=products&filter.q0=id:eq:{product_id}" \
                 "&stats.q0=reviews&filteredstats.q0=reviews&filter_reviews.q0=contentlocale:eq:en_AU,en_BH,en_GB,en_HK" \
                 "&filter_reviewcomments.q0=contentlocale:eq:en_AU,en_BH,en_GB,en_HK&resource.q1=reviews" \
                 "&filter.q1=isratingsonly:eq:false&filter.q1=productid:eq:{product_id}" \
                 "&filter.q1=contentlocale:eq:en_AU,en_BH,en_GB,en_HK&sort.q1=isfeatured:desc&stats.q1=reviews"

    ITEM_URL = 'https://www.waitrose.com/ecom/products/{slug}/{product_id}'

    token_address = "https://www.waitrose.com/api/authentication-prod/v2/authentication/token"

    request_headers = {
        "Host": "www.waitrose.com",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Authorization": "",
        "Connection": "keep-alive"
    }

    request_body = {
        "customerSearchRequest": {
            "queryParams": {
                "searchTerm": "",
                "sortBy": "RELEVANCE",
                "searchTags": [],
                "filterTags": [],
                "size": 48,
                "orderId": "0",
                "start": 0
            }
        }
    }

    results_per_page = 48

    def __init__(self, *args, **kwargs):
        super(WaitroseProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args, **kwargs)

        self.detect_ads = True if kwargs.get('detect_ads') in (1, '1', 'true', 'True', True) else False

    def start_requests(self):
        yield Request(self.token_address, callback=self._start_requests)

    def _start_requests(self, response):
        try:
            body = json.loads(response.body)
        except:
            self.log("Got non-API response, check token address", WARNING)
        else:
            token = body.get('loginResult', {}).get('jwtString')
            if token:
                self.request_headers['Authorization'] = token
                for req in super(WaitroseProductsSpider, self).start_requests():
                    if self.product_url:
                        req = req.replace(callback=self._get_product_id_from_redirect)
                        yield req
                    else:
                        self.request_body['customerSearchRequest']['queryParams']['searchTerm'] = \
                            req.meta['search_term']
                        req.meta['offset'] = 0
                        req = req.replace(
                            headers=self.request_headers,
                            method='POST',
                            body=json.dumps(self.request_body),
                            callback=self.parse,
                            dont_filter=True)
                        if self.detect_ads:
                            req.meta['req'] = req
                            req = req.replace(callback=self._parse_ads, dont_filter=True)
                        yield req

            else:
                self.log("There is no security token in response, failed to start request(s)", ERROR)

    def _parse_ads(self, response):
        ads = []
        try:
            body = json.loads(response.body_as_unicode())
        except:
            self.log("Error while extracting ads links: {}".format(traceback.format_exc()))
        else:
            ad_items = [item for item in body.get('componentsAndProducts', []) if 'aemComponent' in item]

            for item in ad_items:
                url = item.get('aemComponent', {}).get('textArea', {}).get('link', {}).get('url')
                image_url = item.get('aemComponent', {}).get('image', {}).get('landscapeImage', {}).get('src')
                image_url = urljoin('https://ecom.waitrose.com', image_url)
                if url not in [x.get('ad_url') for x in ads]:
                    ads.append({'ad_image': image_url, 'ad_url': url})
        finally:
            response.meta['ads'] = ads
            response.meta['filled_ads'] = []
            return self._parse_ads_products(response)

    def _parse_ads_products(self, response):
        if response.meta['ads']:
            ad = response.meta['ads'].pop()
            response.meta['current_ad'] = ad
            yield Request(ad['ad_url'], meta=response.meta, callback=self._parse_destination_page, dont_filter=True)
        else:
            response.meta['ads'] = response.meta['filled_ads']
            req = response.meta['req']
            req = req.replace(meta=response.meta, callback=self.parse, dont_filter=True)
            yield req

    def _parse_destination_page(self, response):
        products = response.xpath('//div[@class="m-product-details-container"]//a[@class="m-product-open-details"]')
        ad_dest_products = []
        for product in products:
            url = is_empty(product.xpath('@href').extract())
            if url:
                url = urljoin(response.url, url)
            name = is_empty(product.xpath('./text()').extract())
            ad_dest_products.append({"url": url, "name": name})

        response.meta['current_ad'].update({
            "ad_dest_products": ad_dest_products})

        response.meta['filled_ads'].append(response.meta['current_ad'])

        return self._parse_ads_products(response)

    def _get_product_id_from_redirect(self, response):
        try:
            if 'DisplayProductFlyout' in response.url:
                details = response.xpath('//div[contains(@class, "two-col product-detail")]')
                prod_num = details.xpath('@partnumber').extract()[0]
                parent_cat = details.xpath('@data-parentcatentryid').extract()[0]
                link_id = re.search(r'(?<=productId=).+', response.url).group(0)
                product_id = "{}-{}-{}".format(prod_num, parent_cat, link_id)
            else:
                product_id = response.url.split('/')[-1]

            return Request(url=self.PRODUCT_URL.format(product_id=product_id),
                           headers=self.request_headers,
                           callback=self.parse_product,
                           meta=response.meta
                           )
        except:
            self.log("Failed to get product ID from response, stopped {}".format(traceback.format_exc()))
            product = response.meta.get('product') or SiteProductItem()
            product.update({'not_found': True})
            return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta.get('product')
        if self.detect_ads:
            product['ads'] = response.meta.get('ads')

        data = self._extract_main_json(response)

        cond_set_value(product, 'is_out_of_stock', bool(data.get('conflicts')))

        reseller_id = data.get('id')
        cond_set_value(product, 'reseller_id', reseller_id)

        title = data.get('name')
        cond_set_value(product, 'title', title)

        if title and reseller_id:
            slug = re.sub(r' +', '-', title)
            slug = re.sub('[^0-9a-zA-Z\'-]+', '', slug)
            product_url = self.ITEM_URL.format(slug=slug, product_id=reseller_id)
            product['url'] = product_url

        brand = data.get('brand')
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        image_url = data.get('thumbnail', '')
        if image_url.startswith('//'):
            image_url = 'http:' + image_url
        cond_set_value(product, 'image_url', image_url)

        price_per_volume_measure = self._parse_price_per_volum_measure(data)
        if price_per_volume_measure:
            price_per_volume = re.sub('[^0-9.]', "", price_per_volume_measure)
            if price_per_volume:
                price_per_volume = round(float(price_per_volume), 2)
            price_per_volume_measure = price_per_volume_measure.split("/")
            cond_set_value(product, 'price_per_volume', price_per_volume)
            cond_set_value(product, 'volume_measure', price_per_volume_measure[-1])

        categories = data.get('categories', [])
        categories = [category.get('name') for category in categories if category.get('name')]
        cond_set_value(product, 'categories', categories)

        promotion_block = self._parse_promotion_block(data)

        save_amount = self._parse_save_amount(promotion_block, data)
        product['save_amount'] = save_amount

        buy_for = self._parse_buy_for(promotion_block)
        product['buy_for'] = buy_for

        save_percent = self._parse_save_percent(promotion_block)
        product['save_percent'] = save_percent

        if any([save_amount, buy_for, save_percent]):
            product['promotions'] = True
        else:
            product['promotions'] = False

        price = self._parse_price(data.get('displayPrice'))
        product['price'] = Price(price=price, priceCurrency='GBP')

        product['locale'] = "en_UK"

        if reseller_id:
            review_id = reseller_id.split('-')[0]
            response.meta['marks'] = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            response.meta['product'] = product
            response.meta['product_id'] = review_id

            return Request(
                url=self.REVIEW_URL.format(product_id=review_id),
                dont_filter=True,
                callback=self._parse_buyer_reviews,
                meta=response.meta
            )

        return product

    @staticmethod
    def _parse_promotion_block(data):
        return data.get('promotion', {}).get('promotionDescription')

    @staticmethod
    def _parse_save_amount(promotion_block, data):
        save_amount = None
        if promotion_block and 'save' in promotion_block:
            save_amount = data.get('currentSaleUnitPrice', {}).get('price', {}).get('amount')
        return save_amount

    @staticmethod
    def _parse_price_per_volum_measure(data):
        price_volum_measure_info = data.get('displayPriceQualifier', {})
        return price_volum_measure_info

    @staticmethod
    def _parse_buy_for(promotion_block):
        buy_for = None
        if promotion_block and 'for' in promotion_block:
            buy_for = re.findall('\d+\.?\d*', promotion_block)
        if buy_for:
            buy_for = ', '.join(buy_for)
        return buy_for

    @staticmethod
    def _parse_save_percent(promotion_block):
        save_percent = None
        if promotion_block and '%' in promotion_block:
            save_percent = re.findall('\d+\.?\d*', promotion_block)
        return save_percent[0] if save_percent else None

    def _parse_price(self, raw_price):
        try:
            price = re.search(r'[\d\.\,]+', raw_price)
            price = float(price.group(0).replace(',', ''))
            return price
        except:
            self.log("Error while parsing price: {}".format(traceback.format_exc()))
            return 0.00

    def _parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        meta = response.meta.copy()
        product_id = meta['product_id']
        product = response.meta['product']

        if product_id:
            try:
                json_data = json.loads(response.body, encoding='utf-8')
                product_reviews_info = json_data['BatchedResults']['q0']['Results'][0]
                product_reviews_stats = product_reviews_info.get('ReviewStatistics', None)

                if product_reviews_stats:
                    rating_by_stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                    for rating in product_reviews_stats.get('RatingDistribution', []):
                        rating_value = str(rating.get('RatingValue', ''))
                        if rating_value in rating_by_stars.keys():
                            rating_by_stars[rating_value] = int(rating.get('Count', 0))

                    try:
                        average_rating = float(format(product_reviews_stats.get('AverageOverallRating', .0), '.1f'))
                    except:
                        average_rating = 0.0

                    product['buyer_reviews'] = BuyerReviews(
                        num_of_reviews=int(product_reviews_stats.get('TotalReviewCount', 0)),
                        average_rating=average_rating,
                        rating_by_star=rating_by_stars
                    )

            except Exception as e:
                self.log('Reviews error {}'.format(traceback.format_exc(e)))
        else:
            product['buyer_reviews'] = BuyerReviews(**ZERO_REVIEWS_VALUE)

        return product

    def _scrape_total_matches(self, response):
        try:
            body = json.loads(response.body_as_unicode())
            total = body.get('totalMatches', 0)
            response.meta['total'] = total
            return total
        except:
            self.log("Error while parsing total matches: {}".format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        try:
            body = json.loads(response.body_as_unicode())
        except:
            self.log("Error while extracting product links: {}".format(traceback.format_exc()))
        else:
            items = body.get('componentsAndProducts', [])
            for item in items:
                product_id = item.get('searchProduct', {}).get('id')
                if product_id:
                    yield self.PRODUCT_URL.format(product_id=product_id), SiteProductItem()

    def _extract_main_json(self, response):
        try:
            data = json.loads(response.body)
            data = data.get('products')[0]
        except:
            self.log('Product extracting failed: {}'.format(traceback.format_exc()))
        else:
            return data

    def _scrape_next_results_page_link(self, response):
        if response.meta['offset'] + self.results_per_page < response.meta['total']:
            response.meta['offset'] += self.results_per_page
            body = self.request_body.copy()
            body['customerSearchRequest']['queryParams']['start'] = response.meta['offset']
            return Request(
                url=self.SEARCH_URL,
                method="POST",
                body=json.dumps(body),
                meta=response.meta,
                headers=self.request_headers
            )

    def _get_products(self, response):
        for req in super(WaitroseProductsSpider, self)._get_products(response):
            if isinstance(req, Request):
                req = req.replace(headers=self.request_headers)
            yield req
