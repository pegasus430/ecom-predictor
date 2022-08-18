#!/usr/bin/python

import re
import json
import string
import requests
import traceback
import urllib

from lxml import html
from HTMLParser import HTMLParser
import spiders_shared_code.canonicalize_url
from extract_data import Scraper, deep_search
from spiders_shared_code.samsclub_variants import SamsclubVariants


class SamsclubScraper(Scraper):

    CLUB_ID = '4774'

    HEADERS = {
        'WM_QOS.CORRELATION_ID': '1470699438773',
        'WM_SVC.ENV': 'prod',
        'WM_SVC.NAME': 'sams-api',
        'WM_CONSUMER.ID': '6a9fa980-1ad4-4ce0-89f0-79490bbc7625',
        'WM_SVC.VERSION': '1.0.0',
        'Cookie': 'myPreferredClub={}'.format(CLUB_ID),
    }

    IMG_BASE = 'https://images.samsclubresources.com/is/image/samsclub/'
    IMG_ARGS = '?wid=1500&hei=1500&fmt=jpg&qlt=80'

    INVALID_URL_MESSAGE = 'Expected URL format is ' \
                          'http(s)://(m.|www.)samsclub.com/(sams or ip/)(<product name>/)<product id>(.ip) or '

    MOBILE_IMAGE_API = 'https://m.samsclub.com/api/product/{upc}/images'

    INVENTORY_URL = 'https://www.samsclub.com/api/soa/services/v1/inventorylookup/inventory?qtyLevel=true'

    MOBILE_IMAGE_API = 'https://m.samsclub.com/api/product/{upc}/images'

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?passkey=dap59bp2pkhr7ccd1hv23n39x&apiversion=5.5&displaycode=1337-en_us&resource.q0=products&filter.q0=id%3Aeq%3A{}&stats.q0=questions%2Creviews&filteredstats.q0=questions%2Creviews&filter_questions.q0=contentlocale%3Aeq%3Aen_US&filter_answers.q0=contentlocale%3Aeq%3Aen_US&filter_reviews.q0=contentlocale%3Aeq%3Aen_US&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen_US&resource.q1=questions&filter.q1=productid%3Aeq%3Aprod4650346&filter.q1=contentlocale%3Aeq%3Aen_US&sort.q1=totalanswercount%3Adesc&stats.q1=questions&filteredstats.q1=questions&include.q1=authors%2Cproducts%2Canswers&filter_questions.q1=contentlocale%3Aeq%3Aen_US&filter_answers.q1=contentlocale%3Aeq%3Aen_US&sort_answers.q1=totalpositivefeedbackcount%3Adesc%2Ctotalnegativefeedbackcount%3Aasc&limit.q1=10&offset.q1=0&limit_answers.q1=10&resource.q2=reviews&filter.q2=isratingsonly%3Aeq%3Afalse&filter.q2=productid%3Aeq%3Aprod4650346&filter.q2=contentlocale%3Aeq%3Aen_US"

    QUESTIONS_URL = "https://api.bazaarvoice.com/data/batch.json?passkey=dap59bp2pkhr7ccd1hv23n39x" \
                    "&apiversion=5.5" \
                    "&displaycode=1337-en_us" \
                    "&resource.q0=questions" \
                    "&filter.q0=productid%3Aeq%3A{}" \
                    "&limit.q0=100" \
                    "&offset.q0={}"

    VIDEO_URL = 'http://players.brightcove.net/4174796162001/' \
                'd1f1388a-5042-45d3-aa0e-c60848bfd5b3_default/' \
                'index.html?videoId={}'

    FLIXMEDIA_URL = 'https://media.flixcar.com/delivery/js/inpage/859/us/mpn/{0}?&=859&=us&mpn={0}&ssl=1&ext=.js'

    SELLPOINT_URL = 'https://a.sellpoint.net/w/151/{}.json'

    WEBCOLLAGE_POWER_PAGE = 'https://scontent.webcollage.net/sc/power-page?ird=true&channel-product-id={}'
    WEBCOLLAGE_URL = 'http://content.webcollage.net/sc/smart-button?ird=true&channel-product-id={}'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.redirect = 0

        self.inventory_info = {}
        self.product_json = {}

        self.image_urls = None
        self.image_urls_checked = False
        self.no_image_available = 0

        self.spin_images = None

        self.swatches = None
        self.swatches_checked = False

        self.sv = SamsclubVariants()

        self.proxies_enabled = False  # first, they are OFF to save allowed requests

        self.product_page_url = re.sub('http://', 'https://', self.product_page_url.split('?')[0])

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.samsclub(url)

    @staticmethod
    def _cat_id_from_url(url):
        m = re.search('(\d+)\.cp', url)
        if not m:
            m = re.search('categoryId=(\d+)', url)
        if m:
            return m.group(1)

    @staticmethod
    def _is_valid_url(url):
        if re.match('https?://(m\.|www\.)samsclub\.com/(sams/|ip/)?(.+/)?(prod)?\d+(\.ip)?', url):
            return True
        return False

    def check_url_format(self):
        return self._is_valid_url(self.product_page_url)

    @staticmethod
    def _is_shelf_url(url):
        if (re.match('https?://www\.samsclub\.com/(sams/)?(.+/)?(\d+)\.cp', url) or \
                re.match('https?://www\.samsclub\.com/(sams/)?shop/category.jsp\?categoryId=(\d+)', url) or \
                re.match('https?://www\.samsclub\.com/(sams/)?pagedetails/content.jsp\?pageName=.+', url)):
            return True

    def _site_version(self):
        if self.tree_html.xpath("//div[@class='container' and @itemtype='http://schema.org/Product']"):
            return 1
        if self._canonical_link() == 'product.jsp':
            return 2

    def _extract_page_tree(self):
        for i in range(self.MAX_RETRIES):
            try:
                with requests.Session() as s:
                    r = self._request(self.product_page_url, allow_redirects=False, session=s, log_status_code=True)

                    self.page_raw_text = r.content
                    self.tree_html = html.fromstring(self.page_raw_text)

                    redirect_url = None

                    if r.status_code == 302:
                        redirect_url = r.headers['Location']

                    elif r.status_code != 200:
                        print 'Got response %s for %s with headers %s' % (r.status_code, self.product_page_url, r.headers)

                        self.is_timeout = True
                        self.ERROR_RESPONSE['failure_type'] = r.status_code
                        return

                    else:
                        redirect = self.tree_html.xpath('//meta[@http-equiv="Refresh" or @http-equiv="refresh"]/@content')
                        if redirect:
                            redirect_url = re.search('URL=(.*)', redirect[0], re.I).group(1)

                        if not redirect:
                            for javascript in self.tree_html.xpath('//script[@type="text/javascript"]/text()'):
                                javascript = re.sub('[\s\'"\+\;]', '', javascript)
                                redirect = re.match('location.href=(.*)', javascript)

                                if redirect:
                                    redirect_url = redirect.group(1)
                                    if not re.match('https?://.+\.samsclub.com', redirect_url):
                                        redirect_url = 'http://www.samsclub.com' + redirect_url

                    if redirect_url:
                        # Do not redirect to non-valid, non-shelf urls,
                        # to the 100001 'All Products' page, 
                        # or to shelf pages from non-shelf pages
                        if not (self._is_valid_url(redirect_url) or self._is_shelf_url(redirect_url)) or \
                                self._cat_id_from_url(redirect_url) == '100001' or \
                                (not self._is_shelf_url(self.product_page_url) and self._is_shelf_url(redirect_url)):

                            self.is_timeout = True
                            self.ERROR_RESPONSE['failure_type'] = '404'
                            return

                        self.product_page_url = redirect_url
                        self.redirect = 1

                        r = self._request(self.product_page_url, allow_redirects=False, session=s)

                        if self.lh:
                            self.lh.add_log('status_code', r.status_code)

                        if r.status_code != 200:
                            print 'Got response %s for %s with headers %s' % (
                                r.status_code, self.product_page_url, r.headers)

                            self.is_timeout = True
                            self.ERROR_RESPONSE['failure_type'] = r.status_code
                            return

                        self.page_raw_text = r.content
                        self.tree_html = html.fromstring(self.page_raw_text)

                    if 'Page not found' in self._title_seo():
                        self.ERROR_RESPONSE['failure_type'] = '404'
                        continue

                    if 'Access Denied' in self._title_seo():
                        self.ERROR_RESPONSE['failure_type'] = 'Access Denied'
                        self._set_proxy()
                        continue

                    # Try extracting important info (if it is not a shelf page)
                    if not self._is_shelf_url(self.product_page_url):
                        self._extract_product_json()
                        self._get_inventory_info()

                    return

            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

        self.is_timeout = True

    def not_a_product(self):
        if not self.product_json:
            return True

        self.sv.setupCH(self.tree_html, self.product_json)
        self._extract_webcollage_contents()
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        try:
            content = self.page_raw_text

            # If it's version 1, request the mobile site in order to get the product json
            if self._site_version() == 1:
                prod_id = self.product_page_url.split('/')[-1].split('.')[0]
                # Sometimes the url may not include the product name, but if it does and there is '%' in it,
                # then it needs to be encoded (CON-43177)
                prod_name = 'foo'
                canonical_link = self._canonical_link()
                if canonical_link:
                    prod_name = canonical_link.split('/')[-2]
                    if '%' in prod_name:
                        prod_name = urllib.quote(prod_name)
                mobile_url = 'https://m.samsclub.com/ip/{0}/{1}'.format(prod_name, prod_id)
                content = self._request(mobile_url).content

            product_json = re.search('window.__WML_REDUX_INITIAL_STATE__\s*=\s*({.*?});', content).group(1)
            self.product_json = json.loads(product_json)
        except Exception as e:
            print traceback.format_exc()
            raise Exception('Error extracting product json: {}'.format(e))

    def _get_inventory_info(self):
        try:
            data = {'payload': [{
                'productId': self._product_id(),
                'itemNumber': int(self._item_num()),
                'skuId': self._sku(),
                'clubId': self.CLUB_ID}]}
            self.inventory_info = self._request(self.INVENTORY_URL, verb='post', data=json.dumps(data)).json()
        except Exception as e:
            print traceback.format_exc()
            raise Exception('Error extracting inventory info: {}'.format(e))

    def _product_id(self):
        return self.product_json['product']['product']['productId']

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_json['product']['product']['title'].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _model(self):
        # Model is not present in product json fetched from mobile
        model = self.tree_html.xpath("//span[@itemprop='model']//text()")
        if model:
            return model[0].strip()

        return self.product_json['product']['product'].get('modelNumber')

    def _sku(self):
        return self.product_json['product']['selectedSku']['skuId']

    @staticmethod
    def _add_check_digit(upc):
        if len(upc) == 11:
            s = 0
            for i in upc[::2]:
                s += 3 * int(i)
            for i in upc[1::2]:
                s += int(i)
            upc += str(-s % 10)

        return upc

    def _upc(self):
        upc = self.product_json['product']['selectedSku'].get('upc')

        if not upc:
            image_urls = self._image_urls()
            if image_urls:
                upc = re.search('samsclub/(\d+)', image_urls[0])
                if upc:
                    upc = upc.group(1)

        # Get upc min 11 digits, max 12
        upc = upc.zfill(11)[-12:]

        # Return upc with check digit added if necessary
        return self._add_check_digit(upc)

    def _bullets(self):
        for spec in self.product_json['product']['description']['specifications']:
            if spec['specificationHeading'] == 'Specifications':
                specs = html.fromstring(spec['specificationText']).xpath('//li/text()')
                if specs:
                    return '\n'.join(specs)

    def _shelf_description_bullet_count(self):
        if self._shelf_description():
            return len(html.fromstring(self._shelf_description()).xpath('//li/text()'))

    def _variants(self):
        if not self._no_longer_available():
            return self.sv._variants()

    def _no_longer_available(self):
        if self._in_stores() or self._site_online():
            return 0
        return 1

    def _shelf_description(self):
        return self._clean_text(self.product_json['product']['description']['shortDescription'])

    def _long_description(self):
        long_desc = self.product_json['product']['description']['longDescription']
        return self._clean_text(long_desc) if long_desc else None

    def _assembled_size(self):
        specs = deep_search('productSpecifications', self.product_json) \
                or deep_search('specifications', self.product_json)
        if specs:
            if any(s['specificationHeading'] == 'Assembled Size' for s in specs[0]):
                return 1
        return 0

    def _item_num(self):
        return self.product_json['product']['selectedSku']['itemNumber']

    def _swatches(self):
        if not self.swatches_checked:
            self.swatches_checked = True
            self.swatches = self.sv._swatches()

        return self.swatches

    def _swatch_image_missing(self):
        swatches = self._swatches()

        if swatches:
            if any(not s['hero_image'] for s in swatches):
                return 1
            return 0

    def _has_wwlt(self):
        return 1 if self._wwlt_text() else 0

    def _wwlt_text(self):
        wwlt = self.product_json['product']['product'].get('whyWeLoveIt')
        if wwlt:
            return self._clean_text(wwlt)

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if self.image_urls_checked:
            return self.image_urls

        self.image_urls_checked = True

        def fix_image_url(i):
            if not i.startswith('http'):
                i = self.IMG_BASE + i
            return i.split('?')[0] + self.IMG_ARGS

        def get_image_id(image_url):
            return image_url.split('?')[0].split('/')[-1].split('_')[0]

        def get_mobile_images(upc):
            for _ in range(3):
                try:
                    variant_image_json = self._request(self.MOBILE_IMAGE_API.format(upc=upc), timeout = 0.1).json()
                    return [fix_image_url(i['ImageUrl']) for i in variant_image_json['Images']]
                except requests.exceptions.Timeout:
                    continue
                return []

        carousel = self.product_json.get('carousel', {})

        if self._site_version() == 2:
            self.image_urls = [i['zoomIn'] for i in carousel.get('desktopImages', []) if not 'spin' in i['zoomIn']]

            # Get images from the mobile images API
            if self.image_urls:
                upc = get_image_id(self.image_urls[0])
                self.image_urls = get_mobile_images(upc)

        else:
            self.image_urls = [fix_image_url(i['ImageUrl']) for i in carousel.get('images', [])]

            # For some reason, the carousel images often seem to be missing the 'S' image,
            # so this code checks if it is missing and adds it back to the image list
            # First reported in CON-37639
            if self.image_urls:
                r_image_url = re.sub('_[A-Z]\?', '_R?', self.image_urls[0])
                s_image_url = re.sub('_[A-Z]\?', '_S?', self.image_urls[0])
                if r_image_url in self.image_urls and not s_image_url in self.image_urls \
                        and not self._no_image(s_image_url):
                    s_index = self.image_urls.index(r_image_url) + 1
                    self.image_urls.insert(s_index, s_image_url)

            # Get images for the first in-stock variant
            for variant in self._variants() or []:
                if variant['in_stock'] and variant.get('upc'):
                    self.image_urls = get_mobile_images(variant['upc'])
                    break

        if not self.image_urls:
            image_urls = []

            try:
                img_id = re.search('(\d+)_', self.product_json['product']['product']['imageSrc']).group(1)
                image_list = self._request(self.IMG_BASE + img_id + '?req=imageset').content

                for image_url in [fix_image_url(i.strip().split('/')[-1]) for i in image_list.split(';') if i.strip()]:
                    if image_url not in image_urls:
                        image_urls.append(image_url)
            except:
                print traceback.format_exc()

            if image_urls:
                self.image_urls = image_urls
            else:
                self.image_urls = [fix_image_url(self.product_json['product']['product']['imageSrc'])]

        # Check for "no image available" if there is exactly 1 image
        if len(self.image_urls) == 1:
            if self._no_image(self.image_urls[0]):
                self.image_urls = None
                self.no_image_available = 1

        # 360 urls are not present in product json fetched from mobile
        if carousel.get('imageset360'):
            spin_image = carousel['imageset360'][0]
            self.spin_images = [fix_image_url(spin_image + l) for l in string.ascii_uppercase]

        elif self.image_urls:
            spin_image_url = self.image_urls[0].split('?')[0][:-1] + 'spinA'
            if not self._no_image(spin_image_url):
                self.spin_images = [fix_image_url(spin_image_url[:-1] + l) for l in string.ascii_uppercase]

        if self.image_urls:
            return self.image_urls

    def _no_image_available(self):
        return self.no_image_available

    def _image_alt_text(self):
        if self._image_urls():
            return [self._product_name()] * len(self._image_urls())

    def _in_page_360_image_urls(self):
        self._image_urls()
        return self.spin_images

    def _video_urls(self):
        videos = [
            v.get('videoId') for v in self.product_json.get('product', {}).get('product', {}).get('videos', {})
            if isinstance(v, dict) and v.get('videoId')
        ]
        if not videos:
            videos = self.tree_html.xpath('//span[@data-video-id]/@data-video-id')
        if videos:
            return [self.VIDEO_URL.format(v) for v in videos]

    def _redirect(self):
        return self.redirect

    def _super_enhancement(self):
        long_desc = self.product_json['product']['description']['longDescription']
        if long_desc and \
                html.fromstring(self.product_json['product']['description']['longDescription']).xpath('//img'):
            return 1
        return 0

    def _cnet(self):
        product_id = re.match('prod(.*)', self._product_id())
        product_id = product_id.group(1) if product_id else self._product_id()

        sellpoint_json = self._request(self.SELLPOINT_URL.format('l/' + product_id)).json()
        if sellpoint_json:
            self.sellpoints = 1

        widgets = sellpoint_json.get('widgets')
        if widgets:
            widget_json = self._request(self.SELLPOINT_URL.format('w/' + widgets[0])).json()
            url = deep_search('url', widget_json)
            if url and 'cnetcontent' in url[0]:
                return 1
        return 0

    def _flixmedia(self):
        if self._model():
            flixmedia_content = self._request(self.FLIXMEDIA_URL.format(urllib.quote(self._model()))).content
            if 'found=1' in flixmedia_content:
                return 1
        return 0

    def _questions_total(self):
        self._reviews()
        total = deep_search('TotalQuestionCount', self.review_json)
        return total[0] if total else 0

    def _questions_unanswered(self):
        questions_unanswered = 0

        for i in range(10):
            results = self._request(self.QUESTIONS_URL.format(self._product_id(), i*100)).json()
            results = results['BatchedResults']['q0']['Results']
            if results:
                for question in results:
                    if question['TotalAnswerCount'] == 0:
                        questions_unanswered += 1
            else:
                break

        return questions_unanswered

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = None
        pricing_options = self.product_json['product']['selectedSku']['pricingOptions']
        if pricing_options:
            price = pricing_options[0]['finalPrice']['currencyAmount']

        if not price:
            price = self.tree_html.xpath("//*[@itemprop='price']/text()")
            price = float(price[0]) if price else None

        return price

    def _in_stores(self):
        inventory = self.inventory_info['payload']['inventoryList']
        if inventory:
            if inventory[0]['status'] == 'outOfStock':
                return 0
            # Also check html of page (CON-41569)
            if self.tree_html.xpath('//link[@itemprop="availability" and @href="http://schema.org/SoldOut"]'):
                return 0
            return 1
        return 0

    def _in_stores_out_of_stock(self):
        if self._in_stores():
            return 0

    def _marketplace(self):
        return 0

    def _site_online(self):
        if self.product_json['product']['selectedSku']['inventoryOptions'] or \
                not self.inventory_info['payload']['inventoryList']:
            return 1
        return 0

    def _site_online_out_of_stock(self):
        if self._site_online():
            inventory = self.product_json['product']['selectedSku']['inventoryOptions']
            if inventory:
                if inventory[0]['status'] == 'outOfStock':
                    return 1
                return 0
            return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        # Categories aren't included in mobile json data
        if self.product_json['product'].get('breadcrumb'):
            return [b['displayName'] for b in self.product_json['product']['breadcrumb'][1:]]

        categories = self.tree_html.xpath("//div[@class='breadcrumb-child']/a/span/text()")

        if categories:
            return [self._clean_text(c) for c in categories[1:]]

    def _brand(self):
        return self.product_json['product']['product'].get('brandName')

    ##########################################
    ################ FLAGS FOR SPEC TABLE
    ##########################################

    def _specifications(self):
        # Return the 'specifications' html from the product json
        specs = deep_search('productSpecifications', self.product_json) \
                or deep_search('specifications', self.product_json)
        if specs:
            for spec in specs[0]:
                if spec['specificationHeading'] == 'Specifications':
                    return html.fromstring(spec['specificationText'])

    def _spec_table(self):
        specifications = self._specifications()
        if specifications is not None and specifications.xpath('//table'):
            return 1
        return 0

    def _spec_text(self):
        specifications = self._specifications()
        if specifications is not None and not specifications.xpath('//table'):
            return 1
        return 0

    def _spec_content(self):
        c = self._request(self.WEBCOLLAGE_URL.format(self._product_id())).content
        m = re.findall(r'_wccontent = (\{.*?\});', c, re.DOTALL)
        if m and 'Specifications' in m[0]:
            return 1
        return 0

    def _spec_word_count(self):
        specifications = self._specifications()
        if specifications is not None:
            if self._spec_table():
                return len(specifications.xpath('//table')[0].text_content().split())
            else:
                return len(specifications.text_content().split())

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        text = super(SamsclubScraper, self)._clean_text(text)
        # remove anything between style tags
        text = re.sub(re.compile('<style.*?</style>', re.DOTALL), '', text)
        # remove all tags except for ul/li
        text = re.sub('<(?!ul|li|/ul|/li).*?>', '', text)
        # unescape html codes
        text = HTMLParser().unescape(text)
        return text.strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = { 
        # CONTAINER : NONE
        "product_id": _product_id,
        "site_version": _site_version,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "title_seo": _title_seo,
        "model": _model,
        "sku": _sku,
        "upc": _upc,
        "shelf_description": _shelf_description,
        "long_description": _long_description,
        "bullets": _bullets,
        "shelf_description_bullet_count": _shelf_description_bullet_count,
        "variants": _variants,
        "no_longer_available": _no_longer_available,
        "assembled_size": _assembled_size,
        "item_num": _item_num,
        "image_urls": _image_urls,
        "no_image_available": _no_image_available,
        "swatches": _swatches,
        "swatch_image_missing": _swatch_image_missing,
        "has_wwlt": _has_wwlt,
        "wwlt_text": _wwlt_text,

        # CONTAINER : PAGE_ATTRIBUTES
        "video_urls": _video_urls,
        "redirect": _redirect,
        "image_alt_text": _image_alt_text,
        "in_page_360_image_urls": _in_page_360_image_urls,
        "spec_table": _spec_table,
        "spec_text": _spec_text,
        "spec_content": _spec_content,
        "spec_word_count": _spec_word_count,
        "super_enhancement": _super_enhancement,
        "cnet": _cnet,
        "flixmedia": _flixmedia,
        "questions_total": _questions_total,
        "questions_unanswered": _questions_unanswered,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
