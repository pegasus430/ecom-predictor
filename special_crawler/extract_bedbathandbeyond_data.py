#!/usr/bin/python

import re

from lxml import html, etree
import requests
from extract_data import Scraper
from spiders_shared_code.bedbathandbeyond_variants import BedBathAndBeyondVariants


class BedBathAndBeyondScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.bedbathandbeyond.(com|ca)/store" \
                          "/product/<product-name>/<product-id>"

    REVIEW_URL = "https://bedbathandbeyond.ugc.bazaarvoice.com/2009-en_us/{0}/reviews.djs?format=embeddedhtml"

    QUESTIONS_URL = "https://bedbathandbeyond.ugc.bazaarvoice.com/answers/2009-en_us/product/{product_id}/" \
                    "questions.djs?format=embeddedhtml&page={page}"

    VIDEO_URL = "https://video.bedbathandbeyond.com/tvpembed/{}"

    def __init__(self, **kwargs):# **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        # whether product has any webcollage media

        self.image_dimensions = None
        self.zoom_image_dimensions = None
        self.got_image_dimensions = False

        self.bbVnt = BedBathAndBeyondVariants()

    def check_url_format(self):
        """Checks product URL format for this scraper instance is valid.
        Returns:
            True if valid, False otherwise
        """
        m = re.match(r"^https?://www.bedbathandbeyond.(com|ca)/store/product/.*?$", self.product_page_url)
        if 'bedbathandbeyond.ca' in self.product_page_url:
            self.REVIEW_URL = "https://bedbathandbeyond.ugc.bazaarvoice.com/0851-en_ca/{0}/reviews.djs?format=embeddedhtml"
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
            self.bbVnt.setupCH(self.tree_html)
        except:
            pass

        return False

    def _pre_scrape(self):
        self._extract_questions_content()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.tree_html.xpath("//input[contains(@name, 'productId')]/@value")[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        product_name = self.tree_html.xpath("//h1[@id='productTitle']/text()")

        return product_name[0].strip() if product_name else None

    def _product_title(self):
        product_title = self.tree_html.xpath("//title/text()")

        return product_title[0].strip() if product_title else None

    def _sku(self):
        sku = self.tree_html.xpath('//p[contains(@class, "prodSKU")]/text()')
        if sku:
            sku = re.search('\d+', sku[0])
            return sku.group(0) if sku else None

    def _title_seo(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _description(self):
        short_description = self.tree_html.xpath("//div[@itemprop='description']/text()")
        if short_description:
            short_description = ''.join(short_description).replace('\r', '').replace('\n', '').strip()

        return short_description if short_description else None

    def _long_description(self):
        long_description = self.tree_html.xpath(
            "//div[contains(@class, 'bulletsReset grid_6 alpha appendSKUInfo')]//ul"
        )
        if long_description:
            long_description = self._clean_text(html.tostring(long_description[0]))

        return long_description if long_description else None

    def _model(self):
        model_data = self.tree_html.xpath(
            "//div[contains(@class, 'bulletsReset grid_6 alpha appendSKUInfo')]"
            "//ul//li[contains(text(), 'Model')]/text()"
        )
        if model_data:
            return model_data[0].replace('Model', '').strip()

    def _variants(self):
        if not self.bbVnt._get_colors() and not self.bbVnt._get_sizes():
            return None

        return self.bbVnt._variants()

    def _swatches(self):
        if not self.bbVnt._get_colors() and not self.bbVnt._get_images():
            return None

        return self.bbVnt._swatches()

    def _no_longer_available(self):
        return 0

    def _specs(self):
        specs = {}
        specs_elements = self.tree_html.xpath(
            '//div[@id="productSpecTablesContainer"]//table[preceding-sibling::h3[contains(text(), "Specifications")]'
            ' and not(preceding-sibling::h3[1][not(contains(text(), "Specifications"))])]//tr'
        )
        for spec_element in specs_elements:
            data = spec_element.xpath('./td/text()')
            if len(data) == 2:
                specs[data[0]] = data[1]
        return specs if specs else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
    def _image_urls(self):
        main_image = self.tree_html.xpath("//div[@id='s7ProductImageWrapper']//img/@src")[0]
        s7_root = main_image.split('?')[0]
        s7_endpoint = 'https:{root}__{image_num}?478$'

        image_urls = []
        image_urls.append('https:' + str(main_image))

        for index in range(1, 20):
            image_url = s7_endpoint.format(root=s7_root, image_num=index)
            s7_status_code = requests.head(image_url).status_code

            if s7_status_code == 200:
                image_urls.append(image_url)
            else:
                break

        self.images_group = image_urls

        return image_urls

    def _video_urls(self):
        videos = self.tree_html.xpath('//a[contains(@class,"tvpAltVideo")]/@data-videoid')
        if videos:
            return [self.VIDEO_URL.format(video) for video in videos]

    def _get_image_dimensions(self):
        if self.got_image_dimensions:
            return

        self.got_image_dimensions = True

        if not self.images_group:
            self._image_urls()

        image_dims = []
        zoom_image_dims = []
        image_url = "{root}?hei={height}&wid={width}"

        for image in self.images_group:
            image_root = image.split('?')[0]
            image_show = image_url.format(
                root=image_root,
                height=395,
                width=395
            )
            image_zoom = image_url.format(
                root=image_root,
                height=2000,
                width=2000
            )
            show_status = requests.head(image_show).status_code
            zoom_status = requests.head(image_zoom).status_code

            if show_status == 200:
                image_dims.append(1)
            else:
                image_dims.append(0)

            if zoom_status == 200:
                zoom_image_dims.append(1)
            else:
                zoom_image_dims.append(0)

        self.image_dimensions = image_dims
        self.zoom_image_dimensions = zoom_image_dims

    def _image_dimensions(self):
        self._get_image_dimensions()
        return self.image_dimensions

    def _zoom_image_dimensions(self):
        self._get_image_dimensions()
        return self.zoom_image_dimensions

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        reg_price = self.tree_html.xpath("//span[@itemprop='price']/@content")
        low_price = self.tree_html.xpath("//span[@itemprop='lowPrice']/@content")

        price_info = reg_price or low_price

        if price_info:
            price = ''.join(price_info)
            if not '$' in price:
                price = '$' + price
            return price

        return None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath('//span[@itemprop="price"]/@content'):
            return int(bool(self.tree_html.xpath('//link[@itemprop="availability" and contains(@href, "OutOfStock")]')))
        return 1

    def _in_stores_out_of_stock(self):
        return int(not bool(self.tree_html.xpath('//span[@itemprop="price"]/@content')))

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        categories = self.tree_html.xpath(
            "//div[contains(@class, 'breadcrumbs')]"
            "//a[@itemprop='item']/@title"
        )
        categories = [self._clean_text(i) for i in categories]
        return categories

    def _brand(self):
        brand = self._find_between(html.tostring(self.tree_html), '_ga_refinedBrandName =', '.')
        if brand:
            brand = brand.replace('\'', '').strip()

        return brand if brand else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "long_description": _long_description,
        "variants": _variants,
        "swatches": _swatches,
        "no_longer_available": _no_longer_available,
        "sku": _sku,
        "model": _model,
        "specs": _specs,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,
        "image_dimensions": _image_dimensions,
        'zoom_image_dimensions': _zoom_image_dimensions,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        }
