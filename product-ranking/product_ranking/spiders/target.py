# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import copy
import json
import re
import traceback
import urllib
import urlparse
from itertools import islice
from scrapy.item import Field

from scrapy import Selector
from scrapy.conf import settings
from scrapy.http import FormRequest, Request
from scrapy.log import DEBUG

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (FLOATING_POINT_RGEX, BaseProductsSpider,
                                     cond_set_value)
from product_ranking.utils import is_empty, handle_date_from_json
from product_ranking.validation import BaseValidator
from product_ranking.validators.target_validator import TargetValidatorSettings
from product_ranking.guess_brand import guess_brand_from_first_words


class TargetProductItem(SiteProductItem):
    subs_discount_percent = Field()  # Subscription discount percent


class TargetProductSpider(BaseValidator, BaseProductsSpider):
    name = 'target_products'
    allowed_domains = ["target.com", "recs.richrelevance.com",
                       'api.bazaarvoice.com']
    start_urls = ["http://www.target.com/"]

    settings = TargetValidatorSettings

    user_agent_override = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.85 Safari/537.36'

    user_agent_googlebot = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'

    # TODO: support new currencies if you're going to scrape target.canada
    #  or any other target.* different from target.com!
    SEARCH_URL = "http://redsky.target.com/v1/plp/search?keyword={search_term}&count=24&offset=0"
    SEARCH_URL_SHELF = "http://redsky.target.com/v1/plp/search?count=24&offset=0&category={category}"

    SCRIPT_URL = "http://recs.richrelevance.com/rrserver/p13n_generated.js"
    QUESTION_URL = "https://redsky.target.com/drax-domain-api/v1/questions?product_id={product_id}" \
                   "&sort_order=recent_answered&limit={total_questions}&offset=0"
    CALL_RR = False
    CALL_RECOMM = True
    POPULATE_VARIANTS = False
    POPULATE_REVIEWS = True
    POPULATE_QA = True
    SORTING = None

    SORT_MODES = {
        "relevance": "relevance",
        "featured": "Featured",
        "pricelow": "PriceLow",
        "pricehigh": "PriceHigh",
        "newest": "newest",
        "bestselling": "bestselling"
    }

    REDSKY_API_URL = 'https://redsky.target.com/v2/pdp/tcin/{}?excludes=taxonomy&storeId={}'

    JSON_SEARCH_URL = "http://tws.target.com/searchservice/item" \
                      "/search_results/v1/by_keyword" \
                      "?callback=getPlpResponse" \
                      "&searchTerm=null" \
                      "&category={category}" \
                      "&sort_by={sort_mode}" \
                      "&pageCount=60" \
                      "&start_results={index}" \
                      "&page={page}" \
                      "&zone=PLP" \
                      "&faceted_value=" \
                      "&view_type=medium" \
                      "&stateData=" \
                      "&response_group=Items" \
                      "&isLeaf=true" \
                      "&parent_category_id={category}"

    AVAILABILITY_URL = 'https://api.target.com/available_to_promise/v2/{product_id}/search' \
                       '?key=eb2551e4accc14f38cc42d32fbc2b2ea&nearby={zip_code}&field_groups=location_summary' \
                       '&multichannel_option=none&inventory_type=stores&requested_quantity=1&radius=100'

    handle_httpstatus_list = [400, 404]

    def __init__(self, sort_mode=None, store='1139', zip_code='11590', *args, **kwargs):
        if sort_mode:
            if sort_mode.lower() not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
            else:
                self.SORTING = self.SORT_MODES[sort_mode.lower()]

        self.zip_code = zip_code
        self.store = store

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        super(TargetProductSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        if self.summary:
            self.POPULATE_QA = False
            self.POPULATE_REVIEWS = False
            self.CALL_RECOMM = False
            self.POPULATE_VARIANTS = False

        self.scrape_questions = kwargs.get('scrape_questions', None)
        if self.scrape_questions not in ('1', 1, True, 'true', 'True') or self.summary:
            self.scrape_questions = False

        self.user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                          'Chrome/40.0.2214.85 Safari/537.36'

    def start_requests(self):
        for req in super(TargetProductSpider, self).start_requests():
            if self.product_url:
                req = req.replace(meta={'product': TargetProductItem()})
            yield req

    def parse(self, response):
        try:
            data = json.loads(response.body)
            args = self._json_get_args_v1(data.get('search_response', {}).get('metaData', []))

            if args.get('redirect_url'):
                # redirect to shelf page
                category = re.search(r'^http://[\w]*\.target\.com/[\w/-]+/-/N-(\w+)(?:Z\w+)?#?',
                                     args.get('redirect_url'))
                if category:
                    self.SEARCH_URL = self.SEARCH_URL_SHELF

                    redirect_url = self.SEARCH_URL.format(category=category.group(1))
                    self.log('Redirecting to shelf page: {}'.format(redirect_url))

                    yield response.request.replace(url=redirect_url)
            else:
                for item in super(TargetProductSpider, self).parse(response):
                    yield item
        except:
            self.log(traceback.format_exc(), DEBUG)

    def _get_tcin(self, response):
        tcin = re.search(u'Online Item #:[^\d]*(\d+)', response.body_as_unicode())
        if tcin:
            return tcin.group(1)
        return self._product_id_v2(response)

    def parse_product(self, response):
        canonical_url = response.xpath(
            '//meta[@property="og:url"]/@content'
        ).extract()
        response.meta['canonical_url'] = canonical_url
        prod = response.meta['product']

        cond_set_value(prod, 'locale', 'en-US')

        price = is_empty(response.xpath(
            '//p[contains(@class, "price")]/span/text()').extract())
        if not price:
            price = is_empty(response.xpath(
                '//*[contains(@class, "price")]'
                '/*[contains(@itemprop, "price")]/text()'
            ).extract())
        if price:
            price = is_empty(re.findall("\d+\.{0,1}\d+", price))
            if price:
                prod['price'] = Price(
                    price=price.replace('$', '').replace(',', '').strip(),
                    priceCurrency='USD'
                )

        special_pricing = is_empty(response.xpath(
            '//li[contains(@class, "eyebrow")]//text()').extract())
        if special_pricing == "TEMP PRICE CUT":
            prod['special_pricing'] = True
        else:
            prod['special_pricing'] = False

        if 'url' not in prod:
            prod['url'] = response.url

        old_url = prod['url'].rsplit('#', 1)[0]
        prod['url'] = old_url

        cond_set_value(prod, 'store', self.store)
        cond_set_value(prod, 'zip_code', self.zip_code)

        regex = "-/\w-(\d+)"
        reseller_id = re.findall(regex, prod.get('url', ''))
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(prod, "reseller_id", reseller_id)

        tcin = re.search('A-(\d+)', response.url, re.DOTALL)
        if tcin:
            prod['tcin'] = tcin.group(1)

        title = re.search('p/(.*?)/', response.url, re.DOTALL)
        if title:
            cond_set_value(prod, "title", title.group(1))

        if self.scrape_questions:
            tcin = prod['tcin']
            total_question = response.xpath('//span[@data-test="questionsCount"]/text()').re('(\d+)')
            if tcin and total_question:
                return Request(
                    url=self.QUESTION_URL.format(product_id=tcin, total_questions=int(total_question[0])),
                    callback=self._parse_qa_data,
                    meta={
                        'product': response.meta['product'],
                        'tcin': tcin
                    }
                )

        return Request(self.REDSKY_API_URL.format(self._get_tcin(response), self.store),
                       callback=self.parse_pre_product_page,
                       meta=response.meta)

    def parse_pre_product_page(self, response):
        product = response.meta['product']
        if "Access Denied" in response.body_as_unicode():
            return
        elif response.status == 404:
            if response.meta.get('content_json'):
                self._populate_from_v3(response, product, response.meta.get('content_json', {}).get('product', {}))
            else:
                product['no_longer_available'] = True
                product['not_found'] = True
            return product
        content_json = json.loads(response.body_as_unicode())
        upc = content_json.get('product', {}).get('item', {}).get('upc')
        if upc:
            product['upc'] = upc

        save_amount = content_json.get('product', {}).get('price', {}).get('offerPrice', {}).get('saveDollar')
        product['save_amount'] = save_amount

        save_percent = content_json.get('product', {}).get('price', {}).get('offerPrice', {}).get('savePercent')
        product['save_percent'] = save_percent

        product['in_store_pickup'] = None
        try:
            pickup_stores = is_empty(content_json.get('product', {})
                                     .get('available_to_promise_store', {}).get('products', {}))
            if pickup_stores:
                option = pickup_stores.get('availability_status')
                product['in_store_pickup'] = True if option in ['IN_STOCK', 'LIMITED_STOCK_SEE_STORE'] else False
        except Exception as e:
            self.log("Failed to parse pickup options or pickup block is empty: {}".format(traceback.format_exc(e)),
                     DEBUG)

        parent_tcin = content_json.get('product', {}).get('item', {}).get('parent_items', None)
        if isinstance(parent_tcin, unicode):
            response.meta.update({'content_json': content_json})
            return Request(self.REDSKY_API_URL.format(parent_tcin, self.store),
                           callback=self.parse_pre_product_page,
                           meta=response.meta)
        else:
            product = self._populate_from_v3(response, product, content_json.get('product'))
            return product

    def _parse_qa_data(self, response):
        product = response.meta['product']
        tcin = response.meta['tcin']
        recent_questions = []

        try:
            question_data = json.loads(response.body_as_unicode())

            for question in question_data:
                question_info = {}
                question_info['questionId'] = question.get('Id')
                question_info['userNickname'] = question.get('UserNickname')
                question_info['questionSummary'] = question.get('QuestionSummary')

                # Get answers by answer_ids
                answers = question.get('Answers')
                if answers:
                    answer_list = []
                    for answ in answers:
                        answer = dict()
                        answer['answerText'] = answ.get('AnswerText')
                        answer['negativeVoteCount'] = answ.get('TotalNegativeFeedbackCount')
                        answer['positiveVoteCount'] = answ.get('TotalPositiveFeedbackCount')
                        answer['answerId'] = answ.get('Id')
                        answer['userNickname'] = answ.get('UserNickname')
                        answer['submissionTime'] = handle_date_from_json(
                            answ.get('SubmissionTime')
                        )
                        answer['lastModifiedTime'] = handle_date_from_json(
                            answ.get('LastModificationTime')
                        )
                        answer_list.append(answer)
                    question_info['answers'] = answer_list

                question_info['totalAnswersCount'] = question.get('TotalAnswerCount')
                question_info['submissionDate'] = handle_date_from_json(
                    question.get('SubmissionTime')
                )

                recent_questions.append(question_info)
        except:
            self.log(traceback.format_exc())
        if recent_questions:
            product['recent_questions'] = recent_questions

        return Request(self.REDSKY_API_URL.format(tcin, self.store),
                       callback=self.parse_pre_product_page,
                       meta=response.meta)

    @staticmethod
    def _product_id_v2(response_or_url):
        if not isinstance(response_or_url, (str, unicode)):
            response_or_url = response_or_url.url
        # else get it from the url
        _id = re.search('A-(\d+)', response_or_url)
        if _id:
            return _id.group(1)

    @staticmethod
    def _item_info_v3_image(image_info):
        base_url = image_info.get('base_url')
        image_id = image_info.get('primary')
        return base_url + image_id

    @staticmethod
    def _item_info_v3_price(amount, currency='USD'):
        if amount:
            return Price(priceCurrency=currency, price=amount)

    @staticmethod
    def _item_info_v3_price_helper(item):
        amount = item.get(
            'price', {}).get('offerPrice', {}).get(
            'formattedPrice', '').replace('$', '').replace(',', '')
        if not amount or 'see low price in cart' in amount:
            amount = item.get(
                'price', {}).get('offerPrice', {}).get('price')
        try:
            return float(amount)
        except ValueError:
            return 0

    def _item_info_v3_store_only(self, item):
        try:
            return item.get('available_to_promise_network') \
                       .get('availability') == 'UNAVAILABLE'
        except:
            self.log('Can not extract available status, probably item INLA: {}'.format(
                traceback.format_exc())
            )
            return False

    @staticmethod
    def _item_info_v3_reviews(item_info):
        tcin = item_info.get('item', {}).get('tcin')
        rating_review = item_info.get(
            'rating_and_review_statistics', {}).get('result', {}).get(tcin, {}).get('coreStats', {})
        average_rating = rating_review.get('AverageOverallRating', 0)
        num_of_reviews = rating_review.get('RatingReviewTotal', 0)
        rating_distribution = rating_review.get('RatingDistribution', [])
        rating_by_star = {i: 0 for i in range(1, 6)}
        rating_new = {i.get('RatingValue'): i.get('Count') for i in rating_distribution}
        rating_by_star.update(rating_new)
        reviews = BuyerReviews(int(num_of_reviews), round(float(average_rating), 1), rating_by_star)
        return reviews

    def _item_info_v3_availability(self, item):
        try:
            return item.get('available_to_promise_network', {}).get('availability_status') == 'IN_STOCK' \
                   or item.get('available_to_promise_network', {}).get('availability_status') == 'LIMITED_STOCK'
        except:
            self.log('Can not extract available status, probably item INLA: {}'.format(
                traceback.format_exc())
            )
            return False

    def _item_info_v3_variants(self, item_info, product):
        items = item_info.get('item', {}).get('child_items', [])
        variants = []
        for item in items:
            selected = item.get('tcin') == product.get('tcin')
            variant = self._item_info_v3_variant(item, selected)
            variants.append(variant)
        # CON-35037
        if variants and not any(variant.get('selected') for variant in variants):
            variants[0]['selected'] = True
            product['tcin'] = variants[0]['tcin']
        return variants

    def _item_info_v3_variant(self, item, selected):
        variant = {}
        variant['selected'] = selected
        variant['dpci'] = item.get('dpci')
        variant['tcin'] = item.get('tcin')
        variant['upc'] = item.get('upc')
        variant['properties'] = {}
        properties = item.get('variation', [])
        for attribute in properties:
            attribute_value = properties.get(attribute)
            if isinstance(attribute_value, (basestring, int, float)):
                variant['properties'][attribute] = attribute_value
        variant['price'] = self._item_info_v3_price_helper(item)
        image_info = item.get('enrichment', {}).get('images')[0]
        variant['image_url'] = self._item_info_v3_image(image_info)
        variant['is_in_store_only'] = self._item_info_v3_store_only(item)
        variant['in_stock'] = item.get('available_to_promise_network', {}).get('availability_status', {}) == 'IN_STOCK'
        return variant

    @staticmethod
    def _get_giftcards_data(item_info, product, selected_tcin=None):
        if selected_tcin:
            item = item_info.get('item')
            child_items_list = item.get("child_items", [])
            selected_item = [i for i in child_items_list if i.get('tcin', '') == selected_tcin[0]]
            promotion_list = selected_item[0].get('promotion', {}).get('promotionList', [])
        else:
            promotion_list = item_info.get('promotion', {}).get('promotionList', [])
        for promo in promotion_list:
            promo_text = promo.get('longTagSpecialOffer', '')
            giftcard = re.search('\s?(\$?)(\d+\.?\d?\d?)\s?giftcard', promo_text)
            if giftcard:
                giftcard = giftcard.groups()
                product['gift_card_currency'] = giftcard[0]
                giftcard_amount = float(giftcard[-1])
                product['gift_card_value'] = giftcard_amount

    def _populate_from_v3(self, response, product, item_info):
        item = item_info.get('item')
        not_found_list = ['Unauthorized', 'Resource Not Found', 'Forbidden']
        if item and not any(x in item.get('message', '') for x in not_found_list):
            variants = self._item_info_v3_variants(item_info, product)
            product['title'] = item.get('product_description', {}).get('title')
            brand = item.get('product_brand', {}).get('manufacturer_brand')
            if brand:
                product['brand'] = guess_brand_from_first_words(brand)
                if not product['brand']:
                    product['brand'] = brand
            else:
                if product['title']:
                    product['brand'] = guess_brand_from_first_words(product['title'])
            product['buyer_reviews'] = self._item_info_v3_reviews(item_info)
            if variants:
                product['variants'] = variants
                selected_tcin = [v.get("tcin", '') for v in variants if v.get("selected")]
                if selected_tcin:
                    self._get_giftcards_data(item_info, product, selected_tcin)
            else:
                self._get_giftcards_data(item_info, product)
            product['origin'] = item.get('country_of_origin')
            selected_variant = filter(lambda x: x['selected'], product.get('variants', []))

            if selected_variant:
                selected_variant = selected_variant[0]
                product['image_url'] = selected_variant.get('image_url')
                amount = selected_variant.get('price')
                amount = float(amount) if amount else None
                product['price'] = self._item_info_v3_price(amount)
                product['dpci'] = selected_variant.get('dpci')
                cond_set_value(product, 'upc', selected_variant.get('upc'))
                product['is_in_store_only'] = selected_variant.get('is_in_store_only')
                product['is_out_of_stock'] = not (selected_variant.get('in_stock'))
            else:
                amount = self._item_info_v3_price_helper(item_info)
                product['price'] = self._item_info_v3_price(amount)

                # Parse subscribe&save option
                product['subscription_price'] = None
                promotions = item_info.get('promotion', {}).get('promotionList', [])
                subscribe_promo = [promotion for promotion in promotions if
                                   promotion.get('subscriptionType') == 'SUBSCRIPTION']
                if subscribe_promo:
                    subscribe_promo = subscribe_promo[0]
                    if subscribe_promo.get('rewardType') == 'PercentageOff':
                        sub_save_value = subscribe_promo.get('rewardValue')
                        if sub_save_value:
                            product['subscription_price'] = format((1 - sub_save_value / 100) * amount, ".2f")
                            product['subs_discount_percent'] = format(sub_save_value, ".0f")

                product['dpci'] = item.get('dpci')
                cond_set_value(product, 'upc', item.get('upc'))
                image_info = item.get('enrichment', {}).get('images', {})[0]
                product['image_url'] = self._item_info_v3_image(image_info)
                product['is_in_store_only'] = self._item_info_v3_store_only(item_info)
                product['is_out_of_stock'] = not (self._item_info_v3_availability(item_info))

            product['secondary_id'] = product.get('dpci')

            giftcard_amount = product.get('gift_card_value')
            if amount and giftcard_amount:
                product['price_after_gift_card'] = max(round(amount - giftcard_amount, 2), 0.00)

            product_id = re.search(r'\d+', product.get('reseller_id', ''))

            if product_id and product.get('is_in_store_only'):
                meta = response.meta
                meta['product'] = product

                return Request(
                    url=self.AVAILABILITY_URL.format(product_id=product_id.group(), zip_code=self.zip_code),
                    meta=meta,
                    callback=self._parse_is_in_store_only
                )
        else:
            product['not_found'] = True
            product['no_longer_available'] = True

        return product

    def _parse_is_in_store_only(self, response):
        product = response.meta.get('product')
        locations = None
        try:
            locations = json.loads(response.body)['products'][0].get('locations', [])
        except:
            self.log(traceback.format_exc(), DEBUG)

        if locations:
            for location in locations:
                status = location.get('availability_status')
                if status != 'NOT_SOLD_IN_STORE' and status != 'DISCONTINUED':
                    product['is_in_store_only'] = False
                    break

        return product

    @staticmethod
    def _get_price_v2(item_info):
        """ Returns (price, in cart) """
        in_cart = False
        offer = item_info.get('Offers', [{}])[0].get('OfferPrice', [{}])[0]
        try:
            if 'low to display' in offer['formattedPriceValue'].lower():
                # in-cart pricing
                offer = item_info.get('Offers', [{}])[0].get('OriginalPrice', [{}])[0]
                in_cart = True
        except:
            pass
        price = Price(
            priceCurrency=offer['currencyCode'],
            price=offer['formattedPriceValue'].split(' -', 1)[0].replace('$', ''))
        return price, in_cart

    def _extract_links_with_brand(self, containers):
        bi_list = []
        for ci in containers:
            link = ci.xpath(
                "*[@class='productClick productTitle']/@href").extract()
            if link:
                link = link[0]
            else:
                self.log("no product link in %s" % ci.extract(), DEBUG)
                continue
            brand = ci.xpath(
                "*//a[contains(@class,'productBrand')]/text()").extract()
            if brand:
                temp_brand = guess_brand_from_first_words(brand[0])
                brand = temp_brand if temp_brand else brand[0]
            else:
                brand = ""
            isonline = ci.xpath(
                "../div[@class='rating-online-cont']"
                "/div[@class='onlinestorecontainer']"
                "/div/p/text()").extract()
            if isonline:
                isonline = isonline[0].strip()

            # TODO: isonline: u'out of stock online'
            # ==  'out of stock' & 'online'
            price = ci.xpath(
                './div[@class="pricecontainer"]/p/text()').re(FLOATING_POINT_RGEX)
            if price:
                price = price[0]
            else:
                price = ci.xpath(
                    './div[@class="pricecontainer"]/span[@class="map"]/following::p/span/text()') \
                    .re(FLOATING_POINT_RGEX)
                if price:
                    price = price[0]

            bi_list.append((brand, link, isonline, price))
        return bi_list

    def _is_search_v2(self, response):
        return "search_results/v2/by_keyword" in response.url

    def _scrape_product_links(self, response):
        data = json.loads(response.body)
        for item in data.get('search_response', {}).get('items', {}).get('Item', []):
            product = TargetProductItem()
            url = urlparse.urljoin(
                'https://www.target.com',
                item.get('url', '')
            )

            cond_set_value(product, 'title', item.get('title'))
            cond_set_value(product, 'tcin', item.get('tcin'))
            brand_field = item.get('brand')
            if brand_field:
                brand = guess_brand_from_first_words(brand_field)
                if not brand:
                    brand = brand_field
            else:
                if item.get('title'):
                    brand = guess_brand_from_first_words(item.get('title'))
            cond_set_value(product, 'brand', brand)
            cond_set_value(product, 'brand', item.get('brand'))
            cond_set_value(product, 'in_store_pickup', item.get('pick_up_in_store'))

            new_meta = copy.deepcopy(response.meta)
            new_meta['product'] = product
            yield (Request(url, callback=self.parse_product, meta=new_meta,
                           headers={'User-Agent': self.user_agent_override}),
                   product)

    def _scrape_product_links_json(self, response):
        for item in self._get_json_data(response)['items']['Item']:
            url = item['productDetailPageURL']
            url = urlparse.urljoin('http://www.target.com', url)
            product = TargetProductItem()
            attrs = item.get('itemAttributes', {})
            cond_set_value(product, 'title', attrs.get('title'))
            cond_set_value(product, 'brand',
                           attrs.get('productManufacturerBrand'))
            p = item.get('priceSummary', {})
            priceattr = p.get('offerPrice', p.get('listPrice'))
            if priceattr:
                currency = priceattr['currencyCode']
                amount = priceattr['amount']
                if amount == 'Too low to display':
                    price = None
                else:
                    amount = is_empty(re.findall(
                        '\d+\.{0,1}\d+', priceattr['amount']
                    ))
                    price = Price(priceCurrency=currency, price=amount)
                cond_set_value(product, 'price', price)
            new_meta = copy.deepcopy(response.meta)
            new_meta['product'] = product
            yield (Request(url, callback=self.parse_product, meta=new_meta,
                           headers={'User-Agent': self.user_agent_override}),
                   product)

    def _get_json_data(self, response):
        data = re.search('getPlpResponse\((.+)\)', response.body_as_unicode())
        try:
            if data is not None:
                data = json.loads(data.group(1))
            else:
                data = json.loads(response.body_as_unicode())
        except (ValueError, TypeError, AttributeError):
            self.log('JSON response expected.')
            return
        return data['searchResponse']

    def _scrape_total_matches(self, response):
        if response.meta.get('json'):
            return self._scrape_total_matches_json(response)

        elif self._is_search_v2(response):
            return self._scrape_total_matches_json_2(response)

        total = self._scrape_total_matches_json_v1(response)
        if total:
            return total

        return self._scrape_total_matches_html(response)

    def _scrape_total_matches_json_v1(self, response):
        try:
            data = json.loads(response.body)
            args = self._json_get_args_v1(data['search_response']['metaData'])
            return int(args['total_results'])
        except:
            self.log(traceback.format_exc(), DEBUG)

    def _json_get_args_v1(self, data):
        args = {d['name']: d['value'] for d in data}
        return args

    def _json_get_args(self, data):
        args = {d['name']: d['value'] for d in
                data['searchState']['Arguments']['Argument']}
        return args

    def _scrape_total_matches_json_2(self, response):
        try:
            data = json.loads(response.body)
            args = self._json_get_args(data['searchResponse'])
            if 'prodCount' not in data['searchResponse']:
                return 0
            return int(args.get('prodCount'))
        except:
            self.log(traceback.format_exc(), DEBUG)

    def _scrape_total_matches_json(self, response):
        try:
            data = self._get_json_data(response)
            return int(self._json_get_args(data)['prodCount'])
        except:
            self.log(traceback.format_exc(), DEBUG)

    def _scrape_total_matches_html(self, response):
        str_results = response.xpath(
            "//div[@id='searchMessagingHeader']/h2"
            "/span/span[@class='srhCount']/text()")

        num_results = str_results.re('(\d+)\s+result')
        if num_results:
            try:
                return int(num_results[0])
            except ValueError:
                self.log(
                    "Failed to parse total number of matches: %r"
                    % num_results[0],
                    DEBUG
                )
                return None
        else:
            if any('related' in f or u'no\xa0results\xa0found' in f
                   for f in str_results.extract()):
                return 0

        self.log("Failed to parse total number of matches.", DEBUG)
        return None

    def _gen_next_request(self, response, next_page, remaining=None):
        next_page = urllib.unquote(next_page)
        data = {'formData': next_page,
                'stateData': "",
                'isDLP': 'false',
                'response_group': 'Items'
                }

        new_meta = response.meta.copy()
        if 'total_matches' not in new_meta:
            new_meta['total_matches'] = self._scrape_total_matches(response)
        if remaining and remaining > 0:
            new_meta['remaining'] = remaining
        post_url = "http://www.target.com/SoftRefreshProductListView"
        # new_meta['json'] = True

        return FormRequest(
            # return FormRequest.from_response(
            # response=response,
            url=post_url,
            method='POST',
            formdata=data,
            callback=self._parse_link_post,
            meta=new_meta,
            headers={'User-Agent': self.user_agent_override})

    def _parse_link_post(self, response):
        jsdata = json.loads(response.body)
        pagination1 = jsdata['productListArea']['pagination1']
        sel = Selector(text=pagination1.encode('utf-8'))

        next_page = sel.xpath(
            "//div[@id='pagination1']/div[@class='col2']"
            "/ul[@class='pagination1']/li[@class='next']/a/@href").extract()

        requests = []

        remaining = response.meta.get('remaining')
        plf = jsdata['productListArea']['productListForm']

        sel = Selector(text=plf.encode('utf-8'))
        containers = sel.xpath("//div[@class='tileInfo']")

        links = self._extract_links_with_brand(containers)

        if next_page:
            next_page = next_page[0]
            new_remaining = remaining - len(links)
            if new_remaining > 0:
                requests.append(self._gen_next_request(
                    response, next_page, remaining=new_remaining))

        for i, (brand, url, isonline, price) in enumerate(islice(links, 0, remaining)):
            new_meta = response.meta.copy()
            product = TargetProductItem(brand=brand)
            product['search_term'] = response.meta.get('search_term')
            product['site'] = self.site_name
            product['total_matches'] = response.meta.get('total_matches')
            product['results_per_page'] = len(links)
            product['url'] = url
            if isonline == 'out of stock':
                product['is_out_of_stock'] = True

            # The ranking is the position in this page plus the number of
            # products from other pages.
            ranking = (i + 1) + (self.quantity - remaining)
            product['ranking'] = ranking
            new_meta['product'] = product
            requests.append(Request(
                url,
                callback=self.parse_product,
                meta=new_meta, dont_filter=True,
                headers={'User-Agent': self.user_agent_override}), )
        return requests

    def _scrape_next_results_page_link(self, response):
        data = json.loads(response.body)
        args = data.get('search_response', {}).get('metaData', [])
        args_dict = dict((d.values()) for d in args)

        current_page_number = int(args_dict.get('currentPage', 0))
        total_pages_number = int(args_dict.get('totalPages', 0))
        if current_page_number < total_pages_number:
            next_offset = current_page_number * int(args_dict.get('count', 0))
            if args_dict.get('keyword'):
                search_term = args_dict.get('keyword')
                url = self.SEARCH_URL.format(
                    search_term=search_term).replace('offset=0', 'offset=%d' % next_offset)
                return Request(url, meta=response.meta, headers={'User-Agent': self.user_agent_override})
            elif args_dict.get('category'):
                category = args_dict.get('category')
                url = self.SEARCH_URL.format(
                    category=category).replace('offset=0', 'offset=%d' % next_offset)
                return Request(url, meta=response.meta, headers={'User-Agent': self.user_agent_override})

    def _scrape_next_results_page_link_html(self, response):
        next_page = response.xpath(
            "//div[@id='pagination1']/div[@class='col2']"
            "/ul[@class='pagination1']/li[@class='next']/a/@href |"
            "//li[contains(@class, 'pagination--next')]/a/@href"
        ).extract()
        if next_page:
            search = "?searchTerm=%s" % self.searchterms[0].replace(" ", "+")
            if search in next_page[0] and "page=" in next_page[0]:
                return next_page[0]
            next_page = next_page[0]
            return self._gen_next_request(response, next_page)

    def _parse_single_product(self, response):
        return self.parse_product(response)
