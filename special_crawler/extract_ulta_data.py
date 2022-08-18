#!/usr/bin/python

import re
import json
import urlparse
import traceback

from lxml import html
from extract_data import Scraper


class UltaScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    REVIEW_URL = "http://www.ulta.com/reviewcenter/pwr/content/{code}/{product_id}-en_US-meta.js"

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0].strip() == 'product':
            return False

        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@id='pinProduct']/@value")[0].strip()

        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath('//input[@id="pinDisplay"]/@value')[0].strip()

    def _product_title(self):
        return self.tree_html.xpath('//title/text()')[0].strip()

    def _item_num(self):
        item = self.tree_html.xpath("//span[@id='itemNumber']/text()")
        if item:
            item = re.search('\d+', item[0])
        return item.group() if item else None

    def _description(self):

        description_elements = self.tree_html.xpath('//div[@id="product-first-catalog"]/div[contains(@class,"product-catalog-content")]')

        text_elements = self.tree_html.xpath('//div[@id="product-first-catalog"]/div[contains(@class,"product-catalog-content")]/text()')

        short_description = "" . join(text_elements)

        if description_elements:
            description_elements = description_elements[0]

            for description_element in description_elements:
                if "<iframe " in html.tostring(description_element):
                    continue

                short_description += html.tostring(description_element)

        short_description = short_description.strip()

        return short_description if short_description else None

    def _variants(self):
        current_sku = re.search("currentSkuId = '(\d+)'", html.tostring(self.tree_html)).group(1)

        variants = []

        variant_data = re.findall('productSkus\[\d+\] =\s+({[^}]+});', html.tostring(self.tree_html))

        for d in variant_data:
            variant_json = json.loads(d)

            if current_sku == variant_json['id']:
                continue

            price_html = html.fromstring( self.load_page_from_url_with_number_of_retries('http://www.ulta.com/common/inc/productDetail_price.jsp?skuId=%s&productId=%s&fromPDP=true' % (variant_json['id'], self._product_id())))

            variants.append( {
                'variant' : variant_json.get('displayName'),
                'item_no' : variant_json['id'],
                'price' : float( price_html.xpath('//p')[0].text[1:]), # remove leading $ and convert to float
                'image_url' : variant_json['imgUrl'].split('?')[0],
                'selected' : False,
            } )

        if variants:
            return variants

    '''
    def _swatches(self):
        swatches = []

        swatch_els = self.tree_html.xpath('//a[contains(@class,"product-swatch")]/img')

        for e in swatch_els:
            swatches.append( {
                'name' : e.get('alt'),
                'img' : e.get('data-blzsrc').split('?')[0],
            } )

        if swatches:
            return swatches
    '''

    def _no_longer_available(self):
        if re.search('Sorry, this product is no longer available.', self.page_raw_text):
            return 1
        return 0

    def _long_description(self):
        description_elements = self.tree_html.xpath('//div[contains(@class,"product-catalog")]')

        for description_element in description_elements:
            if description_element.xpath("div[contains(@class,'product-catalog-head')]") and \
                            "How to Use" in description_element.xpath("div[contains(@class,'product-catalog-head')]")[0].text_content():
                return re.sub('<div class="product-catalog-content.*>', '', \
                    html.tostring(description_element.xpath("div[contains(@class,'product-catalog-content')]")[0])).\
                    replace('</div>', '').strip()

    def _ingredients(self):
        product_catalog_list = self.tree_html.xpath('//div[contains(@class,"product-catalog")]')

        for product_catalog in product_catalog_list:
            pch = product_catalog.xpath("div[contains(@class,'product-catalog-head')]")

            if pch:
                head_text = pch[0].text_content()

                if "Ingredients" in head_text:
                    ingredients = product_catalog.xpath("div[contains(@class,'product-catalog-content')]")[0].text_content().strip()

                    return ingredients.split(', ')

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################
 
    def _image_urls(self):
        main_image_url = self.tree_html.xpath('//meta[@property="og:image"]/@content')
        main_images = [urlparse.urljoin(self.product_page_url, img) for img in main_image_url]

        thumb_image_urls = self.tree_html.xpath("//li[contains(@class, 'thumbnail-image-pdp')]//a//img/@src")
        thumb_images = [urlparse.urljoin(self.product_page_url, img) for img in thumb_image_urls]
        if not thumb_images and main_images:
            thumb_images = main_images
        return thumb_images

    def _video_urls(self):
        video_urls = []

        for url in self.tree_html.xpath('//iframe/@src'):
            if "www.youtube.com" in url and not url in video_urls:
                video_urls.append(url)

        for idx, item in enumerate(video_urls):
            if "http:" in item:
                video_urls[idx] = item.strip()
            else:
                video_urls[idx] = "http:" + item.strip()

        if video_urls:
            return video_urls

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        if not self.tree_html.xpath('//div[@id="product-review-container"]/a[@id="reviews"]'):
            return None

        return float(self.tree_html.xpath('//span[@class="pr-rating pr-rounded average"]/text()')[0])

    def _review_count(self):
        if not self.tree_html.xpath('//div[@id="product-review-container"]/a[@id="reviews"]'):
            return int(0)

        return int(self.tree_html.xpath('//p[@class="pr-snapshot-average-based-on-text"]/span[@class="count"]/text()')[0])

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True
        try:
            self.reviews = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
            product_id = self._product_id()
            code = self._get_product_code(product_id)
            review_url = self.REVIEW_URL.format(code=code, product_id=product_id)
            response = self._request(review_url)
            stars = re.findall('rating:(\d+)', response.text)
            if stars:
                for star in stars:
                    self.reviews[5 - int(star)][1] += 1
                return self.reviews
            else:
                self.reviews = None
            return self.reviews
        except:
            traceback.format_exc()

    def _get_product_code(self, product_id):
        # override js function
        cr = 0
        for i in range(0, len(product_id)):
            cp = ord(product_id[i])
            cp = cp * abs(255-cp)
            cr += cp
        cr %= 1023
        cr = str(cr)
        ct = 4
        for i in range(0, ct - len(cr)):
            cr = '0' + cr
        cr = cr[0:2] + "/" + cr[2:4]
        return cr

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price_amount = self.tree_html.xpath("//meta[@property='product:price:amount']/@content")
        return float(price_amount[0]) if price_amount else None

    def _site_online(self):
        return 1

    def _in_stores(self):
        for x in self.tree_html.xpath('//div[@id="productBadge"]/img/@src'):
            if 'http://images.ulta.com/is/image/Ulta/badge-online-only' in x:
                return 0
        return 1

    def _site_online_out_of_stock(self):
        oos = re.findall('"outOfStock":"(.*?)"', html.tostring(self.tree_html))
        if oos and oos[0] == 'true':
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################    

    def _categories(self):
        categories_text = self.tree_html.xpath('//div[@class="makeup-breadcrumb"]/ul/li/a/text()')

        return categories_text[1:]

    def _brand(self):
        return self.tree_html.xpath('//input[@id="pinBrand"]/@value')[0].strip()

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
        "item_num": _item_num,
        "description": _description,
        "long_description": _long_description,
        "ingredients": _ingredients,
        "variants": _variants,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : REVIEWS
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
    }
