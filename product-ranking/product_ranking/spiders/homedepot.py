from __future__ import division, absolute_import, unicode_literals

import re
import urlparse
import json
import hjson
import traceback
from lxml import html

from scrapy import Request
from scrapy.log import DEBUG

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, cond_set_value,\
    FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.validators.homedepot_validator import HomedepotValidatorSettings
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import find_brand
from spiders_shared_code.homedepot_variants import HomeDepotVariants


is_empty = lambda x, y=None: x[0] if x else y


def is_num(s):
    try:
        int(s.strip())
        return True
    except ValueError:
        return False


class HomedepotProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'homedepot_products'
    allowed_domains = ["homedepot.com", "origin.api-beta.homedepot.com", "homedepot.ugc.bazaarvoice.com"]
    start_urls = []

    settings = HomedepotValidatorSettings

    SEARCH_URL = "http://www.homedepot.com/s/{search_term}?NCNI-5"
    REVIEWS_URL = "http://homedepot.ugc.bazaarvoice.com/1999m/%s/" \
                  "reviews.djs?format=embeddedhtml"
    QA_URL = "http://homedepot.ugc.bazaarvoice.com/answers/1999aa/product/" \
             "{product_id}/questions.djs?format=embeddedhtml"

    ITEMS_URL = "http://www.homedepot.com/p/svcs/frontEndModel/{product_id}"

    # Store id: 915, Zip code: 07088, cookie lasts until 09/2018
    ZIP_CODE = "07088"
    STORE_COOKIE = "C4%3D915%2BUnion%252FVauxhall%20-%20Vauxhall%2C%20NJ%2B%3A%3BC4_EXP" \
                   "%3D1536944608%3A%3BC24%3D07088%3A%3BC24_EXP%3D1536944608%3A%3BC34%3" \
                   "D32.0%3A%3BC34_EXP%3D1505495014%3A%3BC39%3D1%3B7%3A00-20%3A00%3B2%3" \
                   "B6%3A00-22%3A00%3B3%3B6%3A00-22%3A00%3B4%3B6%3A00-22%3A00%3B5%3B6%3" \
                   "A00-22%3A00%3B6%3B6%3A00-22%3A00%3B7%3B6%3A00-22%3A00%3A%3BC39_EXP%" \
                   "3D1505412208"

    product_filter = []

    def __init__(self, *args, **kwargs):
        # All this is to set the site_name since we have several
        # allowed_domains.
        self.br = BuyerReviewsBazaarApi()
        super(HomedepotProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        self.scrape_questions = kwargs.get('scrape_questions', None)
        if self.scrape_questions not in ('1', 1, True, 'true', 'True'):
            self.scrape_questions = False

    def start_requests(self):
        for req in super(HomedepotProductsSpider, self).start_requests():
            yield req.replace(
                cookies={'THD_PERSIST': self.STORE_COOKIE}
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    @staticmethod
    def _parse_no_longer_available(response):
        message = response.xpath(
            '//div[@class="error" and '
            'contains(., "The product you are trying to view is not currently available.")]')
        return bool(message)

    def parse_product(self, response):
        product = response.meta['product']
        product['_subitem'] = True

        if self._parse_no_longer_available(response):
            product['no_longer_available'] = True
            return product
        else:
            product['no_longer_available'] = False

        cond_set(
            product,
            'title',
            response.xpath("//h1[contains(@class, 'product-title')]/text()").extract())
        brand = response.xpath("//h2[@itemprop='brand']//text()").extract()
        brand = find_brand("".join(brand).strip())
        cond_set_value(
            product,
            'brand',
            brand)

        cond_set_value(product, 'zip_code', self.ZIP_CODE)

        cond_set(
            product,
            'image_url',
            response.xpath(
                "//div[@class='product_mainimg']/img/@src |"
                "//img[@id='mainImage']/@src"
            ).extract())

        product_id = self._get_product_id(response)
        cond_set_value(product, 'reseller_id', product_id)

        cond_set_value(product, 'price', self._parse_price(response))
        cond_set_value(product, 'price_details_in_cart', self._parse_price_in_cart(response))

        try:
            product['model'] = response.css(
                '.product_details.modelNo ::text'
            ).extract()[0].replace('Model', '').replace('#', '').strip()
        except IndexError:
            pass

        internet_no = response.css('#product_internet_number ::text').extract()
        if internet_no:
            internet_no = internet_no[0]

        upc = is_empty(re.findall(
            "ItemUPC=\'(\d+)\'", response.body))
        if upc:
            product["upc"] = upc

        upc = response.xpath("//upc/text()").re('\d+')
        if upc:
            product["upc"] = upc[0][-12:].zfill(12)

        product['locale'] = "en-US"

        metadata = response.xpath(
            "//script[contains(text(),'PRODUCT_METADATA_JSON')]"
            "/text()").re('var PRODUCT_METADATA_JSON = (.*);')

        if metadata:
            metadata = metadata[0]
            try:
                jsmeta = hjson.loads(metadata)
                skus = [jsmeta["attributeDefinition"]["defaultSku"]]
                response.meta['skus'] = skus
                metaname = jsmeta['attributeDefinition']['attributeListing'][0][
                    'label']
                response.meta['attributelabel'] = metaname
            except (KeyError, IndexError):
                self.log("Incomplete data from Javascript.", DEBUG)

        reqs = []
        meta = {"product": product, '_subitem': True}

        if internet_no:
            reqs.append(Request(
                url=self.REVIEWS_URL % internet_no,
                callback=self.parse_buyer_reviews,
                meta={"product": product},
                dont_filter=True,
            ))

        if product_id:
            reqs.append(Request(
                url=self.ITEMS_URL.format(product_id=product_id),
                callback=self.parse_store_data,
                dont_filter=True,
                meta=meta,
            ))

        variants_urls = self._get_variants_urls(response)
        reqs.extend(variants_urls)

        if reqs:
            return self.send_next_request(reqs)

        return product

    def _parse_price(self, response):
        price = response.xpath("//div[@class='pricingReg']/span[@itemprop='price']/text()").extract()
        if price:
            # Price separated between two tags (price__dollars, price__cents)
            ceil = response.xpath('//*[@itemprop="offers"]/*[@itemprop="price"]'
                                  '//*[contains(@class, "price__dollars")]/text()').extract()
            frac = response.xpath('//*[@itemprop="offers"]/*[@itemprop="price"]'
                                  '//*[contains(@class, "price__cents")]/text()').extract()
            if ceil and frac:
                price_re = re.search(FLOATING_POINT_RGEX, '.'.join([ceil[0], frac[0]]))
                if price_re:
                    price = price_re.group(0).replace(',', '')

        if not price:
            price = response.xpath("//div[contains(@class, 'pricingReg')]"
                                   "//span[@itemprop='price']/text() |"
                                   "//div[contains(@class, 'pricingReg')]"
                                   "//span[@itemprop='price']").re(FLOATING_POINT_RGEX)
            if price:
                price = price[0]

        if not price and self._parse_price_in_cart(response):
            price = response.xpath('//*[@id="ciItemPrice"]//@value').extract()

        if price:
            return Price(priceCurrency="USD", price=price)

    @staticmethod
    def _parse_price_in_cart(response):
        return bool(response.xpath('//*[@id="mapMessage"]//text()').extract())

    def _get_variants_urls(self, response):
        color_option_ids = response.xpath(
            '//div[contains(@class, "product_sku_Overlay_ColorSwatch")]//li/@data-itemid'
        ).extract()
        reqs = []
        variants_data = []
        for _ in color_option_ids:
            variants_data.append({
                'html': None,
                'options': []
            })
        for i, color_option_id in enumerate(color_option_ids):
            meta = response.meta.copy()
            meta['variant_index'] = i
            meta['variants_data'] = variants_data
            meta['color_option'] = color_option_id
            if color_option_id == response.meta.get('product').get('reseller_id'):
                response.meta['variant_index'] = i
                response.meta['variants_data'] = variants_data
                reqs.extend(self._get_options(response))
            else:
                url = re.sub('/\d+', '/%s' % color_option_id, response.url)
                reqs.append(
                    Request(
                        url=url,
                        dont_filter=True,
                        callback=self._get_color_variant,
                        meta=meta
                    )
                )
        return reqs

    def _get_color_variant(self, response):
        meta = response.meta.copy()
        reqs = meta.get('reqs')

        if reqs:
            reqs.extend(self._get_options(response))
            return self.send_next_request(reqs)

    def _get_options(self, response):
        reqs = []
        available_options = response.xpath(
            '//ul[contains(@class, "listOptions")]//a[@class="enabled"]/@data-itemid'
        ).extract()
        if available_options:
            for option in available_options:
                reqs.append(self._make_option_request(response, option))
        else:
            reqs.append(self._make_option_request(response, response.meta.get('color_option')))
        return reqs

    def _make_option_request(self, response, option):
        meta = response.meta.copy()
        opt_data = {}
        if not option:
            option = response.xpath('//li[@data-itemid and @class="selected"]/@data-itemid').extract()
            if option:
                option = option[0]
        if option == response.meta.get('product').get('reseller_id'):
            opt_data['selected'] = True
        else:
            opt_data['selected'] = False
        meta['option'] = opt_data
        meta['html'] = html.fromstring(response.body)
        return Request(
            url=self.ITEMS_URL.format(product_id=option),
            dont_filter=True,
            callback=self._get_options_json,
            meta=meta
        )

    def _get_options_json(self, response):
        meta = response.meta.copy()
        reqs = meta.get('reqs')
        variants_data = meta.get('variants_data')
        variant_index = meta.get('variant_index')
        if not variants_data[variant_index].get('html'):
            variants_data[variant_index]['html'] = meta.get('html')

        try:
            json_data = json.loads(response.body)
            opt_data = meta.get('option')
            opt_data['json'] = json_data
            variants_data[variant_index]['options'].append(opt_data)
            meta['variants_data'] = variants_data
        except:
            self.log(traceback.format_exc())

        if reqs:
            req = self.send_next_request(reqs)
            new_meta = req.meta.copy()
            new_meta['variants_data'] = variants_data
            return req.replace(meta=new_meta)

        product = meta.get('product')

        hdv = HomeDepotVariants()
        variants = hdv.variants(variants_data)

        product['variants'] = variants
        return product

    def parse_store_data(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs')

        try:
            product_json = json.loads(response.body)
        except:
            self.log(traceback.format_exc())
            return product

        store = product_json.get('localStore', {}).get('storenumber')
        cond_set_value(product, 'store', store)

        is_out_of_stock = False
        try:
            is_out_of_stock = not product_json['primaryItemData']["storeSkus"][0]["storeAvailability"]["itemAvailable"]
            if is_out_of_stock == True:
                is_out_of_stock = not product_json['primaryItemData']["storeSkus"][0]["storeAvailability"]["availableInLocalStore"]
        except:
            self.log(traceback.format_exc())
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        try:
            options = product_json['primaryItemData']["storeSkus"][0]["fulfillmentOptions"]
            in_store_pickup = options.get('buyOnlinePickupInStore', {}).get('status')
            if in_store_pickup:
                cond_set_value(product, 'in_store_pickup', in_store_pickup)
            else:
                cond_set_value(product, 'in_store_pickup', False)
        except:
            self.log(traceback.format_exc())

        is_in_store_only = False
        if is_out_of_stock == True:
            is_in_store_only = product_json['primaryItemData']["storeSkus"][0]["storeAvailability"]["availableInLocalStore"]
        cond_set_value(product, 'is_in_store_only', is_in_store_only)

        if reqs:
            return self.send_next_request(reqs)

        return product

    def send_next_request(self, reqs):
        req = reqs.pop(0)
        if reqs:
            req.meta["reqs"] = reqs

        return req

    def _get_product_id(self, response):
        product_id = urlparse.urlparse(response.url).path.split('/')[-1]
        reseller_id = re.search(r'(\d+)', product_id)
        return reseller_id.group(1) if reseller_id else None

    def _parse_skudetails(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs')

        try:
            jsdata = json.loads(response.body_as_unicode())
            storeskus = jsdata['storeSkus']
            price = storeskus['storeSku']['pricing']['originalPrice']
            product['price'] = price

            if product.get('price', None):
                if not '$' in product['price']:
                    self.log('Unknown currency at' % response.url)
                else:
                    product['price'] = Price(
                        price=product['price'].replace(',', '').replace(
                            '$', '').strip(),
                        priceCurrency='USD'
                    )

            desc = jsdata['info']['description']
            product['description'] = desc

            url = jsdata['canonicalURL']
            url = urlparse.urljoin(product['url'], url)
            product['url'] = url

            image = jsdata['inlinePlayerJSON']['IMAGE'][1]['mediaUrl']
            product['image_url'] = image

            attrname = response.meta.get('attributelabel', 'Color/Finish')
            colornames = jsdata['attributeGroups']['group'][0]['entries'][
                'attribute']
            colornames = [el['value'] for el in colornames
                          if el['name'] == attrname]
            if colornames:
                product['model'] = str(colornames[0])
        except (ValueError, KeyError, IndexError):
            self.log("Failed to parse SKU details.", DEBUG)

        if reqs:
            return self.send_next_request(reqs)

        return product

    def parse_buyer_reviews(self, response):
        product = response.meta.get("product")
        reqs = response.meta.get('reqs')

        brs = self.br.parse_buyer_reviews_per_page(response)
        self.br.br_count = brs.get('num_of_reviews', None)
        brs['rating_by_star'] = self.br.get_rating_by_star(response)
        product['buyer_reviews'] = brs
        if self.scrape_questions:
            reqs.append(Request(
                url=self.QA_URL.format(product_id=product.get("reseller_id")),
                callback=self._parse_questions,
                meta={'product': product}
            ))

        if reqs:
            return self.send_next_request(reqs)

        return product

    def _scrape_total_matches(self, response):
        totals = response.xpath(
            "//a[@id='all_products']/label"
            "/text()").re(r'All Products \(([\d,]+)\)')
        if totals:
            totals = totals[0]
            totals = totals.replace(",", "")
            if is_num(totals):
                return int(totals)
        no_matches = response.xpath(
            "//h1[@class='page-title']/text()").extract()
        if no_matches:
            if 'we could not find any' in no_matches[0] or \
               'we found 0 matches for' in no_matches[0]:
                return 0
        total_matches = response.xpath('//*[contains(@id, "all_products")]//text()').extract()
        if total_matches:
            total_matches = ''.join(total_matches)
            total_matches = ''.join(c for c in total_matches if c.isdigit())
            if total_matches and total_matches.isdigit():
                return int(total_matches)
        total_matches = response.xpath('//*[@id="allProdCount"]/text()').re(FLOATING_POINT_RGEX)
        if total_matches:
            total_matches = total_matches[0]
            total_matches = total_matches.replace(',', '')
            if total_matches.isdigit():
                return int(total_matches)
        return

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class,'product') "
            "and contains(@class,'plp-grid')]"
            "//descendant::a[contains(@class, 'item_description')]/@href | "
            "//div[contains(@class, 'description')]/a[@data-pod-type='pr']/@href").extract()

        if not links:
            self.log("Found no product links.", DEBUG)

        for link in links:
            if link in self.product_filter:
                continue
            self.product_filter.append(link)
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(
            "//div[@class='pagination-wrapper']/ul/li/span"
            "/a[@title='Next']/@href |"
            "//div[contains(@class, 'pagination')]/ul/li/span"
            "/a[@class='icon-next']/@href |"
            "//li[contains(@class, 'hd-pagination__item')]"
            "/a[contains(@class, 'pagination__link') and @title='Next']/@href"
        ).extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])

    def _parse_questions(self, response):
        product = response.meta['product']
        qa = product.get("recent_questions", [])
        questions_ids_regex = re.compile("""BVQAQuestionSummary.+?javascript:void.+?>([^<]+?)<.+?BVQAElapsedTime.+?>([^<]+).+?BVQAQuestionMain(\d+)(?:.+?BVQAQuestionDetails.+?div>([^<]+)?)""")
        questions_ids = questions_ids_regex.findall(response.body_as_unicode())
        for (question_summary, question_date, question_id, question_details) in questions_ids:
            # regex to get part of response that contain all answers to question with given id
            text_r = "BVQAQuestion{question_id}Answers(.*?)(?:BVQAQuestionDivider|}},)".format(question_id=question_id)
            all_a_text = re.findall(text_r, response.body_as_unicode())
            all_a_text = ''.join(all_a_text[0]) if all_a_text else ''
            # answers_regex = r"Answer:.+?>([^<]+)"
            answers_regex = r"Answer:.+?>(.+?)<\\"
            answers = re.findall(answers_regex, all_a_text)
            nicknames = filter(None, re.findall(r'BVQANickname\\">(.*?)<', all_a_text))
            dates = re.findall(r'BVQAElapsedTime\\"> (.*?)\\n<', all_a_text)
            answers = [{'answerText': self.qa_cleanup(answer),
                        'userNickname': nickname,
                        'submissionDate': date}
                        for answer, nickname, date in zip(answers, nicknames, dates)]
            question = {
                'submissionDate': self.qa_cleanup(question_date),
                'questionId': question_id,
                'questionDetail': self.qa_cleanup(question_details),
                'questionSummary': self.qa_cleanup(question_summary),
                'answers': answers,
                'totalAnswersCount': len(answers)
            }
            qa.append(question)
        product['recent_questions'] = qa
        # parse next page of reviews
        nexpage_regex = re.compile("BVQANextPage.*?bvjsref=.*?[\'\"](.*?)[\\\'\"]")
        nexpage_url = nexpage_regex.search(response.body_as_unicode())
        nexpage_url = nexpage_url.group(1).strip("\\").replace("&amp;", "&") if nexpage_url else None
        if nexpage_url:
            if not nexpage_url == response.url:
                return Request(
                    url=nexpage_url,
                    # for some reason scrapy dupefilter doesn't take into account request params
                    dont_filter=True,
                    callback=self._parse_questions,
                    meta={'product': product}
                )
        return product

    @staticmethod
    def qa_cleanup(qa_string):
        qa_string = qa_string.replace("<br />", '').replace("\\n", '').strip() if qa_string else ''
        return qa_string
