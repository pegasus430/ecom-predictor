#!/usr/bin/python

import re
import requests
from urlparse import urljoin
from extract_data import Scraper


class MorrisonsScraper(Scraper):
    INVALID_URL_MESSAGE = "Expected URL format is http(s)://groceries.morrisons.com/webshop/product/<product-name>/<product-id>"

    def check_url_format(self):
        m = re.match(r"^https?://groceries\.morrisons\.com/webshop/product/[a-zA-Z0-9%\-\%\_]+/.*",
                     self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        with requests.Session() as s:
            s.get('https://groceries.morrisons.com/webshop/startWebshop.do')
            self._extract_page_tree_with_retries(session=s)

    def not_a_product(self):
        product = self.tree_html.xpath('//meta[@property="og:type"]/@content')
        return False if product else True

    def _product_id(self):
        prod_id = self.tree_html.xpath('//meta[@itemprop="sku"]/@content')[0]
        return prod_id

    def _sku(self):
        return self._product_id()

    def _product_name(self):
        return self.tree_html.xpath('//strong[@itemprop="name"]/text()')[0]

    def _specs(self):
        specs = {}
        columns = self.tree_html.xpath('//span[@class="colOne" or @class="colTwo"]')
        for column in columns:
            keys = column.xpath('h3/text()')  # [Categories, Brand, Storage etc]
            counter = 1
            for key in keys:
                wrapper = column.xpath('ul[preceding-sibling::h3[contains(text(), "' + key + '")]]')
                if wrapper:  # there is ul/li construction
                    category_links = wrapper[0].xpath('li/h4/a/@href')
                    category_links = [self.complement_url(url) for url in category_links]
                    specs[key] = {'categories': category_links}
                    info = wrapper[1].xpath('li')  # other info in categories block
                    for block in info:
                        label = block.xpath('span[@class="label"]/text()')[0]
                        value = block.xpath('span[@class="autoWidth"]/a/@href')[0]
                        value = self.complement_url(value)
                        specs[key].update({label: value})
                else:
                    info = column.xpath('p[' + str(counter) + ']/text()')
                    specs.update({key: " ".join(info)})
                    counter += 1
        return specs

    def _description(self):
        description = []
        description_block = self.tree_html.xpath('//div[@id="bopBottom"]/div[1]')[0]

        for index in range(len(description_block.xpath('p'))):
            text_block = description_block.xpath('p[' + str(index + 1) + ']/text()')
            text_block = "\n".join(text_block)
            description.append(text_block)
        return "\n".join(description)

    def _ingredients(self):
        ingredients = []
        for elem in self.tree_html.xpath('//div[@class="bopSection"]'):
            if elem.xpath('./h3/text()') and elem.xpath('./h3/text()')[0].strip() == 'Ingredients':
                texts = elem.xpath('./p/text()')
                for text in texts:
                    ingredients.append(text.strip())
                return ingredients

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        out_of_stock = self.tree_html.xpath('//p[@class="stock-status oos"]')
        if out_of_stock:
            return 1
        return 0

    def _no_longer_available(self):
        return 0

    def _image_urls(self):
        image_urls = [self.complement_url(url) for url in self.tree_html.xpath('//ul[@id="galleryImages"]/li/a/@href')]
        return image_urls

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.reviews_checked = True

        reviews = []
        review_count = self.tree_html.xpath('//strong[@itemprop="ratingCount"]')
        if review_count:
            self.review_count = int(review_count[0].text.strip()) if review_count else 0
            self.average_review = float(self.tree_html.xpath('//meta[@itemprop="ratingValue"]/@content')[0])
            rating = self.tree_html.xpath('//span[@class="reviewsCount"]/text()')
            if rating:
                rating = rating[:5]
                rating = rating[::-1]
                for i in range(1, 6):
                    reviews.append((i, int(rating[i-1].strip())))
                    self.reviews = reviews[::-1]
        return self.reviews

    def _price(self):
        price = self.tree_html.xpath('//span[@class="nowPrice"]/text()')
        if not price:
            price = self.tree_html.xpath('//div[@class="typicalPrice"]/h5/text()')
        return price[0].strip() if price else None

    def _in_stores(self):
        return 0

    def _categories(self):
        categories = self.tree_html.xpath('//ul[@class="categories"]/li/h4/a/text()')

        if categories:
            return [category.strip() for category in categories]

    def _brand(self):
        brand = self.tree_html.xpath('//span[@itemprop="brand"]/a/span/text()')
        return brand[0] if brand else None

    def _temp_price_cut(self):
        price_cut = self.tree_html.xpath('//span[@class="wasPrice"]')
        return 1 if price_cut else 0

    @staticmethod
    def complement_url(url):
        base_url = "https://groceries.morrisons.com"
        return urljoin(base_url, url)

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "ingredients": _ingredients,
        "specs": _specs,
        "sku": _sku,

        "image_urls": _image_urls,
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price": _price,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "no_longer_available": _no_longer_available,
        "temp_price_cut": _temp_price_cut,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
    }
