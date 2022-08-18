#!/usr/bin/python
#  -*- coding: utf-8 -*-

import re
from lxml import html
import requests

from extract_data import Scraper

from spiders_shared_code.wag_variants import WagVariants

class WagScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = ("Expected URL format is http(s)://ww"
                           "w\.wag\.com/.*/p/[a-zA-Z0-9\-]+(\?.*)?")

    reviews_tree = None
    max_score = None
    min_score = None
    review_count = None
    average_review = None
    reviews = None

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.wg = WagVariants()
        self.product_json = None
        self.image_json = None
        self.reviews = None
        self.wc_360 = 0
        self.wc_emc = 0
        self.wc_video = 0
        self.wc_pdf = 0
        self.wc_prodtour = 0
        self.is_webcollage_contents_checked = False
        self.is_video_checked = False
        self.video_urls = []

    def check_url_format(self):
        # for ex: hhttps://www.wag.com/cat/p/fiesta-petware-bowl-663535
        m = re.match(r"^http(s)?://www\.wag\.com/.*/p/[a-zA-Z0-9\-]+(\?.*)?",
                     self.product_page_url)
        return not not m

    def not_a_product(self):
        '''Overwrites parent class method that determines if current page
        is not a product page.
        Currently for Amazon it detects captcha validation forms,
        and returns True if current page is one.
        '''
        is_product = self.tree_html.xpath(
            '//*[@property="og:type" and @content="product"]')
        return not bool(is_product)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_ids = self.tree_html.xpath('//@productid')
        product_id = [x for x in product_ids if x in self._url()]
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@itemprop="name"]/text()')
        return product_name[0].strip() if product_name else None

    def _product_title(self):
        product_title = self.tree_html.xpath('//h1[@itemprop="name"]/text()')
        return product_title[0].strip() if product_title else None

    def _title_seo(self):
        title_seo = self.tree_html.xpath("//title//text()")
        return title_seo[0].strip() if title_seo else None

    def _model(self):
        name = self._product_title()
        models = re.findall('Model ([\w\W]+)', name)
        return models[0] if models else None

    def _upc(self):
        return None

    def _features(self):
        _product_id = self._product_id()
        tab = self.tree_html.xpath(
            '//li[@productid="%s"]/a[em['
            'text()="Description"]]/@id' % _product_id)[0]

        tab_number = re.search('Tab(\d+)Header', tab).group(1)
        features = list(set(self.tree_html.xpath(
            '//*[@id="Tab%sDetailInfo"]//li/text()' % tab_number)))

        descriptContentBox = ''.join(self.tree_html.xpath(
            '//*[@id="Tab%sDetailInfo"]//text()' % tab_number))

        features += list(set(
            re.findall(u'\u2022 (.*)', descriptContentBox)))
        return [x.strip() for x in features] if features else None

    def _feature_count(self):
        features = self._features()
        if features is None:
            return 0
        return len(features)

    def _model_meta(self):
        return None

    def _description(self):
        _product_id = self._product_id()
        tab = self.tree_html.xpath(
            '//li[@productid="%s"]/a[em['
            'text()="Description"]]/@id' % _product_id)[0]

        tab_number = re.search('Tab(\d+)Header', tab).group(1)

        rows = (self.tree_html.xpath('//*[@id="Tab%sDetailInfo"]'
                                     '//*[@class="pIdDesContent"]//'
                                     'text()' % tab_number) or
                list(set(self.tree_html.xpath('//*[@id="Tab%sDetailInfo"]'
                                              '//p/text()' % tab_number))))

        rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
        description = "\n".join(rows)

        return description if description else None

    def _variants(self):
        self.wg.setupCH(self.tree_html, self.product_page_url)
        return self.wg._variants()

    def _swatches(self):
        self.wg.setupCH(self.tree_html, self.product_page_url)
        return self.wg._swatches()

    def _long_description(self):
        return self._description()

    def _ingredients(self):
        try:
            _product_id = self._product_id()
            tab = self.tree_html.xpath(
                '//li[@productid="%s"]/a[em['
                'text()="Ingredients"]]/@id' % _product_id)[0]
            tab_number = re.search('Tab(\d+)Header', tab).group(1)
            ingredients = self.tree_html.xpath(
                '//*[@id="Tab%sDetailInfo"]//'
                '*[@class="pIdDesContent"]//text()' % tab_number)[0]

            r = re.compile(r'(?:[^,(]|\([^)]*\))+')
            ingredients = r.findall(ingredients)
            ingredients = [ingredient.strip() for ingredient in ingredients]
            return ingredients if ingredients else []
        except:
            return []

    def _ingredient_count(self):
        ingredients = self._ingredients()
        return len(self._ingredients()) if ingredients else 0

    def _no_longer_available(self):
        no_longer_aval = self.tree_html.xpath(
            '//*[@class="discontinuedBanner"]')
        if no_longer_aval:
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//*[@pagetype="F-PDPImage"]//@href')
        return ["http:" + x for x in image_urls] if image_urls else None

    def _image_count(self):
        image_urls = self._image_urls()
        return len(image_urls)

    def _video_urls(self):
        return None

    def _video_count(self):
        if self._video_urls():
            return len(self._video_urls())

        return 0

    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        urls = self._pdf_urls()
        if urls is not None:
            return len(urls)
        return 0

    def _extract_webcollage_contents(self):
        return None

    def _wc_360(self):
        self._extract_webcollage_contents()
        return self.wc_360

    def _wc_emc(self):
        self._extract_webcollage_contents()
        return self.wc_emc

    def _wc_video(self):
        self._extract_webcollage_contents()
        return self.wc_video

    def _wc_pdf(self):
        self._extract_webcollage_contents()
        return self.wc_pdf

    def _wc_prodtour(self):
        self._extract_webcollage_contents()
        return self.wc_prodtour

    def _webcollage(self):
        self._extract_webcollage_contents()

        if self.wc_video == 1 or self.wc_emc or self.wc_360 == 1 or\
                self.wc_pdf == 1 or self.wc_prodtour == 1:
            return 1

        atags = self.tree_html.xpath("//a[contains(@href, 'webcollage.net/')]")

        if len(atags) > 0:
            return 1

        return 0

    # extract htags (h1, h2) from its product product page tree
    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t),
                               self.tree_html.xpath(
                               "//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t),
                               self.tree_html.xpath(
                               "//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    # populate the reviews_tree variable for use by other functions
    def _load_reviews(self):
        try:
            num_reviews = self.tree_html.xpath(
                '//*[@itemprop="reviewCount"]/@content')[0]
            average_rating = self.tree_html.xpath(
                '//*[@itemprop="ratingValue"]/@content')[0]

            rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

            stars = self.tree_html.xpath(
                '//*[@class="pr-ratings-histogram-content"]'
                '//p[@class="pr-histogram-label"]//span/text()')

            values = self.tree_html.xpath(
                '//*[@class="pr-ratings-histogram-content"]'
                '//p[@class="pr-histogram-count"]//span/text()')

            if stars and values:
                stars = [re.search('\d+', x).group(0) for x in stars]
                values = [re.search('\d+', x).group(0) for x in values]

                for (star, value) in zip(stars, map(int, values)):
                    rating_by_star[star] += value

            review_id = re.findall('PowerReview.groupId = (\d+);',
                                   html.tostring(self.tree_html))

            if review_id:
                review_id = review_id[0].split('-')[-1]

            else:
                review_id = self._product_id()

            if len(review_id) < 6:
                review_id = "0" + review_id

            review_url = ("https://www.wag.com/amazon_reviews/%s/%s/%s"
                          "/mostrecent_default.html" % (review_id[0:2], review_id[2:4], review_id[4:]))

            r = requests.get(review_url)
            if r and r.status_code == 200:
                review_tree = html.fromstring(r.text)
                stars = review_tree.xpath(
                    '//*[@class="pr-info-graphic-amazon"]'
                    '//dd/text()')
                values = review_tree.xpath(
                    '//*[@class="pr-info-graphic-amazon"]'
                    '//dd/text()')
                if stars and values:
                    stars = [x for x in stars if re.match('(\d+) star', x)]
                    stars = [re.search(
                        '(\d+) star', x).group(1) for x in stars]
                    values = [x.strip() for x in values if x.strip()]
                    values = [x for x in values if re.match(
                        '.*\((\d+)\)', x)]
                    values = [re.search(
                        '\((\d+)\)', x).group(1) for x in values]
                    for (star, value) in zip(stars, map(int, values)):
                        rating_by_star[star] += value

            self.reviews = (num_reviews, average_rating, rating_by_star)

        except:
            pass

    def _average_review(self):
        if not self.reviews:
            self._load_reviews()
        return self.reviews[1]

    def _review_count(self):
        if not self.reviews:
            self._load_reviews()
        return self.reviews[0]

    def _max_review(self):
        if not self.reviews:
            self._load_reviews()
        rating_by_star = self.reviews[2]
        try:
            return max([x for x in rating_by_star if rating_by_star[x]])
        except:
            return None

    def _min_review(self):
        if not self.reviews:
            self._load_reviews()
        rating_by_star = self.reviews[2]
        try:
            return min([x for x in rating_by_star if rating_by_star[x]])
        except:
            return None

    def _reviews(self):
        if not self.reviews:
            self._load_reviews()
        return self.reviews[2]

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return self.tree_html.xpath('//*[@itemprop="price"]/@content')[0].strip()

    def _price_amount(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        return float(price_amount)

    def _price_currency(self):
        return self.tree_html.xpath(
            '//*[@itemprop="priceCurrency"]/@content')[0]

    def _in_stores(self):
        return None

    def _marketplace(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        # marketplace_lowest_price - the lowest of marketplace prices
        return None

    def _marketplace_out_of_stock(self):
        return None

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return self._no_longer_available()

    def _in_stores_out_of_stock(self):
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        _all = self.tree_html.xpath(
            '//*[contains(@class,"positionNav")]/a/text()')
        out = [self._clean_text(r) for r in _all]
        return out[1:] if out else None

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
#    def _clean_text(self, text):
#        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################
    DATA_TYPES = { \
        # CONTAINER : NONE
        "url": _url,
        "product_id": _product_id,

        # CONTAINER: PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "features": _features,
        "feature_count": _feature_count,
        "description": _description,
        "model": _model,
        "long_description": _long_description,
        "variants": _variants,
        "swatches": _swatches,
        "ingredients": _ingredients,
        "ingredient_count": _ingredient_count,
        "no_longer_available": _no_longer_available,

        # CONTAINER: PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "image_count": _image_count,
        "wc_360": _wc_360,
        "wc_emc": _wc_emc,
        "wc_video": _wc_video,
        "wc_pdf": _wc_pdf,
        "wc_prodtour": _wc_prodtour,
        "webcollage": _webcollage,
        "htags": _htags,
        "keywords": _keywords,
        "mobile_image_same": _mobile_image_same,

        # CONTAINER: SELLERS
        "price": _price,
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "marketplace_sellers": _marketplace_sellers,
        "marketplace_lowest_price": _marketplace_lowest_price,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER: CLASSIFICATION
        "categories": _categories,
        "category_name": _category_name,
        "brand": _brand,

        "loaded_in_seconds": None}

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = {
        # CONTAINER: CLASSIFICATION
        # CONTAINER: REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "max_review": _max_review,
        "min_review": _min_review,
        "reviews": _reviews,

        # CONTAINER: PAGE_ATTRIBUTES
        "pdf_urls": _pdf_urls,
        "pdf_count": _pdf_count,
        "video_urls": _video_urls,
        "video_count": _video_count,
    }

