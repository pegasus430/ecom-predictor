#!/usr/bin/python

import re
import json
import requests

from lxml import html, etree
from functools import partial
from extract_data import Scraper
from spiders_shared_code.shoebuy_variants import ShoebuyVariants


class ShoeBuyScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.shoes.com/.*$ or http://www.shoebuy.com/.*$"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=lgzh8hhvewlnvqczzsaof7uno" \
            "&apiversion=5.5" \
            "&displaycode=11477-en_us" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.product_json = None
        self.sv = ShoebuyVariants()

    def check_url_format(self):
        m = re.match(r"^https://www.shoes.com/.*$", self.product_page_url)
        n = re.match(r"^http://www.shoebuy.com/.*$", self.product_page_url)
        return bool(m or n)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

        if itemtype != "product":
            return True

        self._extract_product_json()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _extract_product_json(self):
        try:
            product_json_text = re.search('({"sizes":.*?})\)', html.tostring(self.tree_html), re.DOTALL).group(1)
            self.product_json = json.loads(product_json_text)
            self.sv.setupCH(self.tree_html, self.product_json)
        except:
            self.product_json = None

    def _product_id(self):
        product_id = self.tree_html.xpath('//h2[@class="product_details"]//span[@itemprop="productID"]/text()')

        if product_id:
            return product_id[0]
        return re.findall(r'\d+$', self.product_page_url)[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//div[@class="category_title"]//h1/descendant::text()')
        if product_name:
            return self._clean_text(''.join(product_name))

        product_name = self.tree_html.xpath('//div[contains(@class, "product_information")]/h2//text()')
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _model(self):
        if self.product_json.get("info"):
            return self.product_json["info"]["modelNumber"]
        return None

    def _upc(self):
        scripts = self.tree_html.xpath('//script//text()')
        for script in scripts:
            var = re.findall(r'CI_ItemUPC=(.*?);', script)
            if len(var) > 0:
                var = var[0]
                break
        var = re.findall(r'[0-9]+', str(var))
        return var[0] if var else None

    def _features(self):
        features_td_list = self.tree_html.xpath('//table[contains(@class, "tablePod tableSplit")]//td')
        features_list = []

        for index, val in enumerate(features_td_list):
            if (index + 1) % 2 == 0 and features_td_list[index - 1].xpath(".//text()")[0].strip():
                features_list.append(features_td_list[index - 1].xpath(".//text()")[0].strip() + " " + features_td_list[index].xpath(".//text()")[0].strip())

        return features_list

    def _description(self):
        short_description = self.tree_html.xpath('//div[contains(@class, "product_description")]/span[@itemprop="description"]//text()')
        return self._clean_text(short_description[0]) if short_description else None

    def clean_bullet_html(self, el):
        l = el.xpath(".//text()")
        l = " ".join(l)
        l = " ".join(l.split())
        return l

    def _bullet_feature_X(i, self):
        bullets = self.tree_html.xpath('//ul[contains(@class, "detail_comp")]/li')
        if len(bullets) > i - 1:
            b = bullets[i - 1]
            return self.clean_bullet_html(b)
        return None

    def _bullets(self):
        bullets = self.tree_html.xpath('//ul[contains(@class, "detail_comp")]/li/text()')
        bullets = [self._clean_text(r) for r in bullets if len(self._clean_text(r))>0]
        if len(bullets) > 0:
            return "\n".join(bullets)
        return None

    def _swatches(self):
        return self.sv.swatches()

    def _variants(self):
        return self.sv._variants()

    def _no_longer_available(self):
        arr = self.tree_html.xpath('//div[@id="productinfo_ctn"]//div[contains(@class,"error")]//text()')
        if "to view is not currently available." in " ".join(arr).lower():
            return 1
        return 0

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []

        selected_image = self.tree_html.xpath('//select[@name="quick_view_colors"]//option[@selected="selected"]/@data-image')
        if selected_image:
            selected_image = 'https://www.shoes.com' + selected_image[0]
            for i in range(1, 20):
                image_url = selected_image.replace('/pi', '/pm').replace('/xs', '').replace('_xs', '_jb' + str(i))
                response = requests.head(image_url)
                if response.status_code == 200:
                    image_list.append(image_url)

        if not image_list and selected_image:
            selected_image = selected_image.replace('/xs', '/jb').replace('_xs', '_jb')
            image_list.append(selected_image)

        if not selected_image:
            images = self.tree_html.xpath("//div[@class='large_thumb has_thumbs']//img/@src")
            if images:
                for image in images:
                    image_list.append('https:' + image)

        return image_list

    def _video_urls(self):
        media_list = []
        video_list = []

        if self.product_json.get('media'):
            media_list = self.product_json["media"]["mediaList"]

        for media_item in media_list:
            if "video" in media_item:
                video_list.append(media_item["video"])

        return video_list

    def _video_count(self):
        video_count = 0

        videos = self._video_urls()

        if self.product_json.get("media"):
            media_list = self.product_json["media"]["mediaList"]
            video_count = len( filter(lambda m: 'videoId' in m, media_list))

        if videos:
            return len(videos)

        return video_count

    def _pdf_urls(self):
        pdf_url_list = None
        moreinfo = self.tree_html.xpath('//div[@id="moreinfo_wrapper"]')

        if moreinfo:
            html = etree.tostring(moreinfo[0])
            pdf_url_list = re.findall(r'(http://.*?\.pdf)', html)

        return pdf_url_list

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        stylecode = self.tree_html.xpath('//input[@id="stylecode"]/@value')

        if stylecode:
            review_url = self.REVIEW_URL.format(stylecode[0])
            return super(ShoeBuyScraper, self)._reviews(review_url = review_url)

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//span[@itemprop='price']/text()")
        low_price = self.tree_html.xpath("//span[@itemprop='lowPrice']/text()")
        high_price = self.tree_html.xpath("//span[@itemprop='highPrice']/text()")
        if price:
            price = price[0]
        if low_price and high_price:
            price = '$' + low_price[0] + '-' + '$' + high_price[0]

        return price

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 1

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        all = []
        scripts = self.tree_html.xpath('//script//text()')
        for script in scripts:
            jsonvar = re.findall(r'BREADCRUMB_JSON = (.*?});', script)
            if len(jsonvar) > 0:
                jsonvar = json.loads(jsonvar[0])
                break

        if jsonvar:
            if jsonvar.get('bcEnsightenData', {}).get('contentSubCategory', {}):
                all = jsonvar['bcEnsightenData']['contentSubCategory'].split(u'\u003e')
        return all

    def _brand(self):
        brand = self.tree_html.xpath('//meta[@property="og:brand"]/@content')
        return brand[0] if brand else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "model" : _model, \
        "upc" : _upc,\
        "features" : _features, \
        "description" : _description, \
        "bullet_feature_1": partial(_bullet_feature_X, 1), \
        "bullet_feature_2": partial(_bullet_feature_X, 2), \
        "bullet_feature_3": partial(_bullet_feature_X, 3), \
        "bullet_feature_4": partial(_bullet_feature_X, 4), \
        "bullet_feature_5": partial(_bullet_feature_X, 5), \
        "bullet_feature_6": partial(_bullet_feature_X, 6), \
        "bullet_feature_7": partial(_bullet_feature_X, 7), \
        "bullet_feature_8": partial(_bullet_feature_X, 8), \
        "bullet_feature_9": partial(_bullet_feature_X, 9), \
        "bullet_feature_10": partial(_bullet_feature_X, 10), \
        "bullet_feature_11": partial(_bullet_feature_X, 11), \
        "bullet_feature_12": partial(_bullet_feature_X, 12), \
        "bullet_feature_13": partial(_bullet_feature_X, 13), \
        "bullet_feature_14": partial(_bullet_feature_X, 14), \
        "bullet_feature_15": partial(_bullet_feature_X, 15), \
        "bullet_feature_16": partial(_bullet_feature_X, 16), \
        "bullet_feature_17": partial(_bullet_feature_X, 17), \
        "bullet_feature_18": partial(_bullet_feature_X, 18), \
        "bullet_feature_19": partial(_bullet_feature_X, 19), \
        "bullet_feature_20": partial(_bullet_feature_X, 20), \
        "bullets": _bullets, \
        "swatches" : _swatches, \
        "variants" : _variants, \
        "no_longer_available" : _no_longer_available, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "video_count" : _video_count, \
        "video_urls" : _video_urls, \
        "pdf_urls" : _pdf_urls, \

        # CONTAINER : REVIEWS
        "reviews" : _reviews, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "in_stores" : _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
        "marketplace" : _marketplace, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "brand" : _brand
        }
