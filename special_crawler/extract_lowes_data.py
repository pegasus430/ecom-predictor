#!/usr/bin/python

import re
from lxml import html
from urlparse import urlparse, urlunparse

from extract_data import Scraper
from spiders_shared_code.lowes_variants import LowesVariants

class LowesScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.lowes.com/pd/<prod-name>/<prod-id>"

    REVIEW_URL = "http://lowes.ugc.bazaarvoice.com/0534/{}/reviews.djs?format=embeddedhtml"

    HEADERS = {'Cookie': 'sn=3095'} # San Francisco Lowe's

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self._set_proxy()

        self.lv = LowesVariants()
        self.webcollage_content = None
        self.reviews_is_checked = False
        self.video_urls_checked = False
        self.video_urls = []

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def check_url_format(self):
        m = re.match('^https?://www.lowes.com/pd/.+/\d+(\?.*)?$', self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]'):
            self.lv.setupCH(self.tree_html)
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return urlparse(self.product_page_url).path.split('/')[-1]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//div[contains(@class, 'grid-100') and contains(@class, 'pd-title')]//h1/text()")
        return product_name[0].strip() if product_name else None

    def _model(self):
        return re.search('"modelId":"([^"]*)"', html.tostring(self.tree_html)).group(1)

    def _item_num(self):
        return re.search('"itemNumber":"([^"]*)"', html.tostring(self.tree_html)).group(1)

    def _description(self):
        description = None
        blocks = self.tree_html.xpath('//div[@class="grid-50"]')
        if blocks:
            desc_block = blocks[0]
            description = desc_block.xpath('.//p/text()')
            if not description:
                description = desc_block.xpath('.//ul')
                description = html.tostring(description[0]) if description else None
            else:
                description = description[0]

        return self._clean_text(description) if description else None

    def _bullets(self):
        bullets = self.tree_html.xpath('//div[@id="collapseDesc"]//li/text()')
        if len(bullets) > 0:
            return "\n".join(bullets)

    def _swatches(self):
        swatches = []

        for menuitem in self.tree_html.xpath('//li[@role="menuitem"]'):
            for media in menuitem.xpath('a/div[@class="media"]'):
                swatch = {
                    'color' : media.xpath('div[contains(@class,"media-body")]/span/text()')[0],
                    'hero' : 1,
                    'hero_image' : media.xpath('div[contains(@class,"media-left")]/img/@src'),
                }

                swatches.append(swatch)

        if swatches:
            return swatches

    def _variants(self):
        return self.lv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('.//a[@class="js-epc-trigger"]//img[@data-type!="video"]/@data-src')
        return ['https:' + i if not i.startswith('http') else i for i in image_urls]

    def _video_urls(self):
        if not self.video_urls_checked:
            self.video_urls_checked = True
            raw_video_urls = self.tree_html.xpath('//img[@alt="Product Video"]/@src')
            if raw_video_urls:
                for v in raw_video_urls:
                    url = 'https:' + v.replace('image', 'content')
                    if self._check_video_url(url):
                        self.video_urls.append(url)
        return self.video_urls if self.video_urls else None

    def _wc_360(self):
        if self.tree_html.xpath('//a[contains(@data-setid, "spinset")]'):
            return 1
        return 0

    def _webcollage(self):
        if not self.is_webcollage_checked:
            self.is_webcollage_checked = True

            webcollage_src = self.tree_html.xpath('//iframe[@id="productVideoFrame"]/@data-src')

            if webcollage_src:
                self.webcollage_content = self._request(webcollage_src[0], use_proxies=False).content

        if self.webcollage_content:
            return 1

        return 0

    def _reviews(self):
        if self.reviews_is_checked:
            return self.reviews

        self.reviews_is_checked = True

        scheme, netloc, url, params, query, fragment = urlparse(self.product_page_url)
        review_url = urlunparse((scheme, netloc, url + '/reviews', '', '', ''))

        resp = self._request(review_url)
        if resp.ok:
            review_html = html.fromstring(resp.content)

            review_count = review_html.xpath('//span[contains(@class, "reviews-number")]/text()')
            if review_count:
                review_count = re.search(r'\d+', review_count[0])
                self.review_count = int(review_count.group()) if review_count else None

            average_review = review_html.xpath(
                '//div[contains(@class, "rating-average")]//span[@itemprop="ratingValue"]/text()'
            )
            if average_review:
                average_review = re.search(r'\d*\.?\d+', average_review[0])
                self.average_review = float(average_review.group()) if average_review else None

            reviews = []
            review_groups = review_html.xpath('//div[contains(@class, "legend-list")]//div[@role="listitem"]')
            for review_group in review_groups:
                rating = review_group.xpath('.//div[contains(@class, "grid-45")]//span//descendant::text()')
                rating = re.search(r'\d+', rating[0]) if rating else None
                rating = int(rating.group()) if rating else None

                counts = review_group.xpath('.//div[contains(@class, "grid-20")]//span/text()')
                counts = re.search(r'\d+', counts[0]) if counts else None
                counts = int(counts.group()) if counts else 0

                if rating:
                    reviews.append([rating, counts])

            if reviews:
                self.reviews = reviews

        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//*[@itemprop="price"]/@content')[0]
        return '$' + price

    def _price_currency(self):
        return self.tree_html.xpath('//*[@itemprop="PriceCurrency"]/@content')[0]

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath('//*[@itemprop="name"]/text()') or None

    def _brand(self):
        return self.tree_html.xpath('//meta[@itemprop="brand"]/@content')[0]

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _check_video_url(self, url):
        resp = self._request(url, verb='head')
        if resp.status_code == 200:
            return True
        return False

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "model" : _model,
        "item_num" : _item_num,
        "description" : _description,
        "bullets": _bullets,
        "swatches" : _swatches,
        "variants" : _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,
        "webcollage" : _webcollage,
        "wc_360": _wc_360,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price" : _price,
        "price_currency" : _price_currency,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
