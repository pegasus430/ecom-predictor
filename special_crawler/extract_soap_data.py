#!/usr/bin/python
#  -*- coding: utf-8 -*-

import urllib
import urllib2
import re
import sys
import json
import os.path
import urllib, cStringIO
from io import BytesIO
from PIL import Image
import mmh3 as MurmurHash
from lxml import html
from lxml import etree
import time
import requests
from extract_data import Scraper


class SoapScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www\.soap\.com/p/(.*)"

    reviews_tree = None
    max_score = None
    min_score = None
    review_count = None
    average_review = None
    reviews = None
    feature_count = None
    features = None
    video_urls = None
    video_count = None
    image_urls = None
    image_count = None

    def check_url_format(self):
        # for ex: http://www.soap.com/p/nordic-naturals-complete-omega-3-6-9-1-000-mg-softgels-lemon-64714
        m = re.match(r"^http://www\.soap\.com/p/(.*)", self.product_page_url)
        return not not m

    def not_a_product(self):
        '''Overwrites parent class method that determines if current page
        is not a product page.
        Currently for Amazon it detects captcha validation forms,
        and returns True if current page is one.
        '''

        if len(self.tree_html.xpath("//div[@class='productDetailPic']//a//img")) < 1:
            if len(self.tree_html.xpath("//div[@class='productDetailPic']//div[@id='pdpTop']")) < 1:
                return True
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _url(self):
        return self.product_page_url

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@id='productIDTextBox']/@value")[0].strip()
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self.tree_html.xpath("//div[@class='productTitle']//h1//text()")[0].strip()

    def _product_title(self):
        return self.tree_html.xpath("//div[@class='productTitle']//h1//text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()
    
    def _model(self):
        return None

    def _upc(self):
        return None

    def _features(self):
        if self.feature_count is not None:
            return self.features
        self.feature_count = 0
        rows = self.tree_html.xpath("//dl[@class='descriptTabContent']//dd[@id='Tab1DetailInfo']//div[@class='pIdDesContent']//text()")
        rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
        line_txts = []
        if "Features:" in rows:
            lis = self.tree_html.xpath("//dl[@class='descriptTabContent']//dd[@id='Tab1DetailInfo']//div[@class='pIdDesContent']//ul//li")
            for li in lis:
                txt = "".join(li.xpath(".//text()")).strip()
                if len(txt) > 0:
                    line_txts.append(txt)
        if len(line_txts) < 1:
            return None
        self.feature_count = len(line_txts)
        self.features = line_txts
        return line_txts

    def _feature_count(self):
        if self.feature_count is None:
            self._features()
        return self.feature_count

    def _model_meta(self):
        return None

    def _description(self):
        description = self._description_helper()
        if description is None or len(description) < 1:
            return self._long_description_helper()
        return description

    def _description_helper(self):
        # trs = self.tree_html.xpath("//table[contains(@class,'gridItemList')]//tr[contains(@class,'diaperItemTR')]")
        # item_sku = None
        # for tr in trs:
        #     desc = tr.xpath(".//td[@class='itemDescription']//text()")[0].strip()
        #     try:
        #         sku = tr.xpath(".//td[@class='itemQty']/@sku")[0].strip()
        #         if desc == self._product_name():
        #             item_sku = re.findall(r'\d+$', sku)[0]
        #             break
        #     except IndexError:
        #         pass

        divs = self.tree_html.xpath("//div[@class='naturalBadgeContent']")
        description = ""
        rows = []
        flag = False
        for div in divs:
            # try:
            #     div_id = div.xpath("./@id")[0]
            # except IndexError:
            #     div_id = None
            # if item_sku is not None and div_id is not None:
            #     if item_sku in div_id:
            #         rows = div.xpath(".//text()")
            #         rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
            #         description += "\n".join(rows)
            #         # flag = True
            #         break
            rows = div.xpath(".//text()")
            rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
            description += "\n".join(rows)
            # flag = True
            break

        try:
            product_ids = self.tree_html.xpath("//table[contains(@class,'gridItemList')]//input[@class='skuHidden']/@productid")
        except:
            product_ids = []
        if self._product_id() in product_ids or len(product_ids) < 1:
            product_id = self._product_id()
        else:
            product_id = product_ids[0]
        try:
            tabid = self.tree_html.xpath("//li[@productid='%s']//a/@id" % product_id)[0].strip()
        except IndexError:
            tabid = None

        # if len(rows) < 1 and not flag:
        if not flag:
            try:
                idx = re.findall(r"\d+", tabid)[0]
            except IndexError:
                idx = "1"
            except:
                idx = None
            if idx is not None:
                rows = self.tree_html.xpath("//dl[@class='descriptTabContent']//dd[@id='Tab%sDetailInfo']//text()" % idx)
                rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
                if len(rows) > 0:
                    description += "\n" + "\n".join(rows)
                description = description.replace("\n.", ".")


        # rows = self.tree_html.xpath("//dl[@class='descriptTabContent']//dd[@id='Tab1DetailInfo']//div[contains(@class,'descriptContentBox')]//div[contains(@class,'pIdDesContent')]//p")
        # if not flag:
        #     str_cmp1 = " ".join(self.tree_html.xpath("//dl[@class='descriptTabContent']//dd[@id='Tab1DetailInfo']//div[contains(@class,'descriptContentBox')]//div[contains(@class,'pIdDesContent')]//p//text()"))
        #     str_cmp2 = " ".join(self.tree_html.xpath("//dl[@class='descriptTabContent']//dd[@id='Tab1DetailInfo']//div[contains(@class,'descriptContentBox')]//div[contains(@class,'pIdDesContent')]//p/text()"))
        #     if str_cmp1 == str_cmp2:
        #         flag = False
        #     else:
        #         flag = True
        # if len(rows) == 1 and not flag:
        #     try:
        #         rows = self.tree_html.xpath("//dl[@class='descriptTabContent']//dd[@id='Tab2DetailInfo']//text()")
        #         rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
        #         if len(rows) > 0:
        #             description = "\n" + "\n".join(rows)
        #         description = description.replace("\n.", ".")
        #     except IndexError:
        #         pass

        if len(description) < 1:
            return None
        return description

    def _long_description(self):
        description = self._description_helper()
        if description is None or len(description) < 1:
            return None
        long_desc = self._long_description_helper()
        if description == long_desc:
            return None
        return long_desc

    def _long_description_helper(self):
        tab_headers = self.tree_html.xpath("//ul[contains(@class,'descriptTab')]//li")
        description = ""
        for tab_header in tab_headers:
            txt = "".join(tab_header.xpath(".//text()")).strip()
            if txt == "Description":
                continue
            try:
                productid = tab_header.xpath("./@productid")[0].strip()
                if productid == self._product_id():
                    id = tab_header.xpath(".//a/@id")[0].strip()
                    id = re.findall(r"\d+", id)[0]
                    id = "Tab%sDetailInfo" % id
                    rows = self.tree_html.xpath("//dl[@class='descriptTabContent']//dd[@id='%s']//text()" % id)
                    rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
                    if len(rows) > 0:
                        description += "\n" + "\n".join(rows)
                    description = description.replace("\n.", ".")
            except:
                pass

        if len(description) < 1:
            return None
        return description

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    #returns 1 if the mobile version is the same, 0 otherwise
    def _mobile_image_same(self):
        return None

    def _image_urls(self):
        if self.image_count is not None:
            return self.image_urls
        self.image_count = 0
        image_url = self.tree_html.xpath("//div[contains(@class,'magicThumbBox')]/a/@href")
        image_url_tmp = ["http:%s" % self._clean_text(r) for r in image_url if len(self._clean_text(r)) > 0]
        image_url = []
        for item in image_url_tmp:
            try:
                if self._no_image(item):
                    pass
                else:
                    image_url.append(item)
            except Exception, e:
                image_url.append(item)

        if len(image_url) < 1:
            skuhdn = self.tree_html.xpath("//input[@id='clothSkuHidden']/@value")[0].strip()
            skuhdn = skuhdn.lower()
            skuhdn_prefix = skuhdn.split("-")[0]
            idx = 1
            while True:
                # http://c3.q-assets.com/images/products/p/uxk/uxk-500_1t.jpg
                url = "http://c3.q-assets.com/images/products/p/%s/%s_%st.jpg" % (skuhdn_prefix, skuhdn, idx)
                try:
                    contents = urllib.urlopen(url).read()
                    if "404 - File or directory not found" in contents:
                        break
                    else:
                        image_url.append(url)
                except:
                    break
                idx += 1
            if len(image_url) < 1:
                return None
        self.image_count = len(image_url)
        self.image_urls = image_url
        return image_url

    def _image_count(self):
        if self.image_count is None:
            self._image_urls()
        return self.image_count

    def _video_urls(self):
        if self.video_count is not None:
            return self.video_urls
        self.video_count = 0
        # http://www.soap.com/Product/ProductDetail!GetProductVideo.qs?groupId=98715&videoType=Consumer
        # url = "http://www.soap.com/Product/ProductDetail!GetProductVideo.qs?groupId=%s&videoType=Consumer" % self._product_id()
        product_ids = self.tree_html.xpath("//input[@class='skuHidden']/@productid")
        m = re.findall(r'showVideos\((.*?)\)', "\n".join(self.tree_html.xpath("//script//text()")), re.DOTALL)
        product_ids += m
        product_ids = list(set(product_ids))
        video_urls = []
        for product_id in product_ids:
            url = "http://www.soap.com/Product/ProductDetail!GetProductVideo.qs?groupId=%s" % product_id
            req = urllib2.Request(url, headers={'User-Agent' : "Magic Browser"})
            redirect_contents = urllib2.urlopen(req).read()
            redirect_tree = html.fromstring(redirect_contents)

            rows = redirect_tree.xpath("//div[contains(@class,'productVideoList')]//div[@class='videoImage']//a/@onclick")
            for row in rows:
                m = re.findall(r"playProductVideo\('(.*?)'", row.strip())
                if len(m) > 0:
                    video_urls.append(m[0])
            if len(rows) < 1:
                try:
                    now_playing = redirect_tree.xpath("//div[contains(@class,'productVideoPlayer')]//iframe/@src")[0].strip()
                    video_urls.append(now_playing)
                except IndexError:
                    pass
        if len(video_urls) < 1:
            return None
        self.video_count = len(video_urls)
        self.video_urls = video_urls
        return video_urls

    def _video_count(self):
        if self.video_count is None:
            self._video_urls()
        return self.video_count

    def _pdf_urls(self):
        pdfs = self.tree_html.xpath("//a[contains(@href,'.pdf')]")
        pdf_hrefs = []
        for pdf in pdfs:
            pdf_hrefs.append(pdf.attrib['href'])
        pdf_hrefs = list(set(pdf_hrefs))
        pdf_hrefs = [r for r in pdf_hrefs if "http://http://" not in r]
        return pdf_hrefs

    def _pdf_count(self):
        urls = self._pdf_urls()
        if urls is not None:
            return len(urls)
        return 0

    def _webcollage(self):
        atags = self.tree_html.xpath("//a[contains(@href, 'webcollage.net/')]")
        if len(atags) > 0:
            return 1
        return 0

    # extract htags (h1, h2) from its product product page tree
    def _htags(self):
        htags_dict = {}
        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
        return htags_dict

    def _keywords(self):
        return self.tree_html.xpath("//meta[@name='keywords']/@content")[0]

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    #populate the reviews_tree variable for use by other functions
    def _load_reviews(self):
        # if not self.max_score or not self.min_score:
        if self.review_count is None:
            # SOAP.COM REVIEWS
            try:
                soap_average_review = float(self.tree_html.xpath("//span[contains(@class,'pr-rating pr-rounded average')]//text()")[0].strip())
            except:
                soap_average_review = 0
            try:
                soap_review_count = int(self.tree_html.xpath("//p[contains(@class,'pr-snapshot-average-based-on-text')]//span[@class='count']//text()")[0].strip())
            except:
                soap_review_count = 0

            # AMAZON.COM REVIEWS
            # http://www.soap.com/amazon_reviews/06/47/14/mosthelpful_Default.html
            # product_ids = list(set(self.tree_html.xpath("//input[@class='skuHidden']/@productid")))
            # var pr_page_id = '43977';
            m = re.findall(r"var pr_page_id = '(.*?)'", "\n".join(self.tree_html.xpath("//script//text()")), re.DOTALL)
            product_ids = m
            product_ids = list(set(product_ids))
            redirect_tree = None
            for product_id in product_ids:
                if len(product_id) == 4:
                    product_id = "00%s" % product_id
                if len(product_id) == 5:
                    product_id = "0%s" % product_id
                product_id = [product_id[i:i+2] for i in range(0, len(product_id), 2)]
                if len(product_id) == 4:
                    product_id[2] = product_id[2] + product_id[3]
                    product_id.pop()
                product_id = "/".join(product_id)
                url = "http://www.soap.com/amazon_reviews/%s/mosthelpful_Default.html" % product_id
                req = urllib2.Request(url, headers={'User-Agent' : "Magic Browser"})
                try:
                    redirect_contents = urllib2.urlopen(req).read()
                    redirect_tree = html.fromstring(redirect_contents)
                    break
                except:
                    continue
            if redirect_tree is None:
                self.review_count = soap_review_count
                self.average_review = soap_average_review
                return
            review_count = redirect_tree.xpath("//span[@class='pr-review-num']//text()")[0].strip()
            m = re.findall(r"\d+", review_count)
            if len(m) > 0:
                self.review_count = int(m[0])
            else:
                self.review_count = 0
            average_review = redirect_tree.xpath("//span[contains(@class, 'pr-rating pr-rounded average')]//text()")[0].strip()
            m = re.findall(r"[\d\.]+", average_review)
            if len(m) > 0:
                self.average_review = float(m[0])
            else:
                self.average_review = 0
            self.average_review = round(((soap_review_count*soap_average_review) + (self.review_count*self.average_review)) / (soap_review_count + self.review_count), 2)
            self.review_count += soap_review_count
            rows = redirect_tree.xpath("//div[contains(@class,'pr-info-graphic-amazon')]//dl//dd[3]//text()")
            self.reviews = []
            idx = 5
            rv_scores = []
            for row in rows:
                cnt = int(re.findall(r"\d+", row)[0])
                if cnt > 0:
                    self.reviews.append([idx, cnt])
                    rv_scores.append(idx)
                idx -= 1
                if idx < 1:
                    break
            self.max_score = max(rv_scores)
            self.min_score = min(rv_scores)
        return

    def _average_review(self):
        self._load_reviews()
        return self.average_review

    def _review_count(self):
        self._load_reviews()
        return self.review_count

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
        price = self.tree_html.xpath("//span[@class='singlePrice']//text()")[0].strip()
        return price

    def _price_amount(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        return float(price_amount)

    def _price_currency(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        price_currency = price.replace(price_amount, "")
        if price_currency == "$":
            return "USD"
        return price_currency

    def _in_stores(self):
        return 0

    def _marketplace(self):
        '''marketplace: the product is sold by a third party and the site is just establishing the connection
        between buyer and seller. E.g., "Sold by X and fulfilled by Amazon" is also a marketplace item,
        since Amazon is not the seller.
        '''
        return 0

    def _marketplace_sellers(self):
        '''marketplace_sellers - the list of marketplace sellers - list of strings (["seller1", "seller2"])
        '''
        return None

    def _marketplace_lowest_price(self):
        # marketplace_lowest_price - the lowest of marketplace prices - floating-point number
        return None

    def _marketplace_out_of_stock(self):
        """Extracts info on whether currently unavailable from any marketplace seller - binary
        Uses functions that work on both old page design and new design.
        Will choose whichever gives results.
        Returns:
            1/0
        """
        return None

    def _site_online(self):
        # site_online: the item is sold by the site (e.g. "sold by Amazon") and delivered directly, without a physical store.
        return 1

    def _site_online_out_of_stock(self):
        #  site_online_out_of_stock - currently unavailable from the site - binary
        if self._site_online() == 0:
            return None
        try:
            btn_cls = self.tree_html.xpath("//input[@id='AddCartButton']/@class")[0].strip()
            if "proaddDisableBtn" in btn_cls:
                return 1
            if "proaddBtn" in btn_cls:
                rows = self.tree_html.xpath("//input[@class='skuHidden']/@isoutofstock")
                if len(rows) == 1 and 'Y' in rows:
                    return 1
                if len(rows) > 0 and 'N' not in rows:
                    return 1
                # if len(rows) == 1 and 'N' in rows:
                #     return 1
                if len(self.tree_html.xpath("//div[contains(@class,'productInfoRight')]//td[@class='outOfStockQty']//span[@class='outOfStock']")) < 1:
                    return 0
                # rows = self.tree_html.xpath("//input[contains(@class,'addToCartButtonBox')]")
                # if len(rows) > 0:
                #     return 0
                return 0
        except IndexError:
            pass
        return 0

    def _in_stores_out_of_stock(self):
        '''in_stores_out_of_stock - currently unavailable for pickup from a physical store - binary
        (null should be used for items that can not be ordered online and the availability may depend on location of the store)
        '''
        return None

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        all = self.tree_html.xpath("//div[contains(@class,'positionNav')]//a//text()")
        out = [self._clean_text(r) for r in all]
        if out[0].lower() == "home":
            out = out[1:]
        if len(out) < 1:
            return None
        return out

    def _category_name(self):
        return self._categories()[-1]

    def _brand(self):
        return self.tree_html.xpath("//div[@class='viewBox']//strong[1]//text()")[1].strip()

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
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "features" : _features, \
        "feature_count" : _feature_count, \
        "description" : _description, \
        "model" : _model, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "pdf_urls" : _pdf_urls, \
        "pdf_count" : _pdf_count, \
        "image_urls" : _image_urls, \
        "image_count" : _image_count, \
        "webcollage" : _webcollage, \
        "htags" : _htags, \
        "keywords" : _keywords, \
        "mobile_image_same" : _mobile_image_same, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "in_stores" : _in_stores, \
        "marketplace": _marketplace, \
        "marketplace_sellers" : _marketplace_sellers, \
        "marketplace_lowest_price" : _marketplace_lowest_price, \
        "site_online" : _site_online, \
        "site_online_out_of_stock" : _site_online_out_of_stock, \
        "in_stores_out_of_stock" : _in_stores_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "category_name" : _category_name, \
        "brand" : _brand, \

        "loaded_in_seconds": None \
        }


    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    DATA_TYPES_SPECIAL = { \
        # CONTAINER : CLASSIFICATION
         # CONTAINER : REVIEWS
        "review_count" : _review_count, \
        "average_review" : _average_review, \
        "max_review" : _max_review, \
        "min_review" : _min_review, \
        "reviews" : _reviews, \

        # CONTAINER : PAGE_ATTRIBUTES
        "video_urls" : _video_urls, \
        "video_count" : _video_count, \
    }

