#!/usr/bin/python

import re
from extract_data import Scraper
from spiders_shared_code.boxed_variants import BoxedVariants


class BoxedScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.boxed.com/product/*"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.bv = BoxedVariants()

    def check_url_format(self):
        m = re.match("https?://www.boxed.com/product/.*", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0].strip() == "og:product":
            self.bv.setupCH(self.tree_html)
            return False

        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_url = ''.join(self.tree_html.xpath("//meta[@property='og:url']/@content"))
        if product_url:
            product_id = re.search("product/(.*?)/", product_url).group(1)
            return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        brand = self.tree_html.xpath('//section[@id="product-page"]//h1/text()')
        title = self.tree_html.xpath('//section[@id="product-page"]//h2/text()')
        if brand and title:
            return brand[0] + ' ' + title[0]
        elif title:
            return title[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _nutrition_facts(self):
        nutrition_names= []
        nutrition_values = []
        nutrition_facts = []

        nutrition_info = self.tree_html.xpath("//div[@class='_3TsvAHkMrkjwCrVXE23Mhq']//span")
        for i, data in enumerate(nutrition_info):
            if i % 2 == 0:
                nutrition_names.append(''.join(data.xpath("./text()")))
            else:
                nutrition_values.append(''.join(data.xpath("./text()")))
        other_nutrition_names = self.tree_html.xpath("//ul[@class='_3xG3lnUHF3D3wlU3shm87a']//div/text()")

        for dt in other_nutrition_names:
            nutrition_names.append(dt)
        diff = abs(len(nutrition_names) - len(nutrition_values))
        for index, dt in enumerate(nutrition_values):
            nutrition_facts.append(': '.join([nutrition_names[index], dt]))
        if nutrition_facts:
            if len(nutrition_names) > len(nutrition_facts):
                for i in range(-(diff), 0):
                    nutrition_facts.append(nutrition_names[i])

        return nutrition_facts

    def _description(self):
        description = self.tree_html.xpath('//meta[@property="og:description"]/@content')
        if len(description) > 1:
            description = ''.join(description[:1])
        else:
            description = ''.join(description)
        return description

    def _long_description(self):
        description = self.tree_html.xpath('//div[@class="_9d9OUcL5Ie9mbSW_4mLW4"]/p/text()')
        return description if description else None

    def _no_longer_available(self):
        arr = self.tree_html.xpath('//div[@id="productinfo_ctn"]//div[contains(@class,"error")]//text()')
        if "to view is not currently available." in " ".join(arr).lower():
            return 1
        return 0

    def _ingredients(self):
        ingredients = None
        title_list = self.tree_html.xpath('//div[@class="_28T3vl8DBWBC4pOal3tWcZ"]//h2/text()')
        for title in title_list:
            if 'ingredients' in title.lower():
                i = title_list.index(title)
                ingredients = self.tree_html.xpath('//div[@class="_28T3vl8DBWBC4pOal3tWcZ"]')[i]\
                    .xpath('.//div[@class="_9d9OUcL5Ie9mbSW_4mLW4"]//p/text()')
                break
        if ingredients:
            return [i.strip() for i in ingredients[0].split(',')]

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        media_list = self.tree_html.xpath('//div[contains(@class, "1nwCfhT1NoGhA4C-D1z6AY")]//img/@src')
        for image_url in media_list:
            image_urls.append(image_url.split('//')[1])
        return image_urls

    def _variants(self):
        return self.bv._variants()

    def _review_count(self):
        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//meta[@id='meta-og-price']/@content")
        if price:
            price = ''.join(price)
            return price

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        stock_status = self.tree_html.xpath("//span[@class='_2wgCi1WplMYN5xf-FTxJEI']/text()")
        if stock_status and stock_status[0] == 'In Stock':
            return 0
        return 1

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//div[@class='_2N7OY2Q-RMKLR0Y-Hnkco8']//a/text()")
        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath("//div[contains(@class, 'product-meta')]/h1/text()")
        if brand:
            brand = ''.join(brand)
            return brand
        brand = self.tree_html.xpath('//h1/text()')
        return brand[0] if brand else None

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "description" : _description,
        "long_description" : _long_description,
        "no_longer_available" : _no_longer_available,
        "ingredients" : _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "variants": _variants,

        # CONTAINER : REVIEWS
        "review_count" : _review_count,

        # CONTAINER : SELLERS
        "price" : _price,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
    }
