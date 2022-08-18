# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import json
import urllib
import traceback

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.validators.asda_validator import AsdaValidatorSettings

from scrapy.conf import settings
from scrapy.http import Request
from scrapy.log import WARNING

is_empty = lambda x, y=None: x[0] if x else y


class AsdaProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'asda_products'
    allowed_domains = ["asda.com"]
    start_urls = []

    settings = AsdaValidatorSettings

    SEARCH_URL = "https://groceries.asda.com/api/items/search?pagenum={pagenum}&" \
                 "productperpage={prods_per_page}&keyword={search_term}&contentid" \
                 "=New_IM_Search_WithResults_promo_1&htmlassociationtype=0&listType" \
                 "=12&sortby=relevance+desc&cacheable=true&fromgi=gi&requestorigin=gi"

    PRODUCT_LINK = "https://groceries.asda.com/product/{shelfName}/{name}/{pId}"

    API_URL = "https://groceries.asda.com/api/items/view?itemid={id}&responsegroup" \
              "=extended&cacheable=true&shipdate=currentDate&requestorigin=gi"

    REVIEW_URL = "https://groceries.asda.com/review/reviews.json?" \
                 "Filter=ProductId:%s&Sort=SubmissionTime:desc&" \
                 "apiversion=5.4&passkey=92ffdz3h647mtzgbmu5vedbq&limit=100"

    PRODUCT_URL = "https://groceries.asda.com/api/items/view?itemid={product_id}&responsegroup=extended" \
                  "&cacheable=true&shipdate=currentDate&requestorigin=gi"

    ADS_URL = "https://groceries.asda.com/cmscontent/json/pages/browse/search?Endeca_user_segments=" \
              "anonymous%7Cstore_4565%7Cwapp%7Cvp_XXL%7CZero_Order_Customers%7CDelivery_Pass_Older_" \
              "Than_12_Months%7Cdp-false%7C1007%7C1019%7C1020%7C1023%7C1024%7C1027%7C1038%7C1041%7C" \
              "1042%7C1043%7C1047%7C1053%7C1055%7C1057%7C1059%7C1067%7C1070%7C1082%7C1087%7C1097%7C" \
              "1098%7C1099%7C1100%7C1102%7C1105%7C1107%7C1109%7C1110%7C1111%7C1112%7C1116%7C1117%7C" \
              "1119&storeId=4565&shipDate=1518498000000&Ntt={search_term}&requestorigin=gi&_=1518509667121"

    def __init__(self, *args, **kwargs):
        super(AsdaProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(pagenum=1, prods_per_page=60),
            *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)' \
                          'Chrome/66.0.3359.139 Safari/537.36'
        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

    def start_requests(self):
        for st in self.searchterms:
            request = Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                meta={'search_term': st, 'remaining': self.quantity},
            )

            if self.detect_ads:
                request = request.replace(url=self.ADS_URL.format(search_term=urllib.quote_plus(st.encode('utf-8'))),
                                          callback=self._get_ads_product)

            yield request

        if self.product_url:
            product_id = is_empty(re.findall("product/.*/(\d+)", self.product_url))
            url = self.PRODUCT_URL.format(product_id=product_id)

            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod["url"] = self.product_url
            prod["reseller_id"] = product_id
            yield Request(url,
                          self._parse_single_product,
                          meta={'product': prod})

    def _get_ads_product(self, response):
        meta = response.meta.copy()
        image_urls = []
        ads_urls = []
        ids = []
        try:
            list = json.loads(response.body_as_unicode())
            list = list.get('contents')[0].get('mainContent')[1].get('dynamicSlot').get('contents')
            for data in list:
                url = data.get('link').get('queryString')
                id = re.search('(\d+)', url, re.DOTALL)
                if id:
                    id = id.group(1)
                    ids.append(id)
                    url = 'https://groceries.asda.com/cmslisting/content/event?N=' + id
                    ads_urls.append(url)
                    image_urls.append(data.get('mediaURL'))
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

        ads = []
        for i, url in enumerate(ads_urls):
            ad = {
                'ad_url': url,
                'ad_image': image_urls[i],
                'ads_dest_products': []
            }
            ads.append(ad)

        if ids:
            meta['ads_idx'] = 0
            meta['ads'] = ads

            api_url = "https://groceries.asda.com/cmscontent/json/pages/cmslisting/content/event" \
                      "?Endeca_user_segments=anonymous%7Cstore_4565%7Cwapp%7Cvp_XXL%7CZero_Order_" \
                      "Customers%7CDelivery_Pass_Older_Than_12_Months%7Cdp-false%7C1007%7C1019%7C1020" \
                      "%7C1023%7C1024%7C1027%7C1038%7C1041%7C1042%7C1043%7C1047%7C1053%7C1055%7C1057" \
                      "%7C1059%7C1067%7C1070%7C1082%7C1087%7C1097%7C1098%7C1099%7C1100%7C1102%7C1105" \
                      "%7C1107%7C1109%7C1110%7C1111%7C1112%7C1116%7C1117%7C1119&storeId=4565&shipDate=" \
                      "1519603200000&N={id}&No=0&Nrpp=60&requestorigin=gi&_=1519614747234"

            ads_api_url = [api_url.format(id=i) for i in ids]
            meta['ads_api_url'] = ads_api_url

            return Request(
                url=ads_api_url[0],
                meta=meta,
                callback=self._parse_ads_api_links,
                dont_filter=True,
            )
        else:
            return Request(
                url=self.SEARCH_URL.format(search_term=response.meta.get('search_term'),
                                           pagenum=1,
                                           prods_per_page=60),
                meta=response.meta
            )

    def _parse_ads_api_links(self, response):
        meta = response.meta.copy()
        try:
            ads_products_list = json.loads(response.body_as_unicode())
            ads_products_list = ads_products_list.get('contents')[0].get('mainContent')[0].get('records') \
                if ads_products_list.get('contents') else None

            if not ads_products_list:
                self.log('No ads products detected')
                return Request(
                    url=self.SEARCH_URL.format(search_term=response.meta.get('search_term'),
                                               pagenum=1,
                                               prods_per_page=60),
                    meta=response.meta
                )

            array, url = self.generate_url(ads_products_list)
            meta['list'] = array

            return Request(
                url=url,
                meta=meta,
                callback=self._parse_ads_product,
                dont_filter=True,
            )
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

    def generate_url(self, ads_products_list):
        url = "https://groceries.asda.com/api/items/view?itemid="
        list_len = min(30, len(ads_products_list))
        for i in range(list_len):
            sku = ads_products_list[i].get('attributes', {}).get('sku.repositoryId')
            if sku:
                url += sku[0] + '%2C'
        if len(ads_products_list) > 30:
            array = list[30:]
        else:
            array = None
        url = url[:-3] + "&responsegroup=basic&cacheable=true&storeid=4565&shipdate=currentDate&requestorigin=gi"

        return array, url

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_api_url = response.meta.get('ads_api_url')

        products_info = self._get_products_info(response)
        if products_info:
            products = [
                {
                    'url': item['url'],
                    'name': item['name'],
                    'brand': item['brand'],
                    'reseller_id': self._get_reseller_id(item['url'])
                } for item in products_info
            ]

            ads[ads_idx]['ads_dest_products'] += products
        response.meta['ads'] = ads

        list = response.meta.get('list', [])
        ads_idx += 1
        if ads_idx < len(ads_api_url) and not list:
            link = ads_api_url[ads_idx]
            response.meta['ads_idx'] = ads_idx + 1
        elif list:
            array, url = self.generate_url(list)
            response.meta['list'] = array

            return Request(
                url=url,
                meta=response.meta,
                callback=self._parse_ads_product,
                dont_filter=True
            )
        else:
            return Request(
                url=self.SEARCH_URL.format(search_term=response.meta.get('search_term'),
                                           pagenum=1,
                                           prods_per_page=60),
                meta=response.meta
            )

        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_api_links,
            dont_filter=True
        )

    def _get_products_info(self, response):
        items = []
        try:
            content_list = json.loads(response.body_as_unicode())
            content_list = content_list.get('items')
            for content in content_list:
                item = {}
                item['name'] = content.get('name')
                url = 'https://groceries.asda.com/product/' + self.clean_url(content.get('shelfName')) \
                      + '/' + self.clean_url(content.get('name')) + '/' + self.clean_url(content.get('id'))
                item['url'] = url
                item['brand'] = content.get('brandName')
                items.append(item)
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)

        return items

    def clean_url(self, url):
        url = url.replace('&', '').replace('  ', ' ').replace(' ', '-')
        return url.lower()

    def parse_product(self, response):
        product = response.meta['product']

        try:
            data = json.loads(response.body_as_unicode())
            item = data['items'][0]
            if item.get("images", {}).get("largeImage"):
                product["image_url"] = item.get("images").get("largeImage")
            product['upc'] = item['upcNumbers'][0]['upcNumber']
            product['reseller_id'] = item.get('id')
        except Exception as e:
            self.log('Error while parsing product {}'.format(traceback.format_exc(e)))

        product_id = re.findall('itemid=(\d+)', response.url)
        if product_id:
            url = self.REVIEW_URL % product_id[0]
            meta = {'product': product}
            return Request(url=url, meta=meta, callback=self._parse_review)
        return product

    def _parse_review(self, response):
        prod = response.meta['product']
        num, avg, by_star = prod['buyer_reviews']
        try:
            data = json.loads(response.body_as_unicode())
            by_star = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            reviews = data['Results']
            for review in reviews:
                by_star[review['Rating']] += 1
        except:
            self.log('Error while parsing the json data'.format(traceback.format_exc()))

        prod['buyer_reviews'] = BuyerReviews(num, avg, by_star)
        return prod

    def _search_page_error(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            is_error = data.get('statusCode') != '0'
            if is_error:
                self.log("Site reported error code '%s' and reason: %s"
                         % (data.get('statusCode'), data.get('statusMessage')),
                         WARNING)

            return is_error
        except Exception as e:
            self.log('Search Page Error {}'.format(traceback.format_exc(e)))
            raise

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            return int(data['totalResult'])
        except Exception as e:
            self.log('Total Matches error {}'.format(traceback.format_exc(e)))

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        data = json.loads(response.body_as_unicode())
        for item in data['items']:
            prod = SiteProductItem()
            if item.get('weight'):
                prod['title'] = "{} {}".format(item['name'], item.get('weight', ''))
            else:
                prod['title'] = item['name']

            prod['brand'] = item['brandName']

            prod['is_out_of_stock'] = False
            prod['price'] = item['price']
            if prod.get('price', None):
                prod['price'] = Price(
                    price=prod['price'].replace('£', '').replace(
                        ',', '').strip(),
                    priceCurrency='GBP'
                )

            total_stars = int(item.get('totalReviewCount') if isinstance(item.get('totalReviewCount'), int) else 0)
            avg_stars = float(item.get('avgStarRating') if isinstance(item.get('avgStarRating'), float) else .0)
            prod['buyer_reviews'] = BuyerReviews(num_of_reviews=total_stars,
                                                 average_rating=avg_stars,
                                                 rating_by_star={})
            prod['model'] = item['cin']
            image_url = item.get('imageURL')

            if not image_url and "images" in item:
                image_url = item.get('images').get('largeImage')
            prod['image_url'] = image_url

            pId = is_empty(re.findall("itemid=(\d+)", item['productURL']))
            shelfName = item.get('shelfName')
            name = item.get('name')

            if pId and "search_term" in response.meta and shelfName and name:
                shelfName, name = ["-".join(re.split('\W+', x)).lower() for x in [shelfName, name]]
                prod['url'] = self.PRODUCT_LINK.format(shelfName=shelfName, name=name, pId=pId)

            price_volume_info = item.get('pricePerUOM')
            if price_volume_info and '/' in price_volume_info:
                try:
                    price_per_volume = re.search(r'\d*\.\d+|\d+', price_volume_info.split('/')[0])
                    prod['price_per_volume'] = float(price_per_volume.group())
                    prod['volume_measure'] = price_volume_info.split('/')[1]
                except:
                    self.log('Price Volume Error {}'.format(traceback.format_exc()))

            was_price = item.get("wasPrice")
            now_price = item.get("price")
            if was_price and now_price:
                past_price = re.findall(r'\d+\.*\d*', was_price)
                current_price = re.findall(r'\d+\.*\d*', now_price)
                if past_price and current_price:
                    prod['was_now'] = current_price[0] + ', ' + past_price[0]

            buy_for_info = item.get('promoDetail')
            if buy_for_info:
                buy_for = re.findall(r'\d+\.*\d*', buy_for_info)
                prod['buy_for'] = buy_for[0] + ', ' + buy_for[1] if len(buy_for) > 1 else None

            prod['promotions'] = any(
                [
                    prod.get('was_now'),
                    prod.get('buy_for')
                ]
            )

            prod['locale'] = "en-GB"

            products_ids = item['id']
            url = self.API_URL.format(id=products_ids)

            if self.detect_ads:
                prod['ads'] = meta.get('ads')

            yield url, prod

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        try:
            data = json.loads(response.body_as_unicode())

            max_pages = int(data.get('maxPages', 0))
            cur_page = int(data.get('currentPage', 0) or 0)
            if cur_page >= max_pages:
                return None

            st = urllib.quote(data['keyword'])

            return Request(url=self.SEARCH_URL.format(search_term=st,
                                                      pagenum=cur_page + 1,
                                                      prods_per_page=60),
                           meta=meta)
        except Exception as e:
            self.log('Next Page Error {}'.format(traceback.format_exc(e)))
            raise

    def _parse_single_product(self, response):
        product = response.meta["product"]
        result = self._scrape_product_links(response)

        for p in result:
            for p2 in p:
                if isinstance(p2, SiteProductItem):
                    if "search_term" in p2:
                        del p2["search_term"]
                    product = SiteProductItem(dict(p2.items() + product.items()))

        try:
            data = json.loads(response.body_as_unicode())
            item = data['items'][0]
            if item.get("images", {}).get("largeImage"):
                product["image_url"] = item.get("images").get("largeImage")
            product['upc'] = item['upcNumbers'][0]['upcNumber']
        except Exception as e:
            self.log('Single Product Error {}'.format(traceback.format_exc(e)))

        product_id = re.findall('itemid=(\d+)', response.url)
        if product_id:
            url = self.REVIEW_URL % product_id[0]
            meta = {'product': product}
            return Request(url=url, meta=meta, callback=self._parse_review)

        return product

    @staticmethod
    def _get_reseller_id(link):
        reseller_id = re.search('/(\d+)', link)
        return reseller_id.group(1) if reseller_id else None
