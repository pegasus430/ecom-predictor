#!/usr/bin/python

import re
from spiders_shared_code.chewy_variants import ChewyVariants
from extract_data import Scraper
from lxml import html
from product_ranking.guess_brand import guess_brand_from_first_words
from urlparse import urljoin


class ChewyScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = 'Expected URL format is http(s)://www.chewy.com/<item-name>/dp/<item-id>'

    VIDEO_BASE_URL = 'https://fast.wistia.com/embed/medias/{video_id}.json'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.video_urls = None
        self.video_urls_checked = False

        self.cv = ChewyVariants()

    def check_url_format(self):
        if re.match('https?://www\.chewy\.com/[\w-]+/dp/\d+', self.product_page_url):
            return True
        return False

    def not_a_product(self):
        if self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]'):
            self.cv.setupCH(self.tree_html)
            return False
        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.tree_html.xpath('//input[@id="productId"]/@value')[0]

    # specific to chewy.com
    def _item_id(self):
        return self.tree_html.xpath('//input[@id="itemId"]/@value')[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath('//div[@id="product-title"]/h1/text()')[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath('//title/text()')[0].strip()

    def _description(self):
        description = self.tree_html.xpath(
            '//span[@itemprop="description"]'
        )
        if description:
            description = re.sub(r'\s+', ' ', description[0].text_content())
            return self._clear_text(description)

    def _bullets(self):
        bullets = self.tree_html.xpath(
            '//article[@id="descriptions"]/section[contains(@class,"left")]//ul/li/text()'
        )
        if len(bullets) > 0:
            return "\n".join(bullets)

    def _specs(self):
        keys = self.tree_html.xpath(
            '//ul[@class="attributes"]//div[@class="title"]/text()'
        )
        values = self.tree_html.xpath(
            '//ul[@class="attributes"]//div[@class="value"]/text()'
        )
        if keys and values:
            specs = {}
            for i,key in enumerate(keys):
                specs[self._clear_text(key)] = self._clear_text(values[i])
            return specs if specs else None

    def _ingredients(self):
        ingredients = self.tree_html.xpath(
            '//h3[@class="Ingredients-title"]/parent::section/p/text()'
        )
        return [x.strip() for x in ingredients[0].split(',')] if ingredients else None

    def _variants(self):
        return self.cv._variants()

    def _no_longer_available(self):
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = re.search(r'images: \[(.*?)\]', html.tostring(self.tree_html), re.DOTALL)
        if image_urls:
            image_urls = image_urls.group(1).replace("'", "").split(',')
            return [urljoin(self.product_page_url, i.strip()) for i in image_urls if i.strip()]

    def _video_urls(self):
        if self.video_urls_checked:
            return self.video_urls
        self.video_urls_checked = True
        video_urls = []
        videos = self.tree_html.xpath('//a[@data-wistia-vid]/@data-wistia-vid')
        for video_id in videos:
            data = self._request(self.VIDEO_BASE_URL.format(video_id=video_id))
            assets = data.json()['media']['assets']
            asset = next(a for a in assets if a['type'] == 'original')
            video_urls.append(asset['url'])
        if video_urls:
            self.video_urls = video_urls
        return self.video_urls

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        average_review = self.tree_html.xpath('//span[contains(@class, "ugc-list__header--count")]'
                                              '/span[@itemprop="ratingValue"]/text()')
        return float(average_review[0]) if average_review else None

    def _review_count(self):
        review_count = self.tree_html.xpath('//span[@itemprop="reviewCount"]/text()')
        return int(review_count[0]) if review_count else 0

    def _reviews(self):
        reviews = []
        reviews_data = self.tree_html.xpath(
            '//ul[contains(@class, "progress-line--info")]'
            '//span/text()'
        )
        if len(reviews_data) >= 9:
            for i in range(5):
                percent_review = re.search('\d+', reviews_data[i * 2 + 1]).group(0)
                num_review = float(self._review_count()) / 100 * int(percent_review)
                reviews.append([5 - i, int(num_review)])

        return reviews if reviews else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//*[@class="price"]/span/text()')
        return price[0].strip() if price else None

    def _temp_price_cut(self):
        if self.tree_html.xpath('//div[@class="sale-overlay"]'):
            return 1
        return 0

    def _in_stores(self):
        return 0

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath('//div[@id="availability"]/span/text()')[0] == 'In stock':
            return 0
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath(
            '//*[contains(@class,"breadcrumbs")]//span[@itemprop="name"]/text()'
        )
        return categories if categories else None

    def _brand(self):
        brand = self.tree_html.xpath('//span[@itemprop="brand"]/text()')
        return brand[0] if brand else guess_brand_from_first_words(self._product_name())

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    @staticmethod
    def _clear_text(text):
        return re.sub(r'\s+', ' ', text).strip()

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
        "description": _description,
        "bullets": _bullets,
        "specs": _specs,
        "ingredients": _ingredients,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls" : _video_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "temp_price_cut": _temp_price_cut,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review" : _average_review,
        "reviews": _reviews,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
