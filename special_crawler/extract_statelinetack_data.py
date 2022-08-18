#!/usr/bin/python

import urllib
import re
import sys
import json

from lxml import html, etree
import time
import requests
from extract_data import Scraper


class StateLineTackScraper(Scraper):
    '''
    NOTES : 

    no_image examples:
        http://www.statelinetack.com/item/horseware-pony-liner-200g/E012435/

    '''
    
    ##########################################
    ############### PREP
    ##########################################
    # holds a data from an external request for loading 
    bazaar = None
    INVALID_URL_MESSAGE = "Expected URL format is http://www.statelinetack.com/item/<product-name>/<product-id>/"
    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        #m = re.match("^http://www.amazon.com/dp/[a-zA-Z0-9]+$", self.product_page_url)
        m = re.match(r"^http://www.statelinetack.com/.*?$", self.product_page_url)
        return not not m
    

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _url(self):
        return self.product_page_url

    def _event(self):
        return None
    
    def _product_id(self):
        product_id = self.tree_html.xpath('//input[@id="ctl00_ctl00_CenterContentArea_MainContent_HidBaseNo"]/@value')[0]
        return product_id

    def _site_id(self):
        return None

    def _status(self):
        return "success"





    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        a = self.tree_html.xpath('//*[@itemprop="name"]/text()')[0]
        if a is not None and len(a)>3:
            return a
        return self._product_title()
    
    def _product_title(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0]

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        desc, feat = self._feature_helper()
        return feat

    def _feature_count(self):
        desc, feat = self._feature_helper()
        return len(feat)
        
    def _feature_helper(self):
        tree = self.tree_html
        tree = str(etree.tostring(tree))
        print re.findall(r'\s*<strong>\s*(.*)\s*</strong>\s*', tree)# take care of some crazy spacing issues
        tree = re.sub(r'\s*<strong>\s*(.*)\s*</strong>\s*', r'\1', tree)
        tree = re.sub(r'\n', '', tree)
        tree = html.fromstring(tree)

        full_description = [x.strip() for x in tree.xpath('//div[@id="ItemPageProductSummaryBoxMain"]//div[@class="GreyBoxMiddle"]//text()') if len(x.strip())>0]
        full_description = [x for x in full_description if len(x)>3]
        
        feat_index = [i for i in range(len(full_description)) if re.findall(r'^.{0,10}(F|f)eatures.{0,4}$', full_description[i])]
        spec_index = [i for i in range(len(full_description)) if re.findall(r'^.{0,10}(S|s)pecifications.{0,4}$', full_description[i])]
        if len(feat_index)>0:
            feat_index = feat_index[0]
        else:
            feat_index = 0
            
        if len(spec_index)>0:
            spec_index = spec_index[0]
        else:
            spec_index = None

        if spec_index>0:
            feat = full_description[feat_index+1:spec_index]
        else:
            feat = full_description[feat_index+1:]

        if feat_index>0:
            desc = full_description[0:feat_index]
        else:
            desc = full_description[0]

        if isinstance(desc, str) or isinstance(desc, unicode):
            temp = []
            temp.append(desc)
            desc = temp

        return desc, feat

    def _model_meta(self):
        return None

    def _description(self):
        # description = ([x.strip() for x in self.tree_html.xpath('//div[@id="ItemPageProductSummaryBoxMain"]//div[@class="GreyBoxMiddle"]//text()') if len(x.strip())>0])
        # for row in range(0,6):
        #     if len(description[row]) > 3:#to avoid the heading "product description"
        #         return description[row]
        # return None
        desc, feat = self._feature_helper()
        return ' '.join(desc)


    def _long_description(self):
        return None





    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _no_image(self):
        return None
    
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        #metaimg comes from meta tag
        #metaimg = self.tree_html.xpath('//meta[@property="og:image"]/@content')
        #imgurl comes from the carousel
        imageurl = self.tree_html.xpath('//img[@class="swatch"]/@src')
        
        if(len(imageurl) == 0):
            imageurl = self.tree_html.xpath('//meta[@property="og:image"]/@content')

        return imageurl
    
    def _image_count(self):
        imgurls = self._image_urls()
        return len(imgurls)

    def _video_urls(self):
        #"url":"http://ecx.images-amazon.com/images/I/B1d2rrt0oJS.mp4"
        video_url = self.tree_html.xpath('//script[@type="text/javascript"]') 
        temp = []
        for v in video_url:
            r = re.findall("[\'\"]url[\'\"]:[\'\"](http://.+?\.mp4)[\'\"]", str(v.xpath('.//text()')))
            if r:
                temp.extend(r)
        return temp

    def _video_count(self):
        return len(self._video_urls())

    def _pdf_urls(self):
        moreinfo = self.tree_html.xpath('//div[@class="ItemPageDownloadableResources"]//div//a/@href')
        pdfurl = []
        print '\n\n'
        for a in moreinfo:
            p = re.findall(r'(.*\.pdf)', a)
            pdfurl.extend(p)
        
        baseurl = 'http://www.statelinetack.com/'    
        pdfurl = [baseurl + x[1:] for x in pdfurl] 
        return pdfurl

    def _pdf_count(self):
        return len(self._pdf_urls())

    def _webcollage(self):
        return None

    def _htags_from_tree(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return None

   




    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    
    #bazaar for ratings
    def get_bazaar(self):
        if self.bazaar != None:
            return self.bazaar
        else:
            url = 'http://tabcomstatelinetack.ugc.bazaarvoice.com/3421-en_us/%s/reviews.djs?format=embeddedhtml'
            url = url % (self._product_id())

            contents = urllib.urlopen(url).read()
            # tree = re.findall(r'var materials=(\{.*?\}.*\})', contents)[0]
            # tree = re.sub(r'\\(.)', r'\1', tree)
            # tree = re.findall(r'(\<.*\>)', tree)[0]
            # tree = html.fromstring(contents)

            return contents

    #extract average review, and total reviews  
    def _average_review(self):
        bazaar = self.get_bazaar()
        # avg = bazaar.xpath('//*[contains(@class, "BVRRRatingNumber")]//text()')
        # avg = re.findall(r'<span class=\\"BVRRNumber BVRRRatingRangeNumber\\">(.*?)<\\/span>', bazaar)
        avg = re.findall(r'<span class=\\"BVRRNumber BVRRRatingNumber\\">([0-9.]*?)<\\/span>', bazaar)
        
        return avg[0]

    def _review_count(self):
        bazaar = self.get_bazaar()
        # num = bazaar.xpath('//*[contains(@class, "BVRRRatingRangeNumber")]//text()')
        num = re.findall(r'\<span class\=\\"BVRRNumber\\"\>([0-9]*?)\<\\/span\> review', bazaar)

        return num[0]

    def _max_review(self):
        return None

    def _min_review(self):
        return None

        




    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath("//span[@id='lowPrice']//text()")
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
        return None

    def _marketplace(self):
        return 0

    def _marketplace_sellers(self):
        return None

    def _marketplace_lowest_price(self):
        return None






    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _category_name(self):
        all = self._categories()
        all = map(lambda t: self._clean_text(t), all)
        return all[-1]
    
    def _categories(self):
        all = self.tree_html.xpath('//div[@id="ItemPageBreadCrumb"]//a/text()')
        return all

    def _brand(self):
        return None




    #########################################
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
        "image_urls" : _image_urls, \
        "image_count" : _image_count, \
        "video_urls" : _video_urls, \
        "video_count" : _video_count, \
        "pdf_urls" : _pdf_urls, \
        "pdf_count" : _pdf_count, \
        "webcollage" : _webcollage, \
        "htags" : _htags_from_tree, \
        "keywords" : _keywords, \
        
        # CONTAINER : REVIEWS
        "average_review" : _average_review, \
        "review_count" : _review_count, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "in_stores_only" : _in_stores_only, \
        "in_stores" : _in_stores, \
        "owned" : _owned, \
        "owned_out_of_stock" : _owned_out_of_stock, \
        "marketplace": _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \

        
        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \

        "loaded_in_seconds": None \
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        "mobile_image_same" : _mobile_image_same, \
        "no_image" : _no_image,\
    }




