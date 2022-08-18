#!/usr/bin/python

import urllib
import re
import sys
import json
import os.path
import urllib, cStringIO
from io import BytesIO
from PIL import Image
import mmh3 as MurmurHash
from lxml import html
import time
import requests
from extract_data import Scraper

class PGEStore(Scraper):
    '''
        PGEStore has a lot of code commented out, they changed the format of the site and the commented code is saved as a backup
    '''


    ##########################################
    ############### PREP
    ##########################################
    INVALID_URL_MESSAGE = "Expected URL format is http://www.pgestore.com/[0-9a-zA-Z,/-]+\.html or http://www.pgshop.com/[0-9a-zA-Z,/-]+\.html"
    
    reviews_tree = None
    max_score = None
    min_score = None
    reviews = None
    pdfs = None
    
    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        non_product_arr = ["-about-us.html", "pgshop-faqs.html", "holiday-calendar-2014.html"]
        for non_product in non_product_arr:
            if non_product in self.product_page_url:
                return False
        m = re.match(r"^http://www.pgestore.com/[0-9a-zA-Z,/\-\.\_]+\.html", self.product_page_url)
        n = re.match(r"^http://www.pgshop.com/[0-9a-zA-Z,/\-\.\_]+\.html", self.product_page_url)

        return (not not m) or (not not n)





    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _product_id(self):
        product_id = self.tree_html.xpath('//*[contains(@itemprop, "productID")]//text()')[0]
        product_id = re.findall("([0-9]+)", product_id)[0]
        return product_id

    def _site_id(self):
        return None

    def _status(self):
        return "success"





    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self._clean_text(self.tree_html.xpath("//h1[@class='product-name']//text()")[0])

    def _product_title(self):
        return self._clean_text(self.tree_html.xpath("//h1[@class='product-name']//text()")[0])

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _model(self):
        return None

    def _upc(self):
        return self.tree_html.xpath('//div[@id="prodSku"]//text()')[0]

    def _features(self):
        return self.tree_html.xpath('//div[contains(@class, "main-column vp")]/ul/li//text()')

    def _feature_count(self):
        return len(self._features())

    def _model_meta(self):
        return None

    def _description(self):
        accordions = self.tree_html.xpath('//div[contains(@class, "accordion-container vp")]')
        description = None
        long_des = None
        for accordion in accordions:
            h3 = " ".join(accordion.xpath('.//h3//text()')).strip()
            if h3 == "Description":
                description = [d.strip() for d in accordion.xpath(".//div[contains(@class, 'accordion-content')]//text()") if len(d.strip()) > 0]
                description = "\n".join(description).strip()
            if h3 == "Product Details":
                long_des = [d.strip() for d in accordion.xpath(".//div[contains(@class, 'accordion-content')]//text()") if len(d.strip()) > 0]
                long_des = "\n".join(long_des).strip()

        if description is None:
            return long_des
        return  description

    def _long_description(self):
        accordions = self.tree_html.xpath('//div[contains(@class, "accordion-container vp")]')
        description = None
        long_des = None
        for accordion in accordions:
            h3 = " ".join(accordion.xpath('.//h3//text()')).strip()
            if h3 == "Description":
                description = [d.strip() for d in accordion.xpath(".//div[contains(@class, 'accordion-content')]//text()") if len(d.strip()) > 0]
                description = "\n".join(description).strip()
            if h3 == "Product Details":
                long_des = [d.strip() for d in accordion.xpath(".//div[contains(@class, 'accordion-content')]//text()") if len(d.strip()) > 0]
                long_des = "\n".join(long_des).strip()
        if description is None:
            return None
        return long_des


    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _mobile_image_same(self):
        pass

    def _image_urls(self):
        image_url = self.tree_html.xpath('//div[@class="thumb"]/a/@href')
        return image_url

    def _image_count(self):
        return len(self._image_urls())

    def _video_urls(self):
        video_url = self.tree_html.xpath("//li[starts-with(@class,'video-thumb')]//a/@data-videoid")
        video_url = ["https://www.youtube.com/watch?v=%s" % r for r in video_url]
        return video_url

    def _video_count(self):
        urls = self._video_urls()
        if urls:
            return len(urls)
        return None

    def _pdf_helper(self):
        # if self.pdfs is not None:
        #     url = "http://content.webcollage.net/pgstore/smart-button?ird=true&channel-product-id=%s"%(self._extract_product_id())
        #     contents = urllib.urlopen(url).read()
        #     pdf = re.findall(r'wcobj=\\\"(http:\\/\\/.+?\.pdf)\\\"', str(contents))
        #     if pdf:
        #         self.pdfs = re.sub(r'\\', '', pdf[0])
        return None

    def _pdf_urls(self):
        # self._pdf_helper()
        # return self.pdfs
        return None
        
    def _pdf_count(self):
        urls = self._pdf_urls()
        if urls:
            return len(urls)
        return None

    def _webcollage(self):
        # http://content.webcollage.net/pg-estore/power-page?ird=true&channel-product-id=037000864868
        url = "http://content.webcollage.net/pg-estore/power-page?ird=true&channel-product-id=%s" % self._product_id()
        html = urllib.urlopen(url).read()
        m = re.findall(r'_wccontent = (\{.*?\});', html, re.DOTALL)
        try:
            if ".webcollage.net" in m[0]:
                return 1
        except IndexError:
            pass
        return 0

    def _htags(self):
        htags_dict = {}
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath('//meta[@name="keywords"]/@content')[0]

    def _no_image(self):
        return None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    #populate the reviews_tree variable for use by other functions
    def _load_reviews(self):
        try:
            if not self.max_score or not self.min_score:
                # url = "http://reviews.pgestore.com/3300/PG_00%s/reviews.htm?format=embedded"
                url = "http://pgestore.ugc.bazaarvoice.com/3300-en_us/%s/reviews.djs?format=embeddedhtml" % self._product_id()
                contents = urllib.urlopen(url).read()
                # contents = re.findall(r'"BVRRRatingSummarySourceID":"(.*?)"}', contents)[0]
                reviews = re.findall(r'<span class=\\"BVRRHistAbsLabel\\">(.*?)<\\/span>', contents)
                score = 5
                for review in reviews:
                    if int(review) > 0:
                        self.max_score = score
                        break
                    score -= 1

                score = 1
                for review in reversed(reviews):
                    if int(review) > 0:
                        self.min_score = score
                        break
                    score += 1

                self.reviews = []
                score = 1
                for review in reversed(reviews):
                    self.reviews.append([score, int(review)])
                    score += 1

                # self.reviews_tree = html.fromstring(contents)
        except:
            pass

    def _average_review(self):
        # self._load_reviews()
        # rating = self.reviews_tree.xpath('//span[@class="BVRRNumber BVRRRatingNumber"]/text()')[0]
        # return rating
        rating = self.tree_html.xpath('//div[@id="ratingsreviews"][1]/span/@data-rating')[0]
        return rating

    def _review_count(self):
        # self._load_reviews()
        # nr = self.reviews_tree.xpath('//span[@class="BVRRCount BVRRNonZeroCount"]/span[@class="BVRRNumber"]/text()')[0]
        # return nr
        count = self.tree_html.xpath('//div[@id="ratingsreviews"][1]/span[2]//text()')[0]
        count = re.sub('[^0-9]', '', count)
        return count

    def _max_review(self):
        self._load_reviews()
        return self.max_score

    def _min_review(self):
        self._load_reviews()
        return self.min_score

    def _reviews(self):
        self._load_reviews()
        return self.reviews


    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        # price = (self.tree_html.xpath('//span[@class="price-nosale"]//text()'))
        price = self.tree_html.xpath('//section[starts-with(@class,"price vm")]//span[starts-with(@class,"price-nosale") or starts-with(@class,"price-sales")]//text()')
        if price:
            return price[0].strip()
        else:
            return None

    def _in_stores_only(self):
        return None

    def _in_stores(self):
        return None

    def _owned(self):
        return 1
    
    def _marketplace(self):
        return 0

    def _seller_from_tree(self):
        return None
    
    def _owned_out_of_stock(self):
        return None

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None




    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    
    def _category_name(self):
        return self._categories()[-1]
    
    def _categories(self):
        all = self.tree_html.xpath("//div[contains(@class, 'breadcrumb-wrap')]/ol/li/a/text()")
        return all[1:]#first one is "Home"

    def _brand(self):
        #return self.tree_html.xpath('//span[contains(@class, "brand")]//text()')[0]
        text = self.tree_html.xpath('//div[contains(@class, "pdp-brand")]//div//a[@class="cta"]/@title')[0]
        # Visit the Pampers brand shop
        text = text.replace('Visit the ', '')
        text = text.replace('brand shop', '')
        brand = text.strip()
        return brand


    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

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
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "in_stores_only" : _in_stores_only, \
        "in_stores" : _in_stores, \
        "owned" : _owned, \
        "owned_out_of_stock" : _owned_out_of_stock, \
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

        "pdf_urls" : _pdf_urls, \
        "pdf_count" : _pdf_count, \

         # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \
    }

