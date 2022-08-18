#!/usr/bin/python

import re
import requests
from extract_data import Scraper
from spiders_shared_code.bhphotovideo_variants import BhphotovideoVariants


class BhphotovideoScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.bhphotovideo.com/.*"

    REVIEW_URL = "https://www.bhphotovideo.com/bnh/controller/home?A=GetReviews&Q=json&O=&" \
                 "sku={sku}&" \
                 "pageSize=100&" \
                 "pageNum=0&" \
                 "currReviews={review_num}"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.hv = BhphotovideoVariants()

    def check_url_format(self):
        m = re.match(r"^http(s)://www.bhphotovideo.com/.*?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[@data-selenium="tContent"]')) < 1:
            return True

        self.hv.setupCH(self.tree_html)

        return False

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_id(self):
        product_id = self.tree_html.xpath('//*[@itemprop="productID"]/@content')
        return product_id[-1].split(':')[1] if product_id else None

    def _brand(self):
        brand = self.tree_html.xpath('//span[@itemprop="brand"]/text()')
        return brand[0] if brand else None

    def _product_name(self):
        product_name = self.tree_html.xpath('//span[@itemprop="name"]/text()')
        return product_name[0].strip()

    def _description(self):
        description = self.tree_html.xpath('//div[@class="ov-desc"]//p/text()')
        if description:
            return "".join(description)

    def _bullets(self):
        bullets = self.tree_html.xpath('//ul[@class="top-section-list"]')
        if bullets:
            return '\n'.join([x.strip() for x in bullets[0].xpath('./li/text()')])

    def _sku(self):
        sku = self.tree_html.xpath('//input[@name="sku"]/@value')
        return sku[0]

    def _upc(self):
        upc = self.tree_html.xpath("//span[@class='upcNum']/text()")

        return upc[0].split(':')[1].strip() if upc else None

    def _variants(self):
        return self.hv._variants()

    def _specs(self):
        specs = {}
        specs_list = self.tree_html.xpath("//table[@class='specTable'][1]//tr")
        for spec in specs_list:
            specs_key = spec.xpath('./td[contains(@class, "specTopic")]/text()')[0].strip()
            specs_value = spec.xpath('./td[contains(@class, "specDetail")]/text()')[0].strip()
            specs[specs_key] = specs_value
        return specs

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath('//div[@data-selenium="productThumbnail"]//img/@data-src')
        if not image_urls:
            image_urls = self.tree_html.xpath('//div[@data-selenium="productThumbnail"]//img/@src')
        return [re.sub(r'smallimages|thumbnails', 'images500x500', x) for x in image_urls] if image_urls else None

    def _video_urls(self):
        video_urls = self.tree_html.xpath('//span[@class="videos-container"]//iframe/@src')
        return video_urls if video_urls else None

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        self.reviews_checked = True

        review_num = self.tree_html.xpath('//span[@itemprop="reviewCount"]/text()')
        url = self.REVIEW_URL.format(sku=self._sku(), review_num=review_num[0])
        data = requests.get(url=url, timeout=10).json()

        results = data["snapshot"]

        self.review_count = results["num_reviews"]
        self.average_review = round(float(results["average_rating"]), 1)

        rating_mark_list = []
        for key, value in results["rating_histogram"].iteritems():
            temp = [key, value]
            rating_mark_list.append(temp)

        self.reviews = rating_mark_list

        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = re.search(r'mainPrice\ =\ \"(.*?)\"', self.page_raw_text)
        return '$' + price.group(1) if price else None

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_status = self.tree_html.xpath('//*[@itemprop="availability"]/@content')
        if stock_status and stock_status[0].lower() == 'instock':
            return 0
        return 1

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//ul[@id="breadcrumbs"]'
                                          '/li/a/text()')
        return [self._clean_text(category) for category in categories[1:]]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {

        # CONTAINER : PRODUCT_INFO
        "brand": _brand,
        "product_id": _product_id,
        "product_name": _product_name,
        "description": _description,
        "bullets": _bullets,
        "sku": _sku,
        "variants": _variants,
        "upc": _upc,
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
