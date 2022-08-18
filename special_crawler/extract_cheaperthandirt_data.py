#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html, etree
from ast import literal_eval
import time
import requests
from extract_data import Scraper
from collections import Counter


class CheaperthandirtScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.cheaperthandirt.com/product/.*$"
    BASE_URL_WEBCOLLAGE_CONTENTS = "https://www.cheaperthandirt.com/product/.*$"

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
        m = re.match(r"^https://www.cheaperthandirt.com/product/.*$", self.product_page_url)
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
            if len(self.tree_html.xpath('//div[@id="detailViewContainer"]')) == 0:
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
        product_id = re.findall(r':(\d+)', self.tree_html.xpath('//div[@id="productData"]/@data-product-id')[0])[0]
        return product_id

    def _site_id(self):
        return None

    def _status(self):
        return "success"






    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath('//h1[@id="h1Title1"]/text()')[0].strip()

    def _product_title(self):
        return self.tree_html.xpath('//h1[@id="h1Title1"]/text()')[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath('//h1[@id="h1Title1"]/text()')[0].strip()

    def _model(self):
        return None

    def _upc(self):
        return self.tree_html.xpath('//div[contains(@class,"prodDetailInfo")]//span[contains(@class,"itemUpc")]/text()')[0].strip()

    def _features(self):
        return None

    def _feature_count(self):
        if self._features():
            return len(self._features())

        return None

    def _model_meta(self):
        return None

    def _description(self):
        short_description = self.tree_html.xpath('//span[@itemprop="description"]/text()')[0].strip()

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
        image_list = self.tree_html.xpath("//div[@id='pdpGallery']//a[contains(@class,'rsImg')]/@href")
        if image_list:
            return image_list
        elif self.tree_html.xpath("//div[contains(@class,'rsContainer')]//img[contains(@class,'rsMainSlideImage')]/@src"):
            main_image_url = self.tree_html.xpath("//div[contains(@class,'rsContainer')]//img[contains(@class,'rsMainSlideImage')]/@src")
            return main_image_url

        return None

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _video_urls(self):
        video_list = []

        self._wc_video()

        if self.webcollage_videos:
            video_list.extend(self.webcollage_videos)

        if video_list:
            return video_list

        return None

    def _video_count(self):
        videos = self._video_urls()

        if videos:
            return len(videos)

        return 0

    def _pdf_urls(self):
        pdf_links = self.tree_html.xpath("//a[contains(@href,'.pdf')]/@href")

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
        self._extract_webcollage_contents()

        video_info_list = self.webcollage_contents.xpath("//div[contains(@class, 'wc-json-data')]/text()")
        video_info_list = [json.loads(literal_eval("'%s'" % video_info)) for video_info in video_info_list]

        if video_info_list:
            if not self.webcollage_videos:
                base_url_list = self.webcollage_contents.xpath("//div[contains(@class, 'wc-media-inner-wrap') and @data-resources-base]/@data-resources-base")
                base_url_list = [url[2:-1].replace("\\", "") for url in base_url_list]
                index = 0

                for video_info in video_info_list:
                    if "videos" in video_info:
                        for sub_video_info in video_info["videos"]:
                            self.webcollage_videos.append(sub_video_info["src"]["src"])
                    else:
                        self.webcollage_videos.append(base_url_list[index] + video_info["src"]["src"])
                        index += 1

            return 1

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

        self.extracted_webcollage_contents = True
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        contents = s.get(self.BASE_URL_WEBCOLLAGE_CONTENTS.format(self._product_id()), headers=h, timeout=5).text

        if contents.startswith("/* Failed Request: Request Reference ID:"):
            self.webcollage_contents = None
        else:
            sIndex = contents.find('html: "') + len('html: "')
            eIndex = contents.find('"\n  }')
            self.webcollage_contents = html.fromstring(contents[sIndex:eIndex])

        return self.webcollage_contents

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
        reviews = self._reviews()
        if reviews:
            return self.average_review
        return None

    def _review_count(self):
        review_count = re.findall(r'(\d+)', self.tree_html.xpath('//div[contains(@class,"reviewTotals")]/text()')[0].strip())

        if review_count:
            return int(review_count[0])

        return 0

    def _max_review(self):
        reviews = self._reviews()

        if reviews:
            for review in reviews:
                if review[1] > 0:
                    return review[0]

        return None

    def _min_review(self):
        reviews = self._reviews()

        if reviews:
            for review in reversed(reviews):
                if review[1] > 0:
                    return review[0]

        return None

    def _reviews(self):
        scores = self.tree_html.xpath('//div[contains(@class,"reviewGroup")]'
                                      '//div[contains(@class,"snippetStars")]'
                                      '//span[contains(@class,"snippetRatingDecimal")]//text()')
        if len(scores) < 1:
            return None
        scores = [int(float(r)) for r in scores]
        self.average_review = sum(scores)*1.0/len(scores)
        rating_mark_dict = Counter(scores)
        rating_mark_list = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
        rating_mark_list_new = []
        for item in rating_mark_list:
            if rating_mark_dict[item[0]] > 0:
                item[1] = rating_mark_dict[item[0]]
            rating_mark_list_new.append(item)
        return rating_mark_list_new

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        return self.tree_html.xpath("//*[@id='productPricing']//span[contains(@class,'pricesale')]//text()")[0].strip()

    def _price_amount(self):
        return float(self._price()[1:])

    def _price_currency(self):
        return "USD"

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        try:
            str = self.tree_html.xpath("//form[@id='mainForm']//span[contains(@class,'messagealert')]//text()")[0]
            if "regret that this item is not available at this time" in str:
                return 1
        except:
            pass

        if len(self.tree_html.xpath("//button[@name='addToBasket']")) < 1:
            return 1
        return 0

    def _in_stores_out_of_stock(self):
        return None

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
        categories = self.tree_html.xpath("//div[contains(@class,'breadcrumb')]/a/text()")

        return categories[1:]

    def _category_name(self):
        return self._categories()[-1]
    
    def _brand(self):
        return self.tree_html.xpath("//div[contains(@class,'prodDetailInfo')]//span[@itemprop='brand']//text()")[0].strip()


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
