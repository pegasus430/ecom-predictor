#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
from extract_data import Scraper

class CurrysScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.currys.co.uk/.*$"
    BASE_URL_WEBCOLLAGE_CONTENTS = "http://content.webcollage.net/currys/power-page?ird=true&channel-product-id={}"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.extracted_webcollage_contents = False
        self.webcollage_contents = None
        self.has_webcollage_360_view = False
        self.has_webcollage_emc_view = False
        self.has_webcollage_video_view = False
        self.has_webcollage_pdf = False
        self.has_webcollage_product_tour_view = False
        self.webcollage_videos = []

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^http://www.currys.co.uk/.*$", self.product_page_url)
        return not not m

    def not_a_product(self):
        """Checks if current page is not a valid product page
        (an unavailable product page or other type of method)
        Overwrites dummy base class method.
        Returns:
            True if it's an unavailable product page
            False otherwise
        """
        try:
            divs = self.tree_html.xpath('//div[@id="product-main"]//div[contains(@class,"product-gallery")]')

            if len(divs) < 1:
                raise Exception()

        except Exception:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

        return canonical_link

    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _product_id(self):
        product_id = self.tree_html.xpath('//input[@name="sFUPID"]/@value')[0]
        return product_id

    def _site_id(self):
        return None

    def _status(self):
        return "success"

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        arr = self.tree_html.xpath('//h1[contains(@class,"page-title")]//text()')
        arr = [r.strip() for r in arr if len(r.strip()) > 0]
        return " ".join(arr)

    def _product_title(self):
        arr = self.tree_html.xpath('//h1[contains(@class,"page-title")]//text()')
        arr = [r.strip() for r in arr if len(r.strip()) > 0]
        return " ".join(arr)

    def _title_seo(self):
        arr = self.tree_html.xpath('//h1[contains(@class,"page-title")]//text()')
        arr = [r.strip() for r in arr if len(r.strip()) > 0]
        return " ".join(arr)

    def _model(self):
        return None

    def _upc(self):
        return self.tree_html.xpath("//p[@class='upc']/span[@class='value']/text()")[0].strip()

    def _features(self):
        features_list = list(set(self.tree_html.xpath('//div[contains(@class,"main-desc")]//h2/following-sibling::ul/li/text()')))

        if features_list:
            return features_list

        return None

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _model_meta(self):
        return None

    def _description(self):
        short_description = self.tree_html.xpath('//div[@id="product-info"]')[0].text_content().strip()

        if short_description:
            return short_description

        return None

    def _long_description(self):
        return None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        image_list = self.tree_html.xpath('//div[@id="carousel"]//li[contains(@class,"prd-image")]/a/@href')
        if not image_list:
            # single image
            image_list = self.tree_html.xpath('//img[@class="product-image"]/@src')

        return image_list if image_list else None

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        video_list = []
        if video_list:
            return video_list

        return None

    def _video_count(self):
        videos = self.tree_html.xpath('//div[@id="video"]//iframe')

        if videos:
            return len(videos)

        return 0

    def _pdf_urls(self):
        pdf_links = list(set(self.tree_html.xpath("//a[contains(@href,'.pdf')]/@href")))

        if pdf_links:
            return pdf_links

        return None

    def _pdf_count(self):
        if self._pdf_urls():
            return len(self._pdf_urls())

        return 0

    def _wc_360(self):
        self._extract_webcollage_contents()
        return 0

    def _wc_emc(self):
        self._extract_webcollage_contents()

        if self.webcollage_contents:
            return 1

    def _wc_video(self):
        return 0

    def _wc_pdf(self):
        self._extract_webcollage_contents()

        if self.webcollage_contents.xpath("//a[contains(@href,'.pdf')]/@href"):
            return 1

        return 0

    def _wc_prodtour(self):
        self._extract_webcollage_contents()

        if self.webcollage_contents:
                return 1

        return 0

    def _extract_webcollage_contents(self):
        if self.extracted_webcollage_contents:
            return self.webcollage_contents

        return None

    def _webcollage(self):
        """Uses video and pdf information
        to check whether product has any media from webcollage.
        Returns:
            1 if there is webcollage media
            0 otherwise
        """
        if self._wc_360() == 1 or self._wc_prodtour() == 1or self._wc_pdf() == 1 or self._wc_emc() == 1 or self._wc_video() == 1:
            return 1

        return 0

    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    def _no_image(self):
        return None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        if self._review_count() > 0:
            average_review = self.tree_html.xpath(
                "//div[@id='product-main']//div[contains(@class,'reevoo-custom-badge')]"
                "/span[contains(@class,'reevoo-score')]/@class")
            average_review = float(re.findall(r'score-(\d+)', average_review[0])[0])/2
            return average_review

        return None

    def _review_count(self):
        review_count = self.tree_html.xpath("//div[@class='reevoo-custom-badge']/span[@class='print-only']/text()")[0].split(" ")

        if review_count:
            return int(review_count[0])

        return 0

    def _max_review(self):

        return None

    def _min_review(self):

        return None

    def _reviews(self):

        return None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return self.tree_html.xpath("//*[@data-key='current-price']//text()")[0].strip()

    def _price_amount(self):
        return float(self.tree_html.xpath("//*[@data-key='current-price']//text()")[0][1:].replace(",", ""))

    def _price_currency(self):
        return "EUR"

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    def _seller_from_tree(self):
        return None

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath("//div[contains(@class,'breadcrumb')]/a/span/text()")

        return categories[1:]

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "url" : _url, \
        "event" : _event, \
        "product_id" : _product_id, \
        "site_id" : _site_id, \
        "status" : _status, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "model" : _model, \
        "upc" : _upc,\
        "features" : _features, \
        "feature_count" : _feature_count, \
        "model_meta" : _model_meta, \
        "description" : _description, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_count" : _image_count,\
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "no_image" : _no_image, \
        "pdf_count" : _pdf_count, \
        "pdf_urls" : _pdf_urls, \
        "wc_360": _wc_360, \
        "wc_emc": _wc_emc, \
        "wc_video": _wc_video, \
        "wc_pdf": _wc_pdf, \
        "wc_prodtour": _wc_prodtour, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "canonical_link": _canonical_link,

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \
        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "in_stores" : _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
        "marketplace" : _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \
        "loaded_in_seconds" : None, \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        "mobile_image_same" : _mobile_image_same, \
    }
