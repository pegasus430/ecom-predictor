# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

import itertools
import json
import logging
import re
import traceback
import urllib
import urlparse
from datetime import datetime

from scrapy import Selector
from scrapy.conf import settings
from scrapy.http import Request
from scrapy.log import INFO, WARNING, ERROR
from scrapy.item import Field

from product_ranking.guess_brand import guess_brand_from_first_words, find_brand
from product_ranking.items import BuyerReviews, Price, SiteProductItem as BaseSiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value, FLOATING_POINT_RGEX)
from product_ranking.utils import is_empty, replace_http_with_https
from product_ranking.validation import BaseValidator
from product_ranking.validators.walmart_validator import \
    WalmartValidatorSettings

logger = logging.getLogger(__name__)


class SiteProductItem(BaseSiteProductItem):
    items_left = Field() # example: 'Only 1 left!', type: int


class WalmartProductsSpider(BaseValidator, BaseProductsSpider):
    """Implements a spider for Walmart.com.

    This spider has 2 very peculiar things.
    First, it receives 2 types of pages so it need 2 rules for every action.
    Second, the site sometimes redirects a request to the same URL so, by
    default, Scrapy would discard it. Thus we override everything to handle
    redirects.
    """
    name = 'walmart_products'
    allowed_domains = ["walmart.com"]

    default_hhl = [404, 500, 502, 520]

    # some search terms return shelf landing page, 'redirect=false' should prevent it
    # SEARCH_URL = "https://www.walmart.com/search/?query={search_term}&redirect=false"
    SEARCH_URL = "https://www.walmart.com/search/api/preso?prg=desktop&query={search_term}&page={page_num}&cat_id=0"
    PRESO_BASE_SEARCH_URL = "https://www.walmart.com/search/api/preso?prg=desktop&"

    QA_URL = "https://www.walmart.com/reviews/api/questions" \
             "/{product_id}?sort=mostRecentQuestions&pageNumber={page}"
    ALL_QA_URL = 'https://www.walmart.com/reviews/api/questions/%s?pageNumber=%i'

    REVIEW_DATE_URL = 'https://www.walmart.com/reviews/api/product/{product_id}?' \
                      'limit=3&sort=submission-desc&filters=&showProduct=false'

    STORE_SEARCH_URL = 'https://www.walmart.com/store/finder?location={zip_code}&distance=50'

    QA_LIMIT = 0xffffffff

    _SEARCH_SORT = {
        'best_match': 0,
        'high_price': 'price_high',
        'low_price': 'price_low',
        'best_sellers': 'best_seller',
        'newest': 'new',
        'rating': 'rating_high',
    }

    DEFAULT_STORE = '5260'
    # Not used, just for reference
    DEFAULT_ZIP_CODE = '72758'

    settings = WalmartValidatorSettings

    sponsored_links = []

    _JS_DATA_RE = re.compile(
        r'define\(\s*"product/data\"\s*,\s*(\{.+?\})\s*\)\s*;', re.DOTALL)

    def __init__(self, search_sort='best_match', *args, **kwargs):
        # TODO: refactor it
        global SiteProductItem
        self.username = kwargs.get('username', None)
        super(WalmartProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            url_formatter=FormatterWithDefaults(
                search_sort=self._SEARCH_SORT[search_sort]
            ),
            *args, **kwargs)

        settings.overrides['RETRY_HTTP_CODES'] = [500, 502, 503, 504, 400, 403, 408, 429]
        settings.overrides['REFERER_ENABLED'] = False

        # temporary
        ITEM_PIPELINES = settings.get('ITEM_PIPELINES')
        ITEM_PIPELINES['product_ranking.pipelines.PriceSimulator'] = 300
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.scrape_questions = kwargs.get('scrape_questions', None)
        if self.scrape_questions not in ('1', 1, True, 'true', 'True') or self.summary:
            self.scrape_questions = False
        self.visited_links = {}
        if not getattr(self, 'quantity', None) or getattr(self, 'quantity', 0) > 100:
            self.quantity = 100

    def start_requests(self):
        zip_code = getattr(self, 'zip_code', None)
        store = getattr(self, 'store', None)
        if zip_code and not store:
            yield Request(
                url=self.STORE_SEARCH_URL.format(zip_code=zip_code),
                callback=self.find_store_for_zip_code
            )
        else:
            self.cookies = {'PSID': store if store else self.DEFAULT_STORE}
            if self.product_url:
                if type(self.product_url) is str or type(self.product_url) is unicode:
                    self.product_url = self.product_url.strip()
                    self.product_url = replace_http_with_https(self.product_url)
                product = SiteProductItem()
                product['is_single_result'] = True
                product['url'] = self.product_url
                yield Request(self.product_url,
                              meta={'product': product,
                                    'handle_httpstatus_list': [404, 502, 520]},
                              callback=self.parse_product,
                              cookies=self.cookies
                              )

            else:
                for st in self.searchterms:
                    self.visited_links[st] = []
                    yield Request(self.SEARCH_URL.format(search_term=urllib.quote_plus(st.encode('utf-8')),
                                                         page_num=1),
                                  # self._parse_single_product,
                                  meta={'handle_httpstatus_list': [404, 502, 520],
                                        'remaining': self.quantity, 'search_term': st},
                                  dont_filter=True,
                                  cookies=self.cookies,
                                  callback=self._check_redirect
                                  )

    def find_store_for_zip_code(self, response):
        # Find nearest store for given zipcode value and set it's id in cookies
        # for Walmart, only store id matters, zipcode is only used to find nearest stores
        nearest_store = None
        try:
            stores_data = response.xpath('//script[@id="storeFinder"]/text()').extract()
            parsed_stores_data = json.loads(stores_data[0])
            nearest_stores = parsed_stores_data.get('storeFinder', {}).get(
                'storeFinderCarousel', {}).get('stores')
            if nearest_stores:
                nearest_store = str(nearest_stores[0].get('id'))
        except:
            pass
        finally:
            self.cookies = {'PSID': nearest_store if nearest_store else self.DEFAULT_STORE}
            self.store = nearest_store if nearest_store else self.DEFAULT_STORE
            if not nearest_store:
                self.log('Failed to find store for zipcode: {}, setting default store: {}'.format(
                    getattr(self, 'zip_code', None), self.DEFAULT_STORE), WARNING)

            for request in self.start_requests():
                yield request

    def _check_redirect(self, response):
        try:
            redirect_url = json.loads(response.body)
            redirect_url = redirect_url.get('destinationUrl')
            if redirect_url:
                return response.request.replace(
                    url=urlparse.urljoin(response.url, redirect_url),
                    callback=self.parse
                )
        except:
            self.log('no redirect url')
        return self.parse(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _search_page_error(self, response):
        path = urlparse.urlsplit(response.url)[2]
        return path == '/FileNotFound.aspx'

    @staticmethod
    def _extract_product_info_json_alternative(response):
        js_data = response.xpath('//script[@id="content" and @type="application/json"]/text()')
        if js_data:
            text = js_data.extract()[0]
            try:
                data = json.loads(text).get('content')
                return data if data else None
            except ValueError:
                pass

        _JS_DATA_RE = re.compile(
            r'window\.__WML_REDUX_INITIAL_STATE__\s*=\s*(\{.+?\})\s*;\s*<\/script>', re.DOTALL)
        js_data = re.search(_JS_DATA_RE, response.body_as_unicode().encode('utf-8'))
        if js_data:
            text = js_data.group(1)
            try:
                data = json.loads(text)
                return data
            except ValueError:
                pass
        try:
            data = json.loads(response.body_as_unicode())
            return data if data else None
        except ValueError:
            pass

    def _populate_from_js_alternative(self, data, product, response):
        if data:
            store = self._parse_store(data)
            cond_set_value(product, 'store', store)

            # Parse selected product id
            selected_product_id = self._parse_selected_product_id(data)
            # TODO fix this properly for products like https://www.walmart.com/ip/55208645
            original_selected_product_id = selected_product_id
            selected_product_id = data.get('productBasicInfo', {}).get('selectedProductId')

            # Parse selected product data
            selected_product = self._parse_selected_product_alternative(data, selected_product_id)

            # Parse selected product offers
            selected_product_offers = self._parse_selected_product_offers(selected_product)
            if not selected_product_offers:
                selected_product = self._parse_selected_product_alternative(data, original_selected_product_id)
                selected_product_offers = self._parse_selected_product_offers(selected_product)

            # Parse marketplaces
            marketplaces_data = self._parse_marketplaces_data_alternative(data, selected_product_id)

            # Parse title
            title = self._parse_title_alternative(selected_product)
            if not title:
                alternative_selected_id = data.get('productBasicInfo', {}).get('selectedProductId')
                title = data.get('productBasicInfo', {}).get(alternative_selected_id, {}).get("title")
            cond_set_value(product, 'title', title)

            # Parse brand
            brand = self._parse_brand_alternative(selected_product)
            if not brand:
                alternative_selected_id = data.get('productBasicInfo', {}).get('selectedProductId')
                brand = data.get('productBasicInfo', {}).get(alternative_selected_id, {}).get("brand")
            cond_set_value(product, 'brand', brand)

            # Parse out of stock
            is_out_of_stock = self._parse_out_of_stock_alternative(marketplaces_data, selected_product_offers)
            cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

            # Parse in-store pickup
            in_store_pickup = False if is_out_of_stock else self._check_in_store_pickup(data)
            cond_set_value(product, 'in_store_pickup', in_store_pickup)

            # Parse image url
            image_url = self._parse_image_url_alternative(data)
            cond_set_value(product, 'image_url', image_url)

            # Parse marketplaces names
            marketplaces_names = self._parse_marketplaces_names(data)

            # Parse selected product available marketplaces
            selected_product_marketplaces = self._parse_selected_product_marketplaces(selected_product)

            marketplace = self._parse_marketplaces_alternative(
                marketplaces_data, marketplaces_names, selected_product_marketplaces)
            cond_set_value(product, 'marketplace', marketplace)
            # Check if price is available only in cart
            if marketplace:
                cond_set_value(product, 'price_details_in_cart', marketplace[0].get(
                    "price_details_in_cart", False))

            # Parse buybox_owner
            if self.summary:
                flag = self._check_buybox_owner(response)
                product['buybox_owner'] = True if marketplace and flag else False

            # Parse price
            price = self._parse_price_alternative(marketplaces_data, selected_product_offers, product, data)
            if price:
                cond_set_value(product, 'price', Price(priceCurrency='USD', price=price))
            else:
                product['price'] = None

            # Parse price with discount
            price_with_discount = self._parse_price_with_discount(marketplaces_data)
            cond_set_value(product, 'price_with_discount', price_with_discount)

            # Parse price per volume
            price_volume_info = self._parse_price_per_volume(marketplaces_data)
            if price_volume_info:
                cond_set_value(product, 'price_per_volume', price_volume_info[0])
                cond_set_value(product, 'volume_measure', price_volume_info[1])

            # Parse buyer reviews

            buyer_reviews = self._parse_buyer_reviews_alternative(
                    self._parse_inline_json(response, ids_keys=['btf-content']), selected_product_id)
            cond_set_value(product, 'buyer_reviews', buyer_reviews)

            # Parse bestseller rank
            bestseller_rank = self._parse_bestseller_rank_alternative(selected_product)
            cond_set_value(product, 'bestseller_rank', bestseller_rank)

            # Parse gtin
            gtin = self._parse_gtin_alternative(selected_product)
            cond_set_value(product, 'gtin', gtin)

            pickup_today = self._parse_pickup_today(data)
            cond_set_value(product, 'pickup_today', pickup_today)

            items_left = self._parse_items_left(marketplaces_data)
            cond_set_value(product, 'items_left', items_left)

            # Parse upc
            if gtin and not product.get("upc"):
                cond_set_value(product, 'upc', gtin.lstrip("0").zfill(12))

            # Parse categories data
            categories_data = self._parse_categories_data_alternative(selected_product)
            if categories_data:
                # Parse categories
                categories = self._parse_categories_alternative(categories_data)
                cond_set_value(product, 'categories', categories)

                # Parse categories_full_info
                categories_full_info = self._parse_categories_full_info_alternative(response, categories_data)
                cond_set_value(product, 'categories_full_info', categories_full_info)

                # Parse department
                department = self._parse_department_alternative(categories)
                cond_set_value(product, 'department', department)

            shippable = self._parse_shipping(marketplaces_data)
            cond_set_value(product, 'shipping', shippable)

            rollback = self._is_rollback(marketplaces_data, selected_product_id)
            cond_set_value(product, 'special_pricing', rollback)

            save_amount = self._parse_save_amount_from_html(response)
            cond_set_value(product, 'save_amount', save_amount)

            price_old = self._parse_old(response)
            if price and price_old:
                cond_set_value(product, 'was_now', '{}, {}'.format(price, price_old))

    @staticmethod
    def _is_rollback(marketplaces_data, selected_product_id):
        for marketplace in marketplaces_data:
            if marketplace.get('productId') == selected_product_id:
                return marketplace.get('pricesInfo', {}).get('priceDisplayCodes', {}).get('rollback')

    @staticmethod
    def _check_in_store_pickup(data):
        offers = data.get('product', {}).get('offers')
        if offers:
            return any(
                option.get('availability') == "AVAILABLE" for store in offers
                for option in offers.get(store).get('fulfillment', {}).get('pickupOptions', [])
            )

    @staticmethod
    def _parse_pickup_today(data):
        try:
            offers = data.get('product', {}).get('offers')
            if offers:
                return any(
                    offers.get(store).get('pickupTodayEligible') for store in offers
                )
        except:
            return False

    @staticmethod
    def _parse_items_left(offers):
        for offer in offers:
            urgent_quantity = offer.get('fulfillment', {}).get('urgentQuantity')
            if urgent_quantity:
                return urgent_quantity

    def _check_buybox_owner(self, response):
        try:
            body = json.loads(response.body)
            internal_id = body.get('product', {}).get('selected', {}).get('product')
            sold_by = body.get('product', {}).get('idmlMap', {}).get(internal_id, \
                                                                     {}).get('modules', {}).get('GeneralInfo', {}).get(
                'sold_by')
            return sold_by.get('displayValue')
        except:
            self.log("Failed to check buybox owner: {}".format(traceback.format_exc()))

    @staticmethod
    def _parse_department_alternative(categories):
        return categories[-1] if categories else None

    @staticmethod
    def _parse_categories_full_info_alternative(response, categories_data):
        for category in categories_data:
            category['url'] = urlparse.urljoin(response.url, category.get('url'))
        return categories_data

    @staticmethod
    def _parse_categories_alternative(categories_data):
        return [category.get('name') for category in categories_data]

    @staticmethod
    def _parse_categories_data_alternative(selected_product):
        return selected_product.get('productAttributes', {}).get(
            'productCategory', {}).get('path')

    @staticmethod
    def _parse_selected_product_marketplaces(selected_product):
        return selected_product.get('offers', [])

    @staticmethod
    def _parse_selected_product_id(data):
        return data.get('product', {}).get('selected', {}).get('product')

    @staticmethod
    def _parse_selected_product_alternative(data, selected_product_id):
        selected = data.get('product', {}).get('products', {}).get(selected_product_id)
        if selected:
            return selected
        else:
            return data.get('product', {}).get('primaryProduct', {})

    @staticmethod
    def _parse_products_alternative(data):
        return data.get('product', {}).get('products', {})

    def _parse_variants_alternative(self, response, marketplaces, data, products, selected_product):
        variants = []
        primary_product_id = data.get('product', {}).get('primaryProduct')
        try:
            variants_map = data.get('product', {}).get('variantCategoriesMap', {}).get(primary_product_id, {})
        except:
            variants_map = {}
        for product in products.values():
            selected_product_offers = self._parse_selected_product_offers(product)
            price = self._parse_price_alternative(marketplaces, selected_product_offers)
            variant = {}
            properties = product.get('variants', {})
            variant_id = product.get('usItemId')
            url = urlparse.urljoin(response.url, '/ip/{}'.format(variant_id))
            selected_id = selected_product.get('usItemId')
            selected = selected_id == variant_id
            variant['selected'] = selected
            variant['url'] = url
            variant['price'] = price
            properties = self._parse_variant_properties_alternative(variant, variants_map, properties)
            variant['properties'] = properties
            variants.append(variant)
        return variants if len(variants) > 1 else None

    @staticmethod
    def _parse_variant_properties_alternative(variant, variants_map, properties):
        property_data = {}
        for property_name, property_value in properties.items():
            variant_data = variants_map.get(
                property_name, {}).get('variants', {}).get(property_value)
            name = variant_data.get('name')
            in_stock = variant_data.get('availabilityStatus') == 'AVAILABLE'
            variant['in_stock'] = in_stock
            if 'color' in property_name:
                property_data['color'] = name
            elif 'size' in property_name:
                property_data['size'] = name
            elif 'number_of_pieces' in property_name:
                property_data['count'] = name
            else:
                property_data[property_name] = name
        return property_data

    @staticmethod
    def _parse_selected_product_offers(selected_product):
        # TODO: remove try-exception
        try:
            return selected_product.get('offers', [])
        except:
            return []

    @staticmethod
    def _parse_marketplaces_data_alternative(data, selected_product_id):
        # if there is one seller, structure of json is different
        needed_data = data.get('product', {}).get('offers')
        if needed_data:
            if needed_data.get("availabilityStatus"):
                # pprint.pprint([needed_data])
                values = [needed_data]
            else:
                # pprint.pprint(needed_data.values())
                values = needed_data.values()
        else:
            values = []
        # https://www.walmart.com/nco/Prego-Ready-Meals-Roasted-Tomato--Vegetables-Penne-9-oz-Pack-of-2/47969283
        # marketplaces list has False element in the list, instead of dict (why?)
        order_of_marketplaces = [_id.get('id') for _id in data.get('offersOrder', {}).get(selected_product_id, [])]
        return sorted(
            filter(lambda item: isinstance(item, dict), values),
            key=lambda x: order_of_marketplaces.index(x.get('id')) if x.get('id') in order_of_marketplaces else None
        )

    @staticmethod
    def _parse_brand_alternative(selected_product):
        brand = selected_product.get('productAttributes', {}).get('brand')
        if brand:
            brand = brand.replace('\ufffd', '')
            brand = find_brand(brand)
        return brand

    @staticmethod
    def _parse_title_alternative(selected_product):
        return selected_product.get('productAttributes', {}).get('productName')

    @staticmethod
    def _parse_gtin_alternative(selected_product):
        return selected_product.get('productAttributes', {}).get('sku')

    @staticmethod
    def _parse_out_of_stock_alternative(marketplaces, selected_product_offers):
        for offer in marketplaces:
            offer_id = offer.get('id')
            if offer_id in selected_product_offers \
                    and offer.get('productAvailability', {}).get('availabilityStatus') == "IN_STOCK":
                return False
        if len(marketplaces) == 1:
            for offer in marketplaces:
                offer_id = offer.get('offerInfo', {}).get('offerId')
                if offer_id in selected_product_offers and offer.get('availabilityStatus') == "IN_STOCK":
                    return False
        return True

    def _parse_price_with_discount(self, marketplaces):
        price_with_discount = None

        try:
            for marketplace in marketplaces:
                if marketplace.get('pickupDiscount', {}):
                    price_with_discount = marketplace.get('pickupDiscount', {}).get('price')
                if not price_with_discount and marketplace.get('pickupDiscountOfferPrice'):
                    price_with_discount = marketplace.get('pickupDiscountOfferPrice', {}).get('price')
                if price_with_discount:
                    break
        except Exception:
            self.log("Error while parsing discount: {}".format(traceback.format_exc()), WARNING)

        if price_with_discount:
            price_with_discount = '$' + str(price_with_discount)

        return price_with_discount

    def _parse_price_alternative(self, marketplaces, offers, product=None, data=None):
        if product and product.get('marketplace') and product.get('marketplace')[0].get('price'):
            return product.get('marketplace')[0].get('price')
        elif data and data.get('product', {}).get('midasContext', {}).get('price'):
            return data.get('product').get('midasContext').get('price')

        in_stock_prices = [
            (marketplace.get('pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('price'),
             marketplace.get('shippingPrice', 0))
            for marketplace in marketplaces
            if isinstance(marketplace, dict)
               and marketplace.get('id') in offers
               and marketplace.get('productAvailability', {}).get('availabilityStatus') == 'IN_STOCK']

        not_in_stock_prices = [
            (marketplace.get('pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('price'),
             marketplace.get('shippingPrice', 0))
            for marketplace in marketplaces
            if isinstance(marketplace, dict)
               and marketplace.get('id') in offers
               and marketplace.get('productAvailability', {}).get('availabilityStatus') != 'IN_STOCK']

        prices = in_stock_prices or not_in_stock_prices

        try:
            price = float(min(
                filter(lambda price: isinstance(price[0], (float, int)), prices),
                key=sum
            )[0]
                          )
        except:
            price = None
            self.log('Can not convert price into float: {}'.format(traceback.format_exc()))
        return price

    def _parse_price_per_volume(self, marketplaces):
        try:
            for marketplace in marketplaces:
                price_volume_info = marketplace.get('unitPriceDisplayValue')
                price_per_volume = float(re.search('\d+\.?\d*', price_volume_info).group())
                volume_mesure = price_volume_info.split('/')[-1].strip()
                return price_per_volume, volume_mesure
        except:
            self.log("Can't extract price per volume : {}".format(traceback.format_exc()), WARNING)

    @staticmethod
    def _parse_image_url_alternative(data):
        images = data.get('product', {}).get('images', {}).values()
        for image in images:
            if image.get('type') == 'PRIMARY':
                return image.get('assetSizeUrls', {}).get('main')

    @staticmethod
    def _parse_marketplaces_names(data):
        names = {}
        sellers = data.get('product', {}).get('sellers', {})
        sellers = sellers.values() if not sellers.get('sellerId') else [sellers]
        for seller in sellers:
            seller_id = seller.get('sellerId')
            seller_name = seller.get('sellerDisplayName')
            names[seller_id] = seller_name
        return names

    @staticmethod
    def _parse_marketplaces_alternative(marketplaces_data, marketplaces_names, selected_product_marketplaces):
        marketplaces_dict = {}
        some_marketplaces_are_shippable = any(marketplace.get('fulfillment', {}).get('shippable')
                                              for marketplace in marketplaces_data)
        for marketplace in marketplaces_data:
            offer_id = marketplace.get('id')
            seller_id = marketplace.get('sellerId')
            price = marketplace.get(
                'pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('price', 0)
            currency = marketplace.get(
                'pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('currencyUnit')
            price_details_in_cart = marketplace.get(
                'pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('submapType') == "CHECKOUT"
            name = marketplaces_names.get(seller_id)
            if offer_id in selected_product_marketplaces:
                if (marketplace.get('fulfillment', {}).get('shippable')
                    or not (marketplaces_dict or some_marketplaces_are_shippable)):
                    marketplaces_dict[offer_id] = {'name': name,
                                                   'price': price,
                                                   'currency': currency,
                                                   'price_details_in_cart': price_details_in_cart
                                                   }
        marketplaces = []
        # Sort marketplaces correctly
        for offer_id in selected_product_marketplaces:
            seller = marketplaces_dict.get(offer_id)
            if seller:
                marketplaces.append(seller)
        return marketplaces

    def _parse_buyer_reviews_alternative(self, data, product_id):
        reviews = data.get('product', {}).get('reviews', {}).get(product_id, {})
        return BuyerReviews(
            rating_by_star={
                1: reviews.get('ratingValueOneCount', 0),
                2: reviews.get('ratingValueTwoCount', 0),
                3: reviews.get('ratingValueThreeCount', 0),
                4: reviews.get('ratingValueFourCount', 0),
                5: reviews.get('ratingValueFiveCount', 0),
            },
            num_of_reviews=reviews.get('totalReviewCount', 0),
            average_rating=round(reviews.get('averageOverallRating', 0), 2)
        )

    @staticmethod
    def _parse_bestseller_rank_alternative(selected_product):
        ranks = selected_product.get('itemSalesRanks')
        return ranks[0].get('rank') if ranks else None

    @staticmethod
    def _parse_shipping(offers):
        return any(offer.get('fulfillment', {}).get('shippable') for offer in offers)

    @staticmethod
    def _parse_is_out_of_stock(data):
        return not data.get('analyticsData', {}).get('inStock')

    @staticmethod
    def _parse_brand_from_html(response, product):
        brand = is_empty(response.xpath(
            "//div[@class='product-subhead-section']"
            "/a[@id='WMItemBrandLnk']/text() | "
            ".//*[@id='WMItemBrandLnk']//*[@itemprop='brand']/text() |"
            ".//*[@itemprop='brand']/text()").extract())
        if not brand:
            title = product.get('title', '').replace(u'В®', '')
            brand = guess_brand_from_first_words(title)
        if brand:
            # guess_brand_from_first_words may return None value
            brand = brand.replace('&amp;', "&").replace('\ufffd', '')
        return brand

    @staticmethod
    def _parse_save_amount_from_html(response):
        save_amount = response.xpath(
            "//div[contains(@class, 'Savings-price')]"
            "//*[@class='Price-group']/@title").re(FLOATING_POINT_RGEX)

        if save_amount:
            return save_amount[0]

    @staticmethod
    def _parse_old(response):
        price_old = response.xpath(
            "//div[contains(@class, 'Price-old')]"
            "//span[contains(@class, 'Price-group')]/@title").re(FLOATING_POINT_RGEX)

        if price_old:
            return price_old[0]

    def _scrape_total_matches(self, response):
        if response.css('.no-results'):
            return 0

        matches = response.css('.result-summary-container ::text').re(
            'Showing \d+ of (.+) results')
        if matches:
            num_results = matches[0].replace(',', '')
            num_results = int(num_results)
        else:
            num_results = self._extract_total_matches(response)
            if not num_results:
                self.log(
                    "Failed to extract total matches from %r." % response.url,
                    ERROR
                )
        return num_results

    def _scrape_results_per_page(self, response):
        num = response.css('.result-summary-container ::text').re(
            'Showing (\d+) of')
        if num:
            return int(num[0])
        return None

    def _scrape_product_links(self, response):
        items = response.xpath(
            '//div[@class="js-tile tile-landscape"] | '
            '//div[contains(@class, "js-tile js-tile-landscape")] | '
            '//div[contains(@class,"js-tile tile-grid-unit")]'
        )
        if not items:
            items = response.xpath('//div[contains(@class, "js-tile")]')

        if not items:
            data = self._extract_product_info_json_alternative(response)
            info = self._extract_info_from_json(data)
            products = info.get('items', [])
            is_catapult = info.get('featuredItem', [])

            for product in products:
                link = urlparse.urljoin(
                    response.url,
                    product.get('productPageUrl')
                )

                is_sponsored_product = bool(product.get('wpa'))
                special_offer = product.get('specialOfferBadge')

                res_item = SiteProductItem()
                res_item['url'] = link

                if special_offer == "bestseller":
                    res_item['is_best_seller_product'] = True
                elif special_offer == "new":
                    res_item['is_new_product'] = True

                res_item['is_sponsored_product'] = is_sponsored_product
                res_item['is_catapult_product'] = bool(is_catapult)

                yield link, res_item
        else:
            data = {}

        if not items and not data:
            self.log("Found no product links in %r." % response.url, INFO)

        for item in items:
            link = item.css('a.js-product-title ::attr(href)')[0].extract()
            if link in self.visited_links.get(response.meta.get('search_term'), []):
                continue
            else:
                self.visited_links.get(response.meta.get('search_term'), []).append(link)

            title = ''.join(item.xpath(
                'div/div/h4[contains(@class, "tile-heading")]/a/node()'
            ).extract()).strip()
            title = is_empty(Selector(text=title).xpath('string()').extract())

            image_url = is_empty(item.xpath(
                "a/img[contains(@class, 'product-image')]/@data-default-image"
            ).extract())

            if item.css('div.pick-up-only').xpath('text()').extract():
                is_pickup_only = True
            else:
                is_pickup_only = False

            if item.xpath(
                    './/div[@class="tile-row"]'
                    '/span[@class="in-store-only"]/text()'
            ).extract():
                is_in_store_only = True
            else:
                is_in_store_only = False

            if item.xpath(
                    './/div[@class="tile-row"]'
                    '/span[@class="flag-rollback"]/text()'
            ).extract():
                special_pricing = True
            else:
                special_pricing = False

            if item.css('div.out-of-stock').xpath('text()').extract():
                shelf_page_out_of_stock = True
            else:
                shelf_page_out_of_stock = False

            res_item = SiteProductItem()
            if title:
                res_item["title"] = title.strip()
            if image_url:
                res_item["image_url"] = image_url
            res_item['is_pickup_only'] = is_pickup_only
            res_item['is_in_store_only'] = is_in_store_only
            res_item['special_pricing'] = special_pricing
            res_item['shelf_page_out_of_stock'] = shelf_page_out_of_stock
            yield link, res_item

    def _scrape_next_results_page_link(self, response):
        next_page = None

        next_page_links = response.css(".paginator-btn-next ::attr(href)")
        if len(next_page_links) == 1:
            next_page = next_page_links.extract()[0]
        elif len(next_page_links) > 1:
            self.log(
                "Found more than one 'next page' link in %r." % response.url,
                ERROR
            )
        else:
            next_page = self._extract_next_page_query(response)
            if not next_page:
                self.log(
                    "Found no 'next page' link in %r (which could be OK)."
                    % response.url,
                    INFO
                )

        return next_page

    def _request_questions_info(self, response):
        product_id = response.meta['product_id']
        if product_id is None:
            return response.meta['product']
        new_meta = response.meta.copy()
        new_meta['product']['recent_questions'] = []
        url = self.QA_URL.format(product_id=product_id, page=1)
        if self.scrape_questions:
            return Request(url, self._parse_questions,
                           meta=new_meta, dont_filter=True)
        else:
            return response.meta['product']

    def _parse_questions(self, response):
        data = json.loads(response.body_as_unicode())
        product = response.meta['product']
        if not data:
            if not product.get('buyer_reviews') or \
                            product.get('buyer_reviews') == 0:
                pass
            else:
                return product
        last_date = product.get('date_of_last_question')
        questions = product['recent_questions']
        dateconv = lambda date: datetime.strptime(date, '%m/%d/%Y').date()
        for question_data in data.get('questionDetails', []):
            date = dateconv(question_data['submissionDate'])
            if last_date is None:
                product['date_of_last_question'] = last_date = date
            if date == last_date:
                questions.append(question_data)
            else:
                break
        else:
            total_pages = min(self.QA_LIMIT,
                              data['pagination']['pages'][-1]['num'])
            current_page = response.meta.get('current_qa_page', 1)
            if current_page < total_pages:
                url = self.QA_URL.format(
                    product_id=response.meta['product_id'],
                    page=current_page + 1)
                response.meta['current_qa_page'] = current_page + 1
                return Request(url, self._parse_questions, meta=response.meta,
                               dont_filter=True)
        if not questions:
            del product['recent_questions']
        else:
            product['date_of_last_question'] = str(last_date)
        if product.get('buyer_reviews') and product.get('buyer_reviews') != 0:
            if 'buyer_reviews' in product.keys():
                new_meta = response.meta.copy()
                return Request(url=self.REVIEW_DATE_URL.format(
                    product_id=response.meta['product_id']),
                    callback=self._parse_last_buyer_review_date,
                    meta=new_meta,
                    dont_filter=True)
            else:
                return product

    def _parse_all_questions_and_answers(self, response):
        original_prod_url = response.meta['product']['url']
        product = response.meta['product']

        recent_questions = product.get('recent_questions', [])
        current_qa_page = int(
            re.search(r'pageNumber=(\d+)', response.url).group(1))

        try:
            content = json.loads(response.body)
            if not isinstance(content, dict):
                raise Exception
        except:
            self.log('Can not convert body into json or json not a dict: {}'.format(traceback.format_exc()))
            #yield product
            yield product
            return

        try:
            total_pages = min(self.QA_LIMIT,
                              content.get('pagination', {}).get('pages', [])[-1].get('num'))
        except:
            total_pages = 0
            self.log('Can not extract total question pages number: {}'.format(traceback.format_exc()))
        recent_questions.extend(content.get('questionDetails', []))

        if self.username:
            for idx, q in enumerate(recent_questions):
                if 'answeredByUsername' not in q:
                    recent_questions[idx]['answeredByUsername'] = False
                    if 'answers' in q:
                        for answer in q['answers']:
                            if 'userNickname' in answer:
                                if self.username.strip().lower() == answer['userNickname'].strip().lower():
                                    recent_questions[idx]['answeredByUsername'] = True

        product['recent_questions'] = recent_questions

        if current_qa_page < total_pages:
            _meta = response.meta
            _meta['product'] = product

            next_qa_page = current_qa_page + 1
            url = self.ALL_QA_URL % (self.get_walmart_id_from_url(original_prod_url), next_qa_page)
            yield Request(
                url,
                callback=self._parse_all_questions_and_answers,
                meta=_meta)
        else:
            yield product

    def _parse_last_buyer_review_date(self, response):
        product = response.meta['product']
        data = json.loads(response.body_as_unicode())
        sel = Selector(text=data['reviewsHtml'])
        lbrd = sel.xpath('//span[contains(@class, "customer-review-date")]'
                         '/text()').extract()
        if lbrd:
            lbrd = datetime.strptime(lbrd[0].strip(), '%m/%d/%Y')
            product['last_buyer_review_date'] = lbrd.strftime('%d-%m-%Y')

        return product

    def _parse_temporary_unavailable(self, response):
        condition = response.xpath(
            '//p[contains(@class, "error") '
            'and contains(text(), "We\'re having technical difficulties and are looking into the problem now.")]')
        return bool(condition)

    def parse(self, response):
        # call the appropriate method for the code. It'll only work if you set
        #  `handle_httpstatus_list = [502, 503, 504]` in the spider
        if hasattr(self, 'handle_httpstatus_list'):
            for _code in self.handle_httpstatus_list:
                if response.status == _code:
                    _callable = getattr(self, 'parse_' + str(_code), None)
                    if callable(_callable):
                        yield _callable()

        if self._search_page_error(response):
            remaining = response.meta['remaining']
            search_term = response.meta['search_term']

            self.log("For search term '%s' with %d items remaining,"
                     " failed to retrieve search page: %s"
                     % (search_term, remaining, response.request.url),
                     WARNING)
        elif self._parse_temporary_unavailable(response):
            item = SiteProductItem()
            item['temporary_unavailable'] = True
            yield item
        else:
            prods_count = -1  # Also used after the loop.
            for prods_count, request_or_prod in enumerate(
                    self._get_products(response)):
                yield request_or_prod
            prods_count += 1  # Fix counter.

            request = self._get_next_products_page(response, prods_count)
            if request is not None:
                yield request

    @staticmethod
    def _parse_inline_json(response, ids_keys=('atf-content', 'content')):
        _JS_DATA_RE = re.compile(
            r'window\.__WML_REDUX_INITIAL_STATE__\s*=\s*(\{.+?\})(\s*;\s*})?\s*;\s*<\/script>', re.DOTALL)
        raw_data = re.search(_JS_DATA_RE, response.body)
        data = json.loads(raw_data.group(1), encoding='utf-8') if raw_data else {}
        if not data.get('product', {}).get('selected', {}).get('product'):
            for key in reversed(ids_keys):
                raw_data = response.xpath('//script[@id="{}"]/text()'.format(key)).extract()
                if raw_data:
                    data = json.loads(raw_data[0])[key]

        return data

    def parse_product(self, response):
        product = response.meta.get("product")
        electrode_prod_data = None
        is_review_data = None
        if response.status == 520:
            product['temporary_unavailable'] = True
            return product
        elif response.status == 404:
            product['not_found'] = True
            return product

        if 'redirect_urls' in response.meta:
            product['is_redirected'] = True
            product['url_after_redirection'] = response.meta['redirect_urls'][-1]

        prod_data = self._parse_inline_json(response)
        if prod_data:
            response.meta['data'] = prod_data
            self._parse_upc_electrode(prod_data, product)
            self._populate_from_js_alternative(prod_data, product, response)
            self._parse_variants_electrode(prod_data, product)
            self._parse_inla_electrode(prod_data, product)
            response.meta['product'] = product

        if self.scrape_questions:
            return Request(  # make another call - to scrape questions/answers
                self.ALL_QA_URL % (
                    self.get_walmart_id_from_url(product['url']), 1),
                meta=response.meta,
                callback=self._parse_all_questions_and_answers
            )
        else:
            return product

    def _parse_reviews_from_page(self, response):
        product = response.meta.get('product')
        data = re.search(r'window\.__WML_REDUX_INITIAL_STATE__ =\s*({.+?});', response.body)
        if data:
            try:
                data = json.loads(data.group(1), encoding='utf-8')
            except:
                self.log('Error while parsing backup product JSON to extract reviews {}'.format(traceback.format_exc()))
            else:
                buyer_reviews = self._parse_buyer_reviews_alternative(data)
                product["buyer_reviews"] = buyer_reviews
        return product

    @staticmethod
    def _parse_inla_electrode(electrode_prod_data, product):
        global_oos = electrode_prod_data.get("product", {}).get(
            "selected", {}).get("allOffersAreOOS", None)
        if global_oos:
            cond_set_value(product, 'is_out_of_stock', global_oos)

        offers_raw_data = electrode_prod_data.get("product", {}).get("offers", {})
        if not offers_raw_data:
            product["no_longer_available"] = True
        # checks if default variant is INLA
        # if yes, base product is INLA as well
        variants = product.get("variants", [])
        if variants:
            for variant in variants:
                if variant.get("selected") is True and variant.get("no_longer_available") is True:
                    product["no_longer_available"] = True

        is_in_store_only = not (product.get('price') or product.get('shipping') or product.get('no_longer_available'))
        cond_set_value(product, 'is_in_store_only', is_in_store_only)

        if not product.get('is_in_store_only') and not product.get('price'):
            product['no_longer_available'] = True
            product['is_out_of_stock'] = True

    def _parse_variants_electrode(self, electrode_prod_data, product):
        primary_product = electrode_prod_data.get("product", {}).get("primaryProduct")
        try:
            properties = electrode_prod_data.get('product', {}).get('variantCategoriesMap', {}).get(primary_product)
            variants_properties = self._build_variants_properties(properties)
        except:
            variants_properties = []
            self.log(traceback.format_exc())
        variants_raw_data = electrode_prod_data.get("product", {}).get("products", {})
        offers_raw_data = electrode_prod_data.get("product", {}).get("offers", {})
        canonical_url = product.get("url")

        try:
            canonical_url = '/'.join(canonical_url.split('/')[:-1])
        except:
            canonical_url = None
            self.log(traceback.format_exc())

        parsed_variants = []
        for property_value in variants_properties:
            variant = {}
            sku = property_value.pop('id', None)
            if sku:
                variant['sku'] = sku
            variant['properties'] = property_value
            if sku in variants_raw_data:
                variant_raw = variants_raw_data.get(sku)
                item_id = variant_raw.get("usItemId")
                variant['upc'] = variant_raw.get("upc")
                if canonical_url:
                    variant['url'] = "{}/{}".format(canonical_url, item_id)
                else:
                    variant['url'] = "https://www.walmart.com/ip/{}".format(item_id)

                primary_item_id = product.get("url", '').split("/")[-1]
                variant['selected'] = variant_raw.get("usItemId") == primary_item_id
                offer = variant_raw.get("offers")
                offer_id = offer[0] if offer else None
                if offer_id:
                    offer_data = offers_raw_data[offer_id]
                    if offer_data:
                        variant['price'] = offer_data.get(
                            "pricesInfo", {}).get("priceMap", {}).get("CURRENT", {}).get("price")
                    else:
                        variant['price'] = None
                    in_stock_raw = offer_data.get("productAvailability", {}).get("availabilityStatus")
                    if in_stock_raw == "IN_STOCK":
                        variant['in_stock'] = True
                    elif in_stock_raw == "OUT_OF_STOCK":
                        variant['in_stock'] = False
                else:
                    variant['in_stock'] = False
                    variant['no_longer_available'] = True
            else:
                variant['selected'] = False
                variant['in_stock'] = False
                variant['no_longer_available'] = True
            parsed_variants.append(variant)
        if parsed_variants:
            product['variants'] = parsed_variants

    @staticmethod
    def _parse_upc_electrode(electrode_prod_data, product):
        prod_id = electrode_prod_data.get("productId")
        if prod_id:
            variants_raw_data = electrode_prod_data.get("product", {}).get("products", {})
            for sku, variant_raw in variants_raw_data.iteritems():
                variant_id = variant_raw.get("usItemId")
                if variant_id == prod_id:
                    cond_set_value(product, "upc", variant_raw.get("upc"))
                else:
                    continue

    def _extract_next_page_query(self, response):
        data = self._extract_product_info_json_alternative(response)
        info = self._extract_info_from_json(data)
        query = info.get('pagination', {}).get('next', {}).get('url', '') if data else None
        if query:
            if self.PRESO_BASE_SEARCH_URL in response.url:
                next_page = "{}{}".format(self.PRESO_BASE_SEARCH_URL, query)
            else:
                next_page = urlparse.urljoin(
                    response.url,
                    '/search/?{query}'.format(query=query))
            return next_page

    def _extract_total_matches(self, response):
        self.log('New walmart version!')
        data = self._extract_product_info_json_alternative(response)
        info = self._extract_info_from_json(data)
        total_matches = info.get('requestContext', {}).get('itemCount', {}).get('total', None) if data else None
        return total_matches

    @staticmethod
    def _extract_info_from_json(data):
        info = {}
        if data:
            if 'preso' in data:
                info = data.get('preso', {})
            elif 'topicData' in data:
                info = data.get('topicData', {})
            else:
                info = data
        return info

    def _build_variants_properties(self, properties):
        variants = {}
        available_variants = {}
        for property_name, property_value in properties.items():
            property_name = property_name.replace('actual_color', 'color')
            for variant_value in property_value.get('variants').values():
                property_value = variant_value.get('name')
                if property_name not in variants:
                    variants[property_name] = []
                variants[property_name].append(property_value)

                for variant_id in variant_value.get('products'):
                    if variant_id not in available_variants:
                        available_variants[variant_id] = {}
                    available_variants[variant_id][property_name] = property_value

        variants = list((dict(itertools.izip(variants, x)) for x in itertools.product(*variants.itervalues())
                         if x))
        for variant_id, variant_value in available_variants.items():
            for variant in variants:
                if variant == variant_value:
                    variant['id'] = variant_id

        return variants

    def _get_products(self, response):
        for item in super(WalmartProductsSpider, self)._get_products(response):
            if isinstance(item, Request):
                item.meta.setdefault('handle_httpstatus_list', []).extend([404, 502, 520])

            yield item

    def get_walmart_id_from_url(self, url):
        """ Returns item ID from the given URL """
        # possible variants:
        # http://walmart.com/ip/37002591?blabla=1
        # http://www.walmart.com/ip/Pampers-Swaddlers-Disposable-Diapers-Economy-Pack-Plus-Choose-your-Size/27280840
        g = re.findall(r'/([0-9]{3,20})', url)
        if not g:
            self.log('Can not extract product id from url: {}'.format(url), ERROR)
            return
        return g[-1]

    @staticmethod
    def _parse_store(data):
        offers_base = data.get('product', {}).get('offers', {}).values() or data.get(
            'terra', {}).get('offers', {}).values()
        for offer in offers_base:
            if type(offer) != dict or not offer.get('fulfillment', {}).get('pickupable'):
                continue
            options = offer.get('fulfillment', {}).get('pickupOptions')
            if options and options[0].get('preferredStore'):
                return str(options[0].get('storeId'))
