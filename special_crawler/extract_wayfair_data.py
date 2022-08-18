#!/usr/bin/python

import re
import json
import requests
import traceback
from lxml import html
from urlparse import urlparse
from lxml.html import HtmlElement
from extract_data import Scraper
from shared_cookies import SharedCookies, SharedLock
from spiders_shared_code.wayfair_variants import WayfairVariants
from two_captcha_solver import TwoCaptchaSolver

# Helper functions, shared with Allmodern scraper


def get_auth_data(obj):
    try:
        txid = re.search(r'TRANSACTION_ID\":\"([^"]*)\"', obj.page_raw_text)
        if txid:
            txid = txid.group(1)
        csrf = re.search(r'csrfToken\":\"(.*?)\"', obj.page_raw_text)
        if csrf:
            csrf = csrf.group(1)
        parsed_url = urlparse(obj.product_page_url)
        headers = {
            'origin': '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url),
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'en-US,en;q=0.9,ru;q=0.8',
            'x-requested-with': 'XMLHttpRequest',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'referer': obj.product_page_url.encode('utf-8'),
        }
        if hasattr(obj, 'USER_AGENT'):
            headers['user-agent'] = obj.USER_AGENT

        return txid, headers, csrf

    except Exception as e:
        print traceback.format_exc()

        if obj.lh:
            obj.lh.add_list_log('errors', str(e))


def get_options_data(obj):
    variants_json = None
    js = re.findall(
        'wf.extend\(({"wf":{"apnData.*})\)',
        obj.page_raw_text
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
            {'sku': str(obj._sku()), 'option_ids': [int(p['option_id'])]}
            for p in variants_json[0].get('options', [])
        ]