# def _anchors_from_tree(self):
#         description_node = self.tree_html.xpath('//div[contains(@class, "GreyBoxMiddle")]/div/span/span/span/div[3]')[0]
#         links = description_node.xpath(".//a")
#         nr_links = len(links)
#         links_dicts = []
#         for link in links:
#             links_dicts.append({"href" : link.xpath("@href")[0], "text" : link.xpath("text()")[0]})

#         ret = {"quantity" : nr_links, "links" : links_dicts}
#         return ret

#     def _seller_meta_from_tree(self):
#         return self.tree_html.xpath("//meta[@itemprop='brand']/@content")[0]
    
        
#     def _meta_description(self):
#         return self.tree_html.xpath("//meta[@name='Description']/@content")[0]
    
#     def _meta_keywords(self):
#         return self.tree_html.xpath("//meta[@name='Keywords']/@content")[0]
    
    

#     def main(args):
#         # check if there is an argument
#         if len(args) <= 1:
#             sys.stderr.write("ERROR: No product URL provided.\nUsage:\n\tpython crawler_service.py <amazon_product_url>\n")
#             sys.exit(1)
    
#         product_page_url = args[1]
    
#         # check format of page url
#         if not check_url_format(product_page_url):
#             sys.stderr.write(INVALID_URL_MESSAGE)
#             sys.exit(1)
    
#         return json.dumps(product_info(sys.argv[1], ["name", "short_desc", "keywords", "price", "load_time", "anchors", "long_desc"]))

