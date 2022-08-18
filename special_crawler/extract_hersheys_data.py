#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html
import time
import requests
from extract_data import Scraper

class HersheysScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.hersheysstore.com/product/<product-id>"

    def check_url_format(self):
        m = re.match(r"^http://www.hersheysstore.com/product/([a-zA-Z0-9\-])", self.product_page_url)
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
            page_title = self.tree_html.xpath("//title/text()")[0]
        except Exception:
            page_title = None
            return True
        if page_title.find("Not Found")>=0:
            return True

        else:
            return False


    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _url(self):
        return self.product_page_url

    def _event(self):
        return None

    def _product_id(self):
        return self.tree_html.xpath('//span[@id="eitemNo"]')[0].text[7:].strip()

    def _site_id(self):
        return None

    def _status(self):
        return 'success'




    ##########################################
    ################ CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath('//h1[@class="prod_title"]/span[@class="prod_title_webname1"]')[0].text

    def _product_title(self):
        return self.tree_html.xpath('//h1[@class="prod_title"]/span[@class="prod_title_webname1"]')[0].text
        #return None

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _model(self):
        return None


    def _asin(self):
        return None

    def _features(self):
        return None

    def _feature_count(self):
        return None

    def _model_meta(self):
        return None


    def _description(self):
        description =" ".join(self.tree_html.xpath('//div[@class="featuresBenefits"]//text()')).strip()
        if len(description)>0:
            return description
        return None


    def _long_description(self):
        return None


    def _long_description_helper(self):
        return None




    ##########################################
    ################ CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _meta_tags(self):
        tags = map(lambda x:x.values() ,self.tree_html.xpath('//meta[not(@http-equiv)]'))
        return tags

    def _meta_tag_count(self):
        tags = self._meta_tags()
        return len(tags)

    #returns 1 if the mobile version is the same, 0 otherwise
    def _mobile_image_same(self):
        url = self.product_page_url
        mobile_headers = {"User-Agent"  : "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_2_1 like Mac OS X; en-us) AppleWebKit/533.17.9 (KHTML, like Gecko) Version/5.0.2 Mobile/8C148 Safari/6533.18.5"}
        pc_headers = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        r=requests.get(url, headers=pc_headers)
#        print r.cookies
        img_list = []
        for h in [mobile_headers, pc_headers]:
            contents = requests.get(url, headers=h).text
            tree = html.fromstring(contents)
            image_url = self._image_urls(tree)
            if image_url==None: image_url=[]
#            print '\n\n\nImage URL:', image_url, '\n\n\n'
            img_list.extend(image_url)
        if len(img_list) == 2:
            return img_list[0] == img_list[1]
        return None

    def _image_urls(self, tree = None):
        if tree == None:
            tree = self.tree_html
        image_url = self.tree_html.xpath('//ul[@class="slides cf"]//a/@href')
        if len(image_url)==0:
            image_url = self.tree_html.xpath('//ul[@class="slides cf"]//img/@src')
        if len(image_url) > 0:
            # check if this is a "no image" image
            # this may return a decoder not found error
            try:
                if self._no_image(image_url[0]):
                    return None
            except Exception, e:
                print "image_urls WARNING: ", e.message
        return image_url


    def _mobile_image_url(self):
        return None

    def _image_count(self):
        imgs = self._image_urls()
        if imgs==None: return 0
        return len(imgs)

    # return 1 if the "no image" image is found
#    def _no_image(self):
#        return None

    def _video_urls(self):
        return None

    def _video_count(self):
        return None

    # return one element containing the PDF
    def _pdf_urls(self):
        return None

    def _pdf_count(self):
        urls = self._pdf_urls()
        if urls:
            return len(urls)
        return None

    def _webcollage(self):
        return None

    # extract htags (h1, h2) from its product product page tree
    def _htags(self):
        htags_dict = {}
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    # extract meta "keywords" tag for a product from its product page tree
    # ! may throw exception if not found
    def _keywords(self):
        return self.tree_html.xpath('//meta[@name="keywords"]/@content')[0]





    ##########################################
    ################ CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        return None

    def _review_count(self):
        return None

    def _max_review(self):
        return None

    def _min_review(self):
        return None





    ##########################################
    ################ CONTAINER : SELLERS
    ##########################################

    # extract product price from its product product page tree
    def _price(self):
        price = self.tree_html.xpath("//span[contains(@class, 'prod_item_price')]//text()")
        if price:
            return price[0].strip()
        return None

    def _in_stores_only(self):
        return None

    def _in_stores(self):
        return None

    def _owned(self):
        return 1

    def _owned_out_of_stock(self):
        av = self.tree_html.xpath("//span[contains(@class, 'availability1')]//text()")
        if "In Stock" in av:
            return 0
        return 1

    def _marketplace(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None

    # extract product seller information from its product product page tree (using h2 visible tags)
    def _seller_from_tree(self):
         return None




    ##########################################
    ################ CONTAINER : CLASSIFICATION
    ##########################################

    # extract the department which the product belongs to
    def _category_name(self):
##        all = self._categories()
##        if all != None and len(all) > 1:
##            if all[-1]=="Search":
##                return all[-2]
##            return all[-1]
        return None

    # extract a hierarchical list of all the departments the product belongs to
    def _categories(self):
##        all = self.tree_html.xpath("//ol[@class='breadcrumb']//li//text()")
##        all = map(lambda t: self._clean_text(t), all)
##        alln = [m for m in all if m != '']
##        return alln
        return None

    def _brand(self):
        return "HERSHEY'S"




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
        "upc" : _asin,\
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
   #     "no_image" : _no_image, \
        "pdf_count" : _pdf_count, \
        "pdf_urls" : _pdf_urls, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "meta_tags": _meta_tags,\
        "meta_tag_count": _meta_tag_count,\

        # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \

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
    }


