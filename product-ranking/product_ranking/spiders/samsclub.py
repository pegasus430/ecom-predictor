# -*- coding: utf-8 -*-#

from __future__ import absolute_import, division, unicode_literals

import json
import re
import string
import traceback
import urlparse
import urllib

from itertools import islice

from scrapy.http import Request
from scrapy.conf import settings
from scrapy.log import ERROR, WARNING, INFO

import spiders_shared_code.canonicalize_url
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.utils import upc_check_digit, handle_date_from_json
from product_ranking.spiders import (BaseProductsSpider, cond_set,
                                     cond_set_value)


class SamsclubProductsSpider(BaseProductsSpider):
    name = 'samsclub_products'
    allowed_domains = ["samsclub.com", "api.bazaarvoice.com"]
    start_urls = []

    user_agent = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 Firefox/55.0"
    handle_httpstatus_list = [301, 302]

    SEARCH_URL = "https://www.samsclub.com/sams/search/searchResults.jsp" \
                 "?searchCategoryId=all&searchTerm={search_term}&fromHome=no" \
                 "&_requestid=29417"

    SHIPPING_PRICES_URL = "https://www.samsclub.com/sams/shop/product/moneybox/" \
                          "shippingDeliveryInfo.jsp?zipCode={zip_code}&productId={prod_id}&skuId={sku}"

    NEXT_PAGE_PARAM = "&offset={results_per_next}&recordType=all"

    CLUB_SET_URL = "https://www.samsclub.com/api/soa/services/v1/profile/clubpreference/assignclub"

    PRICE_URL = "https://m.samsclub.com/api/sams/samsapi/v2/productInfo?repositoryId={}&class=product&loadType=full" \
                "&bypassEGiftCardViewOnly=true&clubId={}"

    _REVIEWS_URL = "http://api.bazaarvoice.com/data/batch.json?passkey=dap59bp2pkhr7ccd1hv23n39x&apiversion=5.5" \
                   "&displaycode=1337-en_us&resource.q0=products&filter.q0=id%3Aeq%3A{prod_id}&stats.q0=questions" \
                   "%2Creviews&filteredstats.q0=questions%2Creviews&filter_questions.q0=contentlocale%3Aeq%3Aen_US" \
                   "&filter_answers.q0=contentlocale%3Aeq%3Aen_US&filter_reviews.q0=contentlocale%3Aeq%3Aen_US" \
                   "&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen_US&resource.q1=questions&filter.q1=productid" \
                   "%3Aeq%3A{prod_id}&filter.q1=contentlocale%3Aeq%3Aen_US&sort.q1=totalanswercount%3Adesc" \
                   "&stats.q1=questions&filteredstats.q1=questions&include.q1=authors%2Cproducts%2Canswers" \
                   "&filter_questions.q1=contentlocale%3Aeq%3Aen_US&filter_answers.q1=contentlocale%3Aeq%3Aen_US" \
                   "&sort_answers.q1=totalpositivefeedbackcount%3Adesc%2Ctotalnegativefeedbackcount%3Aasc" \
                   "&offset.q1=0"

    PICK_CLUB_URL = 'https://www.samsclub.com/sams/shoppingtools/clubSelector/displayClubs.jsp' \
                    '?productId={product_id}&skuId={sku}&radius=50&address={zip_code}' \
                    '&redirectURL=/sams/shop/product.jsp?productId={product_id}&amp;selectedTab=allProducts'

    HEADERS = {
        'Accept-Language': 'en-US,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/66.0.3359.139 Safari/537.36',
        'x-forwarded-for': '127.0.0.1'
    }

    def __init__(self, *args, **kwargs):
        self.clubno = kwargs.pop('store', '4774')
        self.zip_code = kwargs.pop('zip_code', '07094')
        self.results_per_page = 48
        self.current_page = 1
        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        formatter = None
        super(SamsclubProductsSpider, self).__init__(
            formatter,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def start_requests(self):
        payload = {"payload": {"clubId": self.clubno}}
        yield Request(self.CLUB_SET_URL, callback=self.after_start_requests, method="POST", body=json.dumps(payload))

    def after_start_requests(self, response):
        if 'success":true' in response.body:
            self.log("Set up club number: {}".format(self.clubno), INFO)
        else:
            self.log("Failed to set club number: {}".format(response.body), WARNING)
        for request in super(SamsclubProductsSpider, self).start_requests():
            request = request.replace(headers=self.HEADERS, dont_filter=True)
            request.meta['dont_redirect'] = True
            yield request

    def parse(self, response):
        if self._search_page_error(response):
            if self.not_a_product(response):
                remaining = response.meta['remaining']
                search_term = response.meta['search_term']

                self.log("For search term '%s' with %d items remaining,"
                         " failed to retrieve search page: %s"
                         % (search_term, remaining, response.request.url),
                         WARNING)
            else:
                prod = SiteProductItem()
                prod['is_single_result'] = True
                prod['url'] = response.url
                prod['search_term'] = response.meta['search_term']

                yield Request(
                    prod['url'],
                    callback=self._parse_single_product,
                    meta={'product': prod},
                    dont_filter=True,
                    headers=self.HEADERS
                )
        else:
            prods_count = -1  # Also used after the loop.
            for prods_count, request_or_prod in enumerate(
                    self._get_products(response)):
                yield request_or_prod
            prods_count += 1  # Fix counter.

            request = self._get_next_products_page(response, prods_count)
            if request is not None:
                yield request

    def _search_page_error(self, response):
        if not self._scrape_total_matches(response):
            self.log("Samsclub: unable to find a match", ERROR)
            return True
        return False

    def not_a_product(self, response):
        if response.xpath("//div[@class='container' and @itemtype='http://schema.org/Product']").extract():
            return False
        return True

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.samsclub(url)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta.get('product')

        if response.status in [301, 302]:
            cond_set_value(product, 'is_redirected', True)
            return product

        cond_set(
            product,
            'brand',
            response.xpath(
                "//div[contains(@class,'prodTitlePlus')]"
                "/span[@itemprop='brand']/text()"
            ).extract())
        if not product.get('brand', None):
            cond_set(
                product,
                'brand',
                response.xpath(
                    '//*[@itemprop="brand"]//span/text()').extract())

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        image_url = response.xpath("//div[@id='plImageHolder']/img/@src").extract()
        if image_url:
            image_url = 'https:' + image_url[0]
            product['image_url'] = image_url

        reseller_id = self._extract_reseller_id(response.url)
        cond_set_value(
            product,
            "reseller_id",
            reseller_id
        )

        cond_set_value(product, 'store', self.clubno)

        cond_set_value(product, 'zip_code', self.zip_code)

        cond_set(product, 'model', response.xpath(
            "//span[@itemprop='model']/text()").extract(),
                 conv=string.strip)
        if product.get('model', '').strip().lower() == 'null':
            product['model'] = ''

        sold_out = response.xpath('//*[@itemprop="availability" and @href="http://schema.org/SoldOut"]')
        inla = True if (not response.body or sold_out) else False
        cond_set_value(product, 'no_longer_available', inla)

        out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        pickup = response.xpath('//li[contains(@class, "pickupIcon")]').extract()
        pickup = True if pickup and not self._parse_in_stores(response) else False

        cond_set_value(product, 'in_store_pickup', pickup)

        product['locale'] = "en-US"

        # Categories
        categorie_filters = [u'sam\u2019s club']
        # Clean and filter categories names from breadcrumb
        bc = response.xpath('//*[@id="breadcrumb"]//a/text()').extract()
        bc = [b.strip() for b in bc if b.strip()]
        if not bc or len(bc) == 1:
            bc = response.xpath(".//*[@id='breadcrumb']//text()").extract()
        bc = [b.strip() for b in bc if b.strip()]
        if not bc:
            bc = response.xpath('//*[@id="breadcrumb"]//a//*[@itemprop="title"]/text() | '
                                '//*[contains(@class, "breadcrumb")]//a/text()').extract()
        bc = [b.strip() for b in bc if b.strip()]
        categories = list(filter((lambda x: x.lower() not in categorie_filters),
                                 map((lambda x: x.strip()), bc)))
        category = categories[-1] if categories else None
        cond_set_value(product, 'categories', categories)
        cond_set_value(product, 'department', category)

        # Subscribe and save
        subscribe_and_save = response.xpath('//*[@class="subscriptionDiv" and \
                not(@style="display: none;")]/input[@id="pdpSubCheckBox"]')
        cond_set_value(product,
                       'subscribe_and_save',
                       1 if subscribe_and_save else 0)

        # Shpping
        shipping_included = response.xpath('//*[@class="freeDelvryTxt"]')
        cond_set_value(product,
                       'shipping_included',
                       1 if shipping_included else 0)

        oos_in_both = response.xpath("//div[@class='biggraybtn']/text()").extract()
        if oos_in_both:
            oos_in_both = oos_in_both[0]

        # Available in Store
        available_store = response.xpath(
            '//*[(@id="addtocartsingleajaxclub" or'
            '@id="variantMoneyBoxButtonInitialLoadClub")'
            'and contains(text(),"Pick up in Club")]') or \
                          response.xpath(
                              '//li[contains(@class,"pickupIcon")]'
                              '/following-sibling::li[contains'
                              '(translate(text(), "ABCDEFGHIJKLMNOPQRSTUVWXYZ",'
                              ' "abcdefghijklmnopqrstuvwxyz"),"ready as soon as")]')

        cond_set_value(product,
                       'available_store',
                       1 if available_store and not oos_in_both else 0)

        # Available Online
        available_online = response.xpath('//*[(@id="addtocartsingleajaxonline" \
                or @id="variantMoneyBoxButtonInitialLoadOnline")]')
        cond_set_value(product,
                       'available_online',
                       1 if available_online else 0)

        in_stores = self._parse_in_stores(response)
        cond_set_value(product, 'is_in_store_only', in_stores)

        if not shipping_included and not product.get('no_longer_available'):
            productId = reseller_id
            pSkuId = ''.join(response.xpath('//*[@id="mbxSkuId"]/@value').extract())
            if not pSkuId:
                regex_match = re.search('''skuId[\"']\:[\"']([^'\"]+)''', response.body)
                if regex_match:
                    pSkuId = regex_match.group(1)
            # This is fixing bug with sku and prod_id extraction for bundle products
            if not pSkuId:
                js_sku_prodid = response.xpath(
                    './/script[contains(text(), "var skuId") and contains(text(), "var productId")]/text()').extract()
                js_sku_prodid = ''.join(js_sku_prodid) if js_sku_prodid else None
                if js_sku_prodid:
                    rgx = r'(prod\d+)'
                    match_list = re.findall(rgx, js_sku_prodid)
                    productId = match_list[0] if match_list else None
                    rgx = r'(sku\d+)'
                    match_list = re.findall(rgx, js_sku_prodid)
                    pSkuId = match_list[0] if match_list else None

            cond_set_value(product, 'sku', pSkuId)

            return Request(self.SHIPPING_PRICES_URL.format(zip_code=self.zip_code, prod_id=productId, sku=pSkuId),
                           meta={'product': product, 'prod_id': productId},
                           callback=self._parse_shipping_cost,
                           headers=self.HEADERS
                           )

        productId = reseller_id
        reviews_url = self._REVIEWS_URL.format(prod_id=productId)
        return Request(reviews_url,
                       meta={'product': product, 'prod_id': productId},
                       callback=self._load_reviews,
                       headers={
                           'Accept': '*/*',
                           'Accept-Encoding': 'gzip, deflate, br',
                           'Accept-Language': 'en-US,en;q=0.8',
                           'Connection': 'keep-alive',
                           'Host': 'api.bazaarvoice.com',
                           'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                         'Chrome/66.0.3359.139 Safari/537.36'
                       })

    def _parse_shipping_cost(self, response):
        product = response.meta['product']
        productId = product.get('reseller_id')
        shipping_list = []
        shipping_blocks = response.xpath('//tr')
        for block in shipping_blocks:
            name_l = block.xpath('./td//span/text()').extract()
            name = name_l[0] if name_l else None
            cost = block.xpath('.//*[contains(text(), "$")]/text()').re('[\d\.\,]+')
            cost = cost[0] if cost else None
            if not cost:
                if block.xpath('./*[contains(text(), "FREE")]').extract() or 'FREE' in name_l:
                    cost = '0'
                else:
                    cost = None
            if cost and name:
                shipping_list.append({'name': name, 'cost': cost})
        product['shipping'] = shipping_list

        if not product.get('buyer_reviews'):
            reviews_url = self._REVIEWS_URL.format(prod_id=productId)
            yield Request(reviews_url,
                          meta={'product': product, 'prod_id': productId},
                          callback=self._load_reviews)
        else:
            url = self.PRICE_URL.format(product.get('reseller_id'), self.clubno)

            # must be requested last to return product data
            yield Request(url, meta=response.meta, callback=self._extract_price, priority=-1)

    def _parse_out_of_stock(self, response):
        availability = response.xpath("//*[@itemprop='availability']/@href").extract()
        if availability:
            if availability[0] == "http://schema.org/OutOfStock":
                return True
        return False

    def _parse_title(self, response):
        title = response.xpath("//div[contains(@class,'prodTitle')]"
                               "/h1/span[@itemprop='name']/text()").extract()
        if not title:
            title = response.xpath("//li[@class='breadcrumb active']//h1/text()").extract()

        return title[0] if title else None

    def _load_reviews(self, response):
        product_id = response.meta.get('prod_id')
        product = response.meta['product']
        buyer_reviews = {}

        contents = response.body_as_unicode()
        try:
            tmp_reviews = re.findall(r'<span class=\\"BVRRHistAbsLabel\\">(.*?)<\\/span>', contents)
            if not tmp_reviews:
                raise BaseException
            reviews = []
            for review in tmp_reviews:
                review = review.replace(",", "")
                m = re.findall(r'([0-9]+)', review)
                reviews.append(m[0])

            reviews = reviews[:5]

            by_star = {}

            score = 1
            total_review = 0
            review_cnt = 0
            for review in reversed(reviews):
                by_star[str(score)] = int(review)
                total_review += score * int(review)
                review_cnt += int(review)
                score += 1
            # filling missing scores with zero count for consistency
            for sc in range(1, 6):
                if str(sc) not in by_star:
                    by_star[str(sc)] = 0

            review_count = review_cnt

            buyer_reviews['rating_by_star'] = by_star

            buyer_reviews['num_of_reviews'] = review_count
            average_review = total_review * 1.0 / review_cnt
            # rounding
            average_review = float(format(average_review, '.2f'))

            buyer_reviews['average_rating'] = average_review
            product['buyer_reviews'] = BuyerReviews(**buyer_reviews)
            if review_count == 0:
                raise BaseException  # we have to jump to the version #2
        except:
            ## TODO rework to use tmtext/product-ranking/product_ranking/br_bazaarvoice_api_script.py
            if not product.get('buyer_reviews'):
                try:
                    review_json = json.loads(response.body)
                    main_info = review_json["BatchedResults"]["q0"]["Results"][0]
                    review_statistics = main_info['FilteredReviewStatistics']

                    qa_data = review_json["BatchedResults"]["q1"]

                    if qa_data.get('Results'):
                        self._parse_qa_data(qa_data, response)
                    else:
                        product['recent_questions'] = []

                    last_data_question = main_info['QAStatistics']['LastQuestionTime']

                    if last_data_question:
                        last_data_question = handle_date_from_json(last_data_question)
                        product['date_of_last_question'] = last_data_question

                    if review_statistics.get("RatingDistribution", None):
                        by_star = {}
                        for item in review_statistics['RatingDistribution']:
                            by_star[str(item['RatingValue'])] = item['Count']
                        for sc in range(1, 6):
                            if str(sc) not in by_star:
                                by_star[str(sc)] = 0

                        buyer_reviews["rating_by_star"] = by_star

                    if review_statistics.get("TotalReviewCount", None):
                        buyer_reviews["num_of_reviews"] = review_statistics["TotalReviewCount"]

                    if review_statistics.get("AverageOverallRating", None):
                        buyer_reviews["average_rating"] = format(review_statistics["AverageOverallRating"], '.1f')
                except Exception as e:
                    self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
                finally:
                    if buyer_reviews:
                        product['buyer_reviews'] = BuyerReviews(**buyer_reviews)
                    else:
                        product['buyer_reviews'] = ZERO_REVIEWS_VALUE

        if not product.get('buyer_reviews'):
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE

        url = self.PRICE_URL.format(product.get('reseller_id'), self.clubno)

        # must be requested last to return product data
        return Request(url, meta=response.meta, callback=self._extract_price)

    def _parse_qa_data(self, qa_data, response):
        product = response.meta['product']
        question_data = qa_data.get('Results')
        answer_data = qa_data.get('Includes')
        recent_questions = []

        if answer_data:
            answer_data = answer_data.get('Answers')

        for question in question_data:
            question_info = {}
            question_info['questionId'] = question.get('Id')
            question_info['userNickname'] = question.get('UserNickname')
            question_info['questionSummary'] = question.get('QuestionSummary')

            # Get answers by answer_ids
            answer_ids = question.get('AnswerIds')
            if answer_ids:
                answers = []
                for answer_id in answer_ids:
                    answ = answer_data.get(answer_id)
                    if answ:
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
                        answers.append(answer)
                question_info['answers'] = answers

            question_info['totalAnswersCount'] = question.get('TotalAnswerCount')
            question_info['submissionDate'] = handle_date_from_json(
                question.get('SubmissionTime')
            )

            recent_questions.append(question_info)

        if recent_questions:
            product['recent_questions'] = recent_questions

    def _extract_upc_value(self, product_data):
        upc = product_data.get('sa', [{}])[0].get('upc')
        if upc:
            return upc_check_digit(upc.zfill(11)[-12:])
        return None

    def _extract_sku_value(self, product_data):
        sku = product_data.get('sa', [{}])[0].get('id')
        return sku if sku else None

    @staticmethod
    def _parse_in_stores(response):
        return bool(response.xpath('.//*[@class="twoChannel"]'))

    @staticmethod
    def _parse_colors(response):
        colors = response.xpath("//ul[@class='colorSwatches allSwct']//span//img/@alt").extract()
        if not colors:
            colors = response.xpath("//span[@class='variant-swatch']/text()").extract()
        return colors

    def _scrape_total_matches(self, response):
        if response.url.find('ajaxSearch') > 0:
            items = response.xpath("//a[@class='shelfProdImgHolder']/@href")
            return len(items)

        totals = response.xpath("//div[contains(@class,'shelfSearchRelMsg2')]"
                                "/span/span[@class='gray3']/text()").extract()
        if not totals:
            totals = response.xpath('//div[@class="sc-page-range-label"]/text()').re('of (\d+)')
        if not totals:
            totals = response.xpath('//*[@class="resultsfound"]/span[@ng-show="!clientAjaxCall"]/text()').extract()
        if not totals:
            totals = response.xpath('//*[contains(@class, "resultsFound")]//b/text()').extract()
        if totals:
            total = int(totals[0])
        elif response.css('.nullSearchShelfZeroResults'):
            total = 0
        else:
            total = response.xpath('//text()').re("'totalRecords':'(\d+)'")
            if total:
                return int(total[0])
        return total if total else None

    def _scrape_product_links(self, response):
        if response.url.find('ajaxSearch') > 0:
            links = response.xpath("//body/ul/li/a/@href").extract()
        else:
            links = response.xpath(
                "//ul[contains(@class,'shelfItems')]"
                "/li[contains(@class,'item')]/a/@href"
            ).extract()

        if not links:
            links = response.xpath(
                "//a[@class='cardProdLink' or @class='cardProdLink ng-scope' or "
                "@class ='sc-product-card-image-container']/@href").extract()

        if not links:
            links = response.xpath('//div[@class="sc-product-card-title"]/a/@href').extract()

        if not links:
            self.log("Found no product links.", WARNING)

        for link in links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_next_results_page_link(self, response, remaining):
        total_matches = self._scrape_total_matches(response)
        results_per_next = self.current_page * self.results_per_page
        st = response.meta.get('search_term')

        if not total_matches:
            return
        if results_per_next > total_matches:
            return
        self.current_page += 1
        next_page_param = self.NEXT_PAGE_PARAM.format(results_per_next=results_per_next)
        next_page_link = self.SEARCH_URL.format(search_term=st) + next_page_param
        if next_page_link:
            return Request(
                url=next_page_link,
                headers=self.HEADERS,
                dont_filter=True,
                meta={'search_term': st, 'remaining': self.quantity}
            )

    @staticmethod
    def _extract_reseller_id(url):
        reseller_id = re.search(r'prod\d+', url)

        if reseller_id:
            return reseller_id.group(0)

        if not reseller_id:
            reseller_id = re.search(r'/(\d+)\.ip', url)

        if reseller_id:
            return reseller_id.group(1)

    def _extract_price(self, response):
        meta = response.meta
        product = meta.get('product')
        try:
            product_data = json.loads(response.body_as_unicode())
        except:
            self.log(traceback.format_exc())
        else:
            cond_set_value(product, 'price', self._extract_price_value(product_data))
            cond_set_value(product, 'save_amount', self._extract_price_save(product_data))
            cond_set_value(product, 'variants', self._extract_variants(product_data))
            cond_set_value(product, 'upc', self._extract_upc_value(product_data))
            cond_set_value(product, 'sku', self._extract_sku_value(product_data))
            cond_set_value(product, 'price_details_in_cart', self._extract_price_details_in_cart(product_data))

        prod_id = product.get('reseller_id')

        prod_name = 'foo'
        canonical_link = product.get('url')
        if canonical_link:
            prod_name = canonical_link.split('/')[-2]
            if '%' in prod_name:
                prod_name = urllib.quote(prod_name)

        if prod_id:
            meta['product'] = product
            mobile_url = 'https://m.samsclub.com/ip/{0}/{1}'.format(prod_name, prod_id)
            return Request(
                url=mobile_url,
                meta=meta,
                callback=self._parse_out_of_stock_alternate
            )

        return product

    def _parse_out_of_stock_alternate(self, response):
        meta = response.meta
        product = response.meta.get('product')
        product_json = {}
        out_of_stock = False

        try:
            product_json = json.loads(
                re.search('window.__WML_REDUX_INITIAL_STATE__\s*=\s*({.*?});', response.body).group(1)
            )
        except:
            self.log(traceback.format_exc())

        if product_json:
            inventory = product_json.get('product', {}).get('selectedSku', {}).get('inventoryOptions')
            if inventory:
                if inventory[0].get('status') == 'outOfStock':
                    out_of_stock = True
            else:
                out_of_stock = True

        product['is_out_of_stock'] = out_of_stock

        product_id = product.get('reseller_id')
        sku = product.get('sku')

        if product_id and sku:
            meta['product'] = product
            return Request(
                url=self.PICK_CLUB_URL.format(product_id=product_id, sku=sku, zip_code=self.zip_code),
                meta=meta,
                headers=self.HEADERS,
                callback=self._parse_in_store_pickup
            )

        return product

    @staticmethod
    def _parse_in_store_pickup(response):
        product = response.meta.get('product')
        product['in_store_pickup'] = bool(
            response.xpath('//span[@id="inStock" and contains(text(), "In Stock")]')
        )

        return product

    @staticmethod
    def _extract_price_details_in_cart(product_data):
        if product_data.get('sa'):
            return bool(product_data.get('sa')[0].get('mo') == '3')
        return False

    @staticmethod
    def _extract_variants(product_data):
        variants = []
        variants_data = product_data.get('sa', [])
        default_upc = None
        if variants_data:
            default_upc = upc_check_digit(variants_data[0].get('upc'))
        for variant in variants_data:
            price = variant.get('dp')
            if not price:
                price = variant.get('ip')
            variants.append(
                {
                    'properties': {
                                      variant_property[0].lower(): variant_property[1]
                                      for variant_properties in variant.get('cfgd', [])
                                      for variant_property in variant_properties.items()
                                  } or None,
                    'price': float(price.replace('$', '').replace(',', '')) if price else None,
                    'upc': upc_check_digit(variant.get('upc')) if variant.get('upc') else default_upc,
                    'in_stock': bool(variant.get('onlineInv', {}).get('status')),
                    'image_url': variant.get('li') or None,
                    'sku': variant.get('id') or None
                }
            )

        return variants if len(variants) > 1 else None

    def _extract_price_value(self, product_data):
        price = '0'
        try:
            prices = product_data.get('sa')[0]
        except:
            self.log(traceback.format_exc())
        else:
            if prices.get('onlinePrice').get('listPrice'):
                price = prices.get('onlinePrice').get('listPrice')
            elif prices.get('onlinePrice').get('finalPrice'):
                price = prices.get('onlinePrice').get('finalPrice')
            elif prices.get('clubPrice').get('listPrice'):
                price = prices.get('clubPrice').get('listPrice')
            elif prices.get('clubPrice').get('finalPrice'):
                price = prices.get('clubPrice').get('finalPrice')
        price = float(price.replace('$', '').replace(',', ''))
        return Price(price=price, priceCurrency='USD')

    def _extract_price_save(self, product_data):
        try:
            prices = product_data.get('sa')[0]
            price = prices.get('onlinePrice').get('amountSaved')
            price = float(price.replace('$', '').replace(',', ''))
        except:
            price = 0
        return price

    def _get_next_products_page(self, response, prods_found):
        link_page_attempt = response.meta.get('link_page_attempt', 1)

        result = None
        if prods_found is not None:
            # This was a real product listing page.
            remaining = response.meta['remaining']
            remaining -= prods_found
            if remaining > 0:
                next_page = self._scrape_next_results_page_link(response, remaining)
                if next_page is None:
                    pass
                elif isinstance(next_page, Request):
                    next_page.meta['remaining'] = remaining
                    result = next_page
                else:
                    url = urlparse.urljoin(response.url, next_page)
                    new_meta = dict(response.meta)
                    new_meta['remaining'] = remaining
                    result = Request(url, self.parse, meta=new_meta, priority=1)
        elif link_page_attempt > self.MAX_RETRIES:
            self.log(
                "Giving up on results page after %d attempts: %s" % (
                    link_page_attempt, response.request.url),
                ERROR
            )
        else:
            self.log(
                "Will retry to get results page (attempt %d): %s" % (
                    link_page_attempt, response.request.url),
                WARNING
            )

            # Found no product links. Probably a transient error, lets retry.
            new_meta = response.meta.copy()
            new_meta['link_page_attempt'] = link_page_attempt + 1
            result = response.request.replace(
                meta=new_meta, cookies={}, dont_filter=True)

        return result

    def _get_products(self, response):
        remaining = response.meta['remaining']
        search_term = response.meta['search_term']
        prods_per_page = response.meta.get('products_per_page')
        total_matches = response.meta.get('total_matches')
        scraped_results_per_page = response.meta.get('scraped_results_per_page')

        prods = self._scrape_product_links(response)

        if prods_per_page is None:
            # Materialize prods to get its size.
            prods = list(prods)
            prods_per_page = len(prods)
            response.meta['products_per_page'] = prods_per_page

        if scraped_results_per_page is None:
            scraped_results_per_page = self._scrape_results_per_page(response)
            if scraped_results_per_page:
                self.log(
                    "Found %s products at the first page" % scraped_results_per_page
                    , INFO)
            else:
                scraped_results_per_page = prods_per_page
                if hasattr(self, 'is_nothing_found'):
                    if not self.is_nothing_found(response):
                        self.log(
                            "Failed to scrape number of products per page", WARNING)
            response.meta['scraped_results_per_page'] = scraped_results_per_page

        if total_matches is None:
            total_matches = self._scrape_total_matches(response)
            if total_matches is not None:
                response.meta['total_matches'] = total_matches
                self.log("Found %d total matches." % total_matches, INFO)
            else:
                if hasattr(self, 'is_nothing_found'):
                    if not self.is_nothing_found(response):
                        self.log(
                            "Failed to parse total matches for %s" % response.url, WARNING)

        if total_matches and not prods_per_page:
            # Parsing the page failed. Give up.
            self.log("Failed to get products for %s" % response.url, WARNING)
            return

        for i, (prod_url, prod_item) in enumerate(islice(prods, 0, remaining)):
            # Initialize the product as much as possible.
            prod_item['site'] = self.site_name
            prod_item['search_term'] = search_term
            prod_item['total_matches'] = total_matches
            prod_item['results_per_page'] = prods_per_page
            prod_item['scraped_results_per_page'] = scraped_results_per_page
            # The ranking is the position in this page plus the number of
            # products from other pages.
            prod_item['ranking'] = (i + 1) + (self.quantity - remaining)
            if self.user_agent_key not in ["desktop", "default"]:
                prod_item['is_mobile_agent'] = True

            if prod_url is None:
                # The product is complete, no need for another request.
                yield prod_item
            elif isinstance(prod_url, Request):
                cond_set_value(prod_item, 'url', prod_url.url)  # Tentative.
                yield prod_url
            else:
                # Another request is necessary to complete the product.
                url = urlparse.urljoin(response.url, prod_url)
                cond_set_value(prod_item, 'url', url)  # Tentative.

                yield Request(
                    url,
                    callback=self.parse_product,
                    meta={'product': prod_item},
                    headers=self.HEADERS,
                )