def get_inventory_data(obj, custom_headers={}):
    txid, headers, csrf = get_auth_data(obj)
    retry = obj.MAX_RETRIES or 3
    options_data = get_options_data(obj)
    for custom_header in custom_headers:
        headers[custom_header['key']] = custom_header['value']
    for i in range(int(retry)):
        try:
            data = {
                'postal_code': '',
                'event_id': 0,
                'should_calculate_all_kit_items': 'false'
            }
            if options_data:
                inventory_url = obj.INVENTORY_URL.format(txid)
                data['product_data'] = options_data
            else:
                inventory_url = obj.SINGLE_PRODUCT_INVENTORY_URL.format(txid)
                data['product_data'] = [
                    {
                        'sku': obj._sku(),
                        'qty': 1,
                        'is_fully_configured': True
                    }
                ]
                data['_csrf_token'] = csrf
                data['source'] = 'main_pdp'
                data['postal_code'] = ''
            headers['content-type'] = 'application/json; charset=UTF-8'
            resp = obj._request(
                inventory_url,
                session=obj.session,
                verb='post',
                headers=headers,
                data=json.dumps(data)
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print traceback.format_exc()
            if obj.lh:
                obj.lh.add_list_log('errors', 'Error getting inventory data: {}'.format(e))


def get_images_data(obj):
    txid, headers, csrf = get_auth_data(obj)
    retry = obj.MAX_RETRIES or 3

    for i in range(int(retry)):
        try:
            image_url = obj.IMAGES_URL.format(obj._sku())
            resp = obj._request(image_url, session=obj.session, headers=headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print traceback.format_exc()

            if obj.lh:
                obj.lh.add_list_log('errors', 'Error getting image data: {}'.format(e))


def get_valid_image_ids(obj):
    txid, headers, csrf = get_auth_data(obj)
    retry = obj.MAX_RETRIES or 3

    for i in range(int(retry)):
        try:
            data = {
                "query": "product_detail_image_component~0",
                "variables": {
                    "sku": "%s" % obj._sku(),
                    "optionIds": [
                        obj._product_id()
                    ]
                }
            }
            headers['x-request-id'] = txid
            headers['use-path'] = 'true'
            resp = obj._request(
                obj.IMAGES_IDS_URL,
                session=obj.session,
                verb='post',
                headers=headers,
                data=json.dumps(data)
            )
            if resp.status_code != 200 and resp.json().get('data', {}).get('product', {}).get('imageIds'):
                return resp.json()['data']['product']['imageIds']
        except Exception as e:
            print traceback.format_exc()

            if obj.lh:
                obj.lh.add_list_log('errors', 'Error getting additional image data: {}'.format(e))

class WayfairScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    IMAGES_URL = "http://www.wayfair.com/a/product_image_group/get_images?sku={0}"

    IMAGES_IDS_URL = "http://www.wayfair.com/graphql"

    INVENTORY_URL = "https://www.wayfair.com/a/inventory/load?_txid={}"

    SINGLE_PRODUCT_INVENTORY_URL = "https://www.wayfair.com/a/product/get_liteship_and_inventory_data?_txid={}"

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
                 " (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.wv = WayfairVariants()

        self.inventory_data = {}
        self.image_valid_ids = []
        self.image_data = {}

        self.solve_captcha = True
        self.session = requests.session()
        self.shared_lock = SharedLock('wayfair')
        self.shared_cookies = SharedCookies('wayfair')

        self.product_page_url = re.sub('https://', 'http://', self.product_page_url)

    def _extract_page_tree(self):
        for _ in range(self.MAX_RETRIES):
            try:
                s3_cookies = self.shared_cookies.load()
                if s3_cookies and not self.shared_lock.load():
                    self.session.cookies = s3_cookies
                req = self._request(
                    self.product_page_url,
                    session=self.session,
                    log_status_code=True
                )
                self.page_raw_text = req.text
                self.tree_html = html.fromstring(self.page_raw_text)
                if self._is_captcha() and self.solve_captcha:
                    if not self.shared_lock.load():
                        self.shared_cookies.delete()
                        self.shared_lock.save('1')
                    captcha_url = req.url
                    answer = self._solve_captcha(captcha_url)
                    if answer:
                        goto_url = self.tree_html.xpath('//input[@name="goto"]/@value')
                        data = {
                            'g-recaptcha-response': answer,
                            'goto': goto_url[0] if goto_url else None,
                            'px': 1
                        }
                        req = self._request(
                            captcha_url,
                            verb='post',
                            headers={
                                'content-type': 'application/x-www-form-urlencoded'
                            },
                            session=self.session,
                            data=data,
                            log_status_code=True
                        )
                        if req.status_code == 200:
                            self.page_raw_text = req.text
                            self.tree_html = html.fromstring(self.page_raw_text)
                            if not self._is_captcha():
                                if self.shared_lock.load():
                                    self.shared_lock.save('')
                                    self.shared_cookies.save(self.session)
                                return
            except Exception as e:
                if self.lh:
                    self.lh.add_list_log('errors', str(e))
        if self.shared_lock.load():
            self.shared_lock.save('')

    def _is_captcha(self):
        return bool(self.tree_html.xpath('//div[@class="g-recaptcha"]'))

    def _solve_captcha(self, captcha_url):
        solver = TwoCaptchaSolver(self, captcha_url)
        return solver.recaptchaV2()

    def not_a_product(self):
        if self._is_captcha():
            self.ERROR_RESPONSE['failure_type'] = 'Captcha'
            self.is_timeout = True
            return True

        if self.tree_html.xpath('//div[contains(@class, "ProductDetail")]'):
            self._extract_additional_data()
            self.wv.setupCH(self.tree_html)

            # If there is not a valid piid in the url, fail it (CON-42563)
            if 'piid=' in self.product_page_url and self._variants() and not self._selected_variant():
                return True

            return False

        return True

    def _extract_additional_data(self):
        if not self.inventory_data:
            self.inventory_data = get_inventory_data(self)
        self.session.close()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        pid = re.search(r'piid=(\d+)', self.product_page_url)
        if not pid:
            pid = re.search(r'"selectedOptions":\["(\d+)"', self.page_raw_text)
        if not pid:
            pid = re.search(r'-(\w+).html', self.product_page_url)
        return pid.group(1) if pid else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath('//meta[@property="og:title"]/@content')[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _sku(self):
        return self.tree_html.xpath("//*[@name='sku']/@value")[0]

    def _features(self):
        features = self.tree_html.xpath(
            '//li[@class="ProductOverviewInformation-list-item"]/text()'
        )
        if features:
            return [x.strip() for x in features]

    def _bullets(self):
        details = self.tree_html.xpath("//div[@id='details_section_header']//"
                                       "div[contains(@class,'ProductDetailSpecifications-content')]")
        if details:
            key, data = None, {}
            for item in details[0].xpath('.//h3|.//li//text()'):
                if isinstance(item, HtmlElement) and item.text_content():
                    key = item.text_content().strip()
                    continue
                if key:
                    data.setdefault(key, [])
                    data[key].append(item)

            bullets = [x.strip() for x in data.get('Product Details', [])]
            if bullets:
                return "\n".join(bullets)

    def _description(self):
        description = self.tree_html.xpath("//*[@class='ProductOverviewInformation-description']"
                                           "/text()")
        if description:
            return description[0].strip()

    def _long_description(self):
        content_block = self.tree_html.xpath("//div[@class='js-content-contain']")
        long_description_content = ""
        if content_block:
            for child_block in content_block[0]:
                if child_block.attrib["class"] == "product_section_description":
                    continue
                if '<p class="product_sub_section_header">Features</p>' in html.tostring(child_block):
                    continue
                long_description_content += child_block.text_content().strip()
            long_description_content = re.sub(r'\\n+|\\t+|\ +', ' ', long_description_content).strip()

        if len(long_description_content) > 0:
            return long_description_content

    def _variants(self):
        if self.inventory_data:
            return self.wv._variants(self.inventory_data)

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        if self.image_data and self.image_valid_ids:
            image_data = self.image_data.get('images')
            if not image_data:
                image_data = self.image_data.get('images', {}).get('models')
            if image_data:
                for img in image_data:
                    if img['image_resource_id'] in self.image_valid_ids:
                        image_urls.append(img['large_image_url'])
        else:
            images = self.tree_html.xpath(
                '//div[contains(@class, "InertiaCarouselComponent-arrowsWrapper--vertical")]//img[@srcset]/@srcset'
            )
            if images:
                for img in images:
                    srcset = re.findall('(http.*?)\s', img)
                    if srcset:
                        image_urls.append(srcset[-1])
        return image_urls if image_urls else None

    def _pdf_urls(self):
        return self.tree_html.xpath("//a[contains(@href, '.pdf')]/@href")

    def _video_urls(self):
        video_urls = set(re.findall(r'"source":"(.*?)","type":"video\\\/mp4', html.tostring(self.tree_html)))
        if video_urls:
            return [i.replace('\\', '') for i in video_urls if '"source":' not in i]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        reviews = self.tree_html.xpath('//*[@class="ProductReviewsHistogram-count"]/text()')

        review_count = self.tree_html.xpath('//*[@data-event-name="reviewTopClick"]'
                                            '//*[@class="ReviewStars-reviews"]'
                                            '/text()')
        self.review_count = int(review_count[0]) if review_count else 0

        average_review = self.tree_html.xpath('//div[@class="ProductReviewsHistogram-header"]'
                                              '//p[@class="ReviewStars-reviews"]/text()')
        if average_review:
            self.average_review = float(average_review[0])

        return [[5-i, int(review)] for i, review in enumerate(reviews)]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return float(re.search('"price":(.*?)}', html.tostring(self.tree_html), re.DOTALL).group(1))

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.inventory_data:
            if isinstance(self.inventory_data, dict):
                return int(self.inventory_data.get('inventory', [{}])[0].get('available_quantity', 0) == 0)
            else:
                for option in self.inventory_data:
                    if not self._product_id().isdigit():
                        return int(option.get('available_quantity') == 0)
                    if int(self._product_id()) in option.get('option_ids'):
                        return int(option.get('available_quantity') == 0)

        return int(not self.tree_html.xpath('//button[@id="btn-add-to-cart"]'))

    def _in_stores(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath("//nav[contains(@class, 'Breadcrumbs')]//li/a/text()")

    def _brand(self):
        return re.search('"brand":(.*?),', html.tostring(self.tree_html), re.DOTALL).group(1).replace('"', '')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "sku": _sku,
        "features": _features,
        "bullets": _bullets,
        "description": _description,
        "long_description": _long_description,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "pdf_urls": _pdf_urls,
        "video_urls": _video_urls,

        # CONTAINER : REVIEWS
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,
        "site_online": _site_online,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
