#!/usr/bin/python

import re
from lxml import html
from extract_data import Scraper
from spiders_shared_code.quill_variants import QuillVariants
import json
import urllib


class QuillScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    WEBCOLLAGE_POWER_PAGE = 'https://scontent.webcollage.net/quill/power-page?ird=true&channel-product-id={}'
    REVIEW_URL = 'https://www.quill.com/Reviews/GetReviewData?' \
                 'sku={sku}' \
                 '&pageNum=0&sort=dateCreated%3Adesc' \
                 '&isQview=False' \
                 '&loginUrl={login_url}' \
                 '&noReview=False'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.qv = QuillVariants()

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        if not self.tree_html.xpath("//div[contains(@class, 'skuImageZoom')]//img"):
            return True
        self.qv.setupCH(self.tree_html)
        self._extract_webcollage_contents()
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.search('data-product-id="(\d+)"', html.tostring(self.tree_html))
        if product_id:
            return product_id.group(1)

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _brand(self):
        brand = self.tree_html.xpath('//div[@class="formLabel SL_m"]/text()')
        return brand[1] if len(brand) > 1 else None

    def _product_name(self):
        return self.tree_html.xpath("//h1[contains(@class, 'Name')]//text()")[0].strip()
    
    def _model(self):
        model = self.tree_html.xpath('//div[@class="formLabel SL_m"]/text()')
        return model[0].strip() if model else None

    def _description(self):
        description = self.tree_html.xpath('//div[@id="SkuTabDescription"]')
        return self._clean_html(html.tostring(description[0]))

    def _long_description(self):
        description = self.tree_html.xpath('//div[@class="qOverflow"]')
        return self._clean_html(html.tostring(description[0]))

    def _variants(self):
        return self.qv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        urls = self.tree_html.xpath('//ul[@class="carouselInner"]//img/@data-zoomimage')
        image_urls = []
        for url in urls:
            image_urls.append('https:' + url)
        return image_urls

    def _video_urls(self):
        return self.wc_videos if self.wc_videos else None

    ##########################################
    ############### CONTAINER : REVIEWS
    #########################################

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews
        self.is_review_checked = True
        review_data = self.tree_html.xpath('//script[@type="application/ld+json" and contains(text(), "reviewCount")]'
                                           '/text()')
        try:
            review_data = json.loads(review_data[0])
            self.review_count = int(review_data.get('aggregateRating', {}).get('reviewCount', 0))
            self.average_review = float(review_data.get('aggregateRating', {}).get('ratingValue', 0))
        except:
            return

        if not self.review_count:
            return
        login_url = re.search(r'QuillReview\.LoginURL = \'(.*?)\'', html.tostring(self.tree_html))
        sku = self.tree_html.xpath('//input[@id="skuData_Sku"]/@value')
        if not login_url or not sku:
            return

        url = self.REVIEW_URL.format(sku=sku[0], login_url=urllib.quote_plus(login_url.group(1).encode('utf-8')))
        review_html = self._request(url, timeout=5).text
        review_html = html.fromstring(review_html)
        stars = review_html.xpath('//a[contains(@id, "QRratingBreakdownBox")]/text()')
        rating_by_star = []
        for idx, star in enumerate(stars):
            rating_by_star.append([5-idx, int(star.replace('(', '').replace(')', ''))])

        self.reviews = rating_by_star

        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//span[@id="skuPriceLabel"]/span[contains(@class, "price")]/text()')
        return '$' + price[0]

    def _temp_price_cut(self):
        if self.tree_html.xpath('//div[@id="SkuSaveStory"]/span'):
            return 1
        return 0

    def _in_stores(self):
        return 0

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = re.search(r'stock":{"OOS":"(.*?)"', html.tostring(self.tree_html), re.DOTALL)
        if out_of_stock:
            return 1 if out_of_stock.group(1) != 'false' else 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        category_list = []
        categories = self.tree_html.xpath('//div[@id="skuBreadCrumbs"]//li/a/span/text()')
        for category in categories:
            category = category.strip()
            if category and not category == '>':
                category_list.append(category)

        return category_list

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_html(self, html_string):
        # remove all html tags
        html_string = re.sub('<([^\s>]+)[^>]*?>', r'<\1>', html_string)
        # remove extra spaces before and after tags
        html_string = re.sub('>\s+', '>', html_string)
        html_string = re.sub('\s+<', '<', html_string)
        return html_string.strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "description" : _description,
        "model" : _model,
        "long_description" : _long_description,
        "variants" : _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls" : _video_urls,

        # CONTAINER : REVIEWS
        "reviews" : _reviews,

        # CONTAINER : SELLERS
        "price" : _price,
        "temp_price_cut" : _temp_price_cut,
        "in_stores" : _in_stores,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,
        "marketplace" : _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
