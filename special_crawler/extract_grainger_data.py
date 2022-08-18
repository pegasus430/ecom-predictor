#!/usr/bin/python

import re
from extract_data import Scraper

class GraingerScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.grainger.com/.*"

    REVIEW_URL = "https://grainger.ugc.bazaarvoice.com/5049hbrs-en_us/{0}/reviews.djs?format=embeddedhtml"

    VIDEO_URL = "https://e.invodo.com/4.0/pl/{version}/{id_key}/{id}.js"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.video_urls = []
        self.video_checked = False

    def check_url_format(self):
        m = re.match(r"^(http|https)://www.grainger.com/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@id="productPage"]')) < 1:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//span[@itemprop="productID"]/text()')
        if product_id:
            return product_id[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _brand(self):
        brand = self.tree_html.xpath('//*[@itemprop="Brand"]/text()')
        if brand:
            return brand[0].strip()

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@class="productName"]/text()')
        if product_name:
            return re.sub("[\n\t]", "", product_name[0]).strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        model = self.tree_html.xpath('//span[@itemprop="model"]/text()')
        if model:
            return model[0]

    def _description(self):
        description_list = self.tree_html.xpath('//div[@id="copyTextSection"]/text()')
        description = ''
        for desc in description_list:
            description += desc
        return description

    def _item_num(self):
        return self._product_id()

    def _upc(self):
        upc = self.tree_html.xpath('//li[@id="unspsc"]/span/text()')
        if upc:
            return upc[0]

    def _features(self):
        features = self.tree_html.xpath(
            '//span[@class="specName" and contains(text(), "Features")]'
            '/following-sibling::span[@class="specValue"]/text()'
        )
        if features:
            return [x.strip() for x in features[0].split(',')]

    def _specs(self):
        spec_names = self.tree_html.xpath(
            '//span[@class="specName" and not(contains(text(), "Features"))]/text()'
        )
        spec_values = self.tree_html.xpath(
            '//span[@class="specName" and not(contains(text(), "Features"))]'
            '/following-sibling::span[@class="specValue"]/text()'
        )
        specs = dict(zip(spec_names, spec_values))

        return specs if specs else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        urls = self.tree_html.xpath('//li[@data-type="prodImage"]//img/@data-image')
        image_urls = []
        if urls:
            for url in urls:
                image_urls.append('https:' + url)
        else:
            image_url = self.tree_html.xpath('//div[@id="mainImage"]//img/@data-blzsrc')
            image_urls.append('https:' + image_url[0])
        return image_urls

    def _video_urls(self):
        if self.video_checked:
            return self.video_urls


        self.video_checked = True
        video_ids = self.tree_html.xpath('//li[@data-type="video"]/@data-code')
        for video_id in video_ids:
            for i in reversed(range(1, 7)):
                headers = {
                    'Referer': self.product_page_url
                }
                resp = self._request(self.VIDEO_URL.format(
                    version=i,
                    id_key=video_id[-1],
                    id=video_id
                ), headers=headers)
                if resp.status_code == 200:
                    video_url = re.search(r'\"http\":\"(.*?)\"', resp.text)
                    if video_url:
                        self.video_urls.append(video_url.group(1))
                    break
        return self.video_urls

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath('//span[@itemprop="price"]/text()')
        if price:
            return price[0]

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath('//ul[@class="nav"]/li/a/text()')
        return categories

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "brand": _brand,
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "description": _description,
        "item_num": _item_num,
        "upc": _upc,
        "features": _features,
        "specs": _specs,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        }
