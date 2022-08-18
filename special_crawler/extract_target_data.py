#!/usr/bin/python

import re
import six
import urllib
import requests
import traceback
from lxml import html
from HTMLParser import HTMLParser
from extract_data import Scraper, deep_search
from spiders_shared_code.target_variants import TargetVariants

from cStringIO import StringIO
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

def fetch_bytes(url):
    with requests.Session() as s:
        response = s.get(url, stream=True, timeout=10)
        # need at least 2000 bytes for PIL Image to detect color properly
        for chunk in response.iter_content(2000):
            response.close()
            return chunk

def get_color(rgb):
    if rgb == (0, 0, 0):
        return 'black'
    if rgb == (255, 255, 255):
        return 'white'
    else:
        return 'gray'

class TargetScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://(www|intl).target.com/p/(<prod-name>/)(A|a)-<prod-id>"

    WEBCOLLAGE_POWER_PAGE = 'http://content.webcollage.net/target/power-page?ird=true&channel-product-id={}'
    WEBCOLLAGE_SMART_BUTTON = 'http://content.webcollage.net/target/smart-button?ird=true&channel-product-id={}'
    WEBCOLLAGE_PRODUCT_CONTENT_PAGE = 'http://content.webcollage.net/target/product-content-page?channel-product-id={}'

    PRODUCT_API = 'http://redsky.target.com/v2/pdp/tcin/{product_id}?excludes=taxonomy&storeId=2088'
    QUESTION_API = 'https://redsky.target.com/drax-domain-api/v1/questions?product_id={}'

    VIDEO_BASE_URL = 'http://cdnbakmi.kaltura.com/p/1634272/playManifest/entryId/{}/format/url/protocol/http/a.mp4'

    CATEGORY_URL = 'https://redoak.target.com/content-publish/pages/v1/?url=%2Fp%2Ffoo%2F-%2FA-{}&children=true&breadcrumbs=true&channel=web'

    MODULE_URL = 'https://static.targetimg1.com/itemcontent/sizecharts/html/{module_name}.html'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.tv = TargetVariants()

        self.product_id = None

        self.item_info = None
        self.parent_item_info = None

        self.image_colors_and_sizes_checked = False
        self.image_colors = []
        self.image_res = []

        self.categories = None
        self.categories_checked = False

        self.no_longer_available = 0

    def check_url_format(self):
        m = re.match('https?://(?:www|intl).target.com/p/(?:.*/)?[Aa]-(\d+)', self.product_page_url)
        if m:
            self.product_id = m.group(1)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        self.no_longer_available = 0

        self._get_item_info()

        if not self.item_info.get('item'):
            self.no_longer_available = 1
        else:
            # parent_item_info might be null, that's ok that means there are no variants
            self.tv.setupCH(item_info=self.parent_item_info, selected_upc=self._upc())

    def _item_info_helper(self, product_id):
        return self._request(self.PRODUCT_API.format(product_id = product_id)).json()['product']

    def _get_item_info(self):
        try:
            self.item_info = self._item_info_helper(self._product_id())

            if self.item_info['item'].get('parent_items') and type(self.item_info['item']['parent_items']) is not list:
                self.parent_item_info = self._item_info_helper(self.item_info['item']['parent_items'])

            # if the item itself has children, it is a parent item
            elif self.item_info['item'].get('child_items'):
                self.parent_item_info = self.item_info

        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', str(e))

    def _pre_scrape(self):
        self._extract_webcollage_contents()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_id

    def _tcin(self):
        return self.product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_title = self.item_info['item']['product_description']['title']
        product_title = HTMLParser().unescape(product_title)
        # Convert TM symbol to standard format
        return product_title.replace(u'\u0099', u'\u2122')

    def _upc(self):
        upc = deep_search('upc', self.item_info)
        return upc[0] if upc else None

    def _bullets(self):
        product_desc = self.item_info['item']['product_description']
        if 'soft_bullets' in product_desc:
            bullets = product_desc['soft_bullets']['bullets']
            bullets = [re.sub('&bull;|&nbsp;', '', b).strip() for b in bullets]
            if len(bullets) == 1 and bullets[0].startswith('Produced in'):
                return None
            return '\n'.join(bullets)

    def _features(self):
        features = self.item_info['item']['product_description']['bullet_description']
        features = map(lambda f: re.sub('<.*?>', '', f).strip(), features)
        if features:
            return features

    def _description(self):
        if self.item_info['item'].get('child_items'):
            return self.item_info['item']['child_items'][0]['product_description'].get('downstream_description')

        return self.item_info['item']['product_description'].get('downstream_description')

    def _color(self):
        return self.tv._color()

    def _size(self):
        return self.tv._size()

    def _style(self):
        return self.tv._style()

    def _color_size_stockstatus(self):
        return self.tv._color_size_stockstatus()

    def _stockstatus_for_variants(self):
        return self.tv._stockstatus_for_variants()

    def _variants(self):
        return self.tv._variants()

    def _swatches(self):
        return self.tv._swatches()

    def _details(self):
        return self._description()

    def _mta(self):
        return ''.join(self.item_info['item']['product_description']['bullet_description'])

    def _ingredients(self):
        ingredients = deep_search('ingredients', self.item_info)

        if ingredients:
            r = re.compile(r'(?:[^,(]|\([^)]*\))+')
            ingredients = r.findall(ingredients[0])

            return [ingredient.strip() for ingredient in ingredients]

    def _no_longer_available(self):
        return self.no_longer_available

    def _item_num(self):
        dpci = self.item_info['item'].get('dpci')

        if not dpci:
            dpci = self.item_info['item']['child_items'][0].get('dpci')

        return dpci

    def _parent_id(self):
        parent_id = self.item_info['item'].get('parent_items')
        if isinstance(parent_id, six.string_types):
            return parent_id

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _canonical_link(self):
        return self.item_info['item']['buy_url']

    def _image_names(self):
        image_names = []

        for image_url in self._image_urls():
            image_name = image_url.split('?')[0].split('/')[-1]

            if '_' in image_name:
                image_name = re.findall('\d+', image_name.split('_')[1])[0]
                image_names.append(image_name)
            else:
                image_names.append('Primary')

        return image_names

    def _image_urls(self):
        image_urls = []

        all_images = self.item_info['item']['enrichment']['images']

        if self.item_info['item'].get('child_items'):
            all_images = self.item_info['item']['child_items'][0]['enrichment']['images']

        for images in all_images:
            base_url = images['base_url']

            image_urls.append(base_url + images['primary'])

            for alt in images.get('alternate_urls', []):
                image_urls.append(base_url + alt)

        return [i + '?scl=1' for i in image_urls]

    def _get_image_colors_and_sizes(self):
        if not self.image_colors_and_sizes_checked:
            self.image_colors_and_sizes_checked = True

            for image in self._image_urls():
                try:
                    i = Image.open(StringIO(fetch_bytes(image)))
                    self.image_colors.append(get_color(i.load()[0, 0]))
                except:
                    print traceback.format_exc()
                    self.image_colors.append(None)

                try:
                    width, height = i.size
                    self.image_res.append([width, height])
                except:
                    print traceback.format_exc()
                    self.image_res.append(None)

    def _image_colors(self):
        self._get_image_colors_and_sizes()
        return self.image_colors

    def _image_res(self):
        self._get_image_colors_and_sizes()
        return self.image_res

    def _video_urls(self):
        video_urls = []

        videos = self.item_info.get('item', {}).get('enrichment', {}).get('video_content_list', [])

        for video in videos:
            entry_id = video.get('entry_id')
            if entry_id:
                video_url = self.VIDEO_BASE_URL.format(entry_id)
                if requests.head(video_url).ok:
                    video_urls.append(self.VIDEO_BASE_URL.format(entry_id))

        video_data = dict(self.item_info.get('item', {}))
        video_data.pop('child_items', None)
        videos = deep_search('videos', video_data)
        if isinstance(videos, list) and len(videos) >= 1:
            for video in videos[0]:
                for vf in video.get('video_files', []):
                    video_url = vf.get('video_url')
                    if video_url:
                        video_urls.append('http:' + video_url)

        # Add webcollage videos if there are no other videos
        if not video_urls:
            video_urls.extend(self.wc_videos)

        return video_urls if video_urls else None

    def _pdf_urls(self):
        pdf_urls = self.tree_html.xpath("//a[contains(@href,'.pdf')]/@href")
        if pdf_urls:
            return pdf_urls

    def _ugc(self):
        item_info = self.parent_item_info if self.parent_item_info else self.item_info
        if item_info.get('awesome_shop'):
            awesome_shop = item_info.get('awesome_shop')
            if awesome_shop.get('awesomeshopUrl'):
                url = awesome_shop.get('awesomeshopUrl')
                product_id = self._product_id()
                if product_id in url:
                    req = self._request(url)
                    if req.status_code == 200:
                        content = html.fromstring(req.text)
                        images = content.xpath('//img[@class="card--img"]/@src')
                        if not images:
                            images_data = content.xpath('//section[@id]//div[@role="img"]/@style')
                            images = re.findall(r'url\((.*?)/\w+/\d+x\d+', ' '.join(images_data))
                        if images:
                            return ['https:' + image for image in images] if images else None

            if awesome_shop.get('ugc'):
                return ['http:' + ugc.get('imageUrl') for ugc in awesome_shop.get('ugc') if ugc.get('imageUrl')]
            image_url = awesome_shop.get('ugcHero').get('imageUrl')
            return ['http:' + image_url] if image_url else None

    def _size_chart(self):
        if self.item_info.get('item', {}).get('display_option', {}).get('is_size_chart'):
            return 1
        return 0

    def _questions_total(self):
        return self.item_info.get('question_answer_statistics', {}).get('questionCount')

    def _questions_unanswered(self):
        url = self.QUESTION_API.format(self._product_id())
        headers = {'User-Agent': self.select_browser_agents_randomly()}
        questions = requests.get(url, headers=headers, timeout=10).json()
        return len([q for q in questions if not q.get('AnswerIds')])

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        item_info = self.parent_item_info if self.parent_item_info \
                and self.parent_item_info.get('item') else self.item_info
        tcin = item_info.get('item').get('tcin')
        rating_review = item_info.get(
            'rating_and_review_statistics', {}).get('result', {}) \
            .get(tcin, {}).get('coreStats', {}
        )
        self.average_review = rating_review.get('AverageOverallRating')
        dist = rating_review.get('RatingDistribution', [])
        self.review_count = sum(d.get('Count') for d in dist)
        if self.review_count:
            return [[d.get('RatingValue'), d.get('Count')] for d in reversed(dist)]

    def _how_to_measure(self):
        size_chart_guide_url = self.item_info.get('item', {}).get('enrichment', {}).get('size_chart')
        if size_chart_guide_url:
            chart_name = re.search(r'size-charts/(.*?)\?', size_chart_guide_url)
            if chart_name:
                response = self._request(self.MODULE_URL.format(module_name=chart_name.group(1)))
                if response.status_code == 200:
                    measure_html = html.fromstring(response.content)
                    return int(bool(measure_html.xpath(
                        '//div[contains(@class, "size-chart-content")]'
                        '//div[contains(@class,"size-chart-section measure")]'
                    )))
        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _temp_price_cut(self):
        eyebrow = self.item_info['price']['offerPrice']['eyebrow']
        if eyebrow in ['OnSale', 'Clearance']:
            return 1
        return 0

    def _price(self):
        price = self.item_info['price']['offerPrice']['formattedPrice']
        return price if re.search('\d', price) else None

    def _subscribe_price(self):
        sub_price = None
        price = self._price_amount()
        percent = self._subscribe_discount()
        if price and percent:
            sub_price = round((price * (100 - percent)) / 100, 2)

        return sub_price

    def _subscribe_discount(self):
        percent = None
        promotion = self.item_info.get('promotion', {}).get('promotionList')
        if promotion and promotion[0].get('subscriptionType') == 'SUBSCRIPTION':
            percent = promotion[0].get('rewardValue')

        return percent

    def _site_online(self):
        child_items = self.item_info['item'].get('child_items')
        if child_items:
            if child_items[0]['available_to_promise_network']['availability'] != 'UNAVAILABLE':
                return 1
        elif self.item_info['available_to_promise_network']['availability'] != 'UNAVAILABLE':
            return 1
        return 0

    def _site_online_out_of_stock(self):
        if self._site_online():
            child_items = self.item_info['item'].get('child_items')
            if child_items:
                if child_items[0]['available_to_promise_network']['availability_status'] != 'OUT_OF_STOCK':
                    return 0
            elif self.item_info['available_to_promise_network']['availability_status'] != 'OUT_OF_STOCK':
                return 0
            return 1

    def _in_stores(self):
        child_items = self.item_info['item'].get('child_items')
        if child_items:
            if child_items[0]['available_to_promise_store']['products'][0]['availability_status'] != 'OUT_OF_STOCK':
                return 1
        elif self.item_info['available_to_promise_store']['products'][0]['availability_status'] != 'OUT_OF_STOCK':
            return 1
        return 0

    def _in_stores_out_of_stock(self):
        if self._in_stores():
            child_items = self.item_info['item'].get('child_items')
            if child_items:
                for loc in child_items[0]['available_to_promise_store']['products'][0]['locations']:
                    if loc['availability_status'] not in ['NOT_SOLD_IN_STORE', 'OUT_OF_STOCK']:
                        return 0
            else:
                for loc in self.item_info['available_to_promise_store']['products'][0]['locations']:
                    if loc['availability_status'] not in ['NOT_SOLD_IN_STORE', 'OUT_OF_STOCK']:
                        return 0
            return 1

    def _marketplace(self):
        return 0

    def _in_stores_only(self):
        child_items = self.item_info['item'].get('child_items')
        if child_items:
            discontinued = child_items[0]['available_to_promise_store']['products'][0]['availability_status'] == 'DISCONTINUED'
        else:
            discontinued = self.item_info['available_to_promise_store']['products'][0]['availability_status'] == 'DISCONTINUED'
        if not self._site_online() and (self._in_stores() or discontinued):
            return 1
        return 0

    def _in_stock(self):
        if self._site_online():
            return self._site_online_in_stock()
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        if self.categories_checked:
            return self.categories

        self.categories_checked = True

        for _ in range(3):
            try:
                category_json = self._request(self.CATEGORY_URL.format(self._product_id())).json()
                categories = category_json.get('metadata', {}).get('breadcrumbs')
                if categories:
                    self.categories = [HTMLParser().unescape(c.get('seo_h1')) for c in categories[1:]]
                    return self.categories
            except Exception as e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', 'Error getting categories: {}'.format(e))

    def _brand(self):
        brand = self.item_info['item']['product_brand'].get('manufacturer_brand')
        if brand:
            brand = HTMLParser().unescape(brand)
            # Convert TM symbol to standard format
            return brand.replace(u'\u0099', u'\u2122')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {

        # CONTAINER : NONE
        "product_id" : _product_id,
        "upc" : _upc,
        "tcin" : _tcin,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "bullets": _bullets,
        "features" : _features,
        "description" : _description,
        "variants": _variants,
        "swatches": _swatches,
        "ingredients": _ingredients,
        "details": _details,
        "mta": _mta,
        "no_longer_available": _no_longer_available,
        "item_num": _item_num,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_names" : _image_names,
        "image_urls" : _image_urls,
        "image_colors" : _image_colors,
        "image_res" : _image_res,
        "canonical_link" : _canonical_link,
        "pdf_urls" : _pdf_urls,
        "video_urls" : _video_urls,
        "size_chart" : _size_chart,
        "questions_total": _questions_total,
        "questions_unanswered": _questions_unanswered,

         # CONTAINER : REVIEWS
        "reviews" : _reviews,
        "how_to_measure" : _how_to_measure,

        # CONTAINER : SELLERS
        "price" : _price,
        "temp_price_cut" : _temp_price_cut,
        "marketplace" : _marketplace,
        "in_stores" : _in_stores,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "in_stores_out_of_stock" : _in_stores_out_of_stock,
        "in_stores_only" : _in_stores_only,
        "in_stock" : _in_stock,
        "subscribe_price" : _subscribe_price,
        "subscribe_discount" : _subscribe_discount,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        "ugc": _ugc,
        "parent_id": _parent_id,
        }
