#!/usr/bin/python

import re
import requests
import lxml.html as html
from extract_data import Scraper


class IcelandcoukScraper(Scraper):
    INVALID_URL_MESSAGE = "Expected URL format is http://groceries.iceland.co.uk/(<product-name>/)p/<product-code>"

    def check_url_format(self):
        m = re.match(r"http://groceries\.iceland\.co\.uk/([\w-]+/)?p/[\d]+", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if not self.tree_html.xpath("//meta[@property='og:type' and @content='food']"):
            return True

    def _product_id(self):
        product_id = self.tree_html.xpath('//*[@data-sku]/@data-sku')
        if product_id:
            return product_id[0]

    def _product_name(self):
        product_name = self.tree_html.xpath('//meta[@property="og:title"]/@content')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        description = self.tree_html.xpath('//meta[@name="description"]/@content')
        if description:
            return description[0]

    def _specs(self):
        specs = {}
        product_info = self.tree_html.xpath('//div[@id="product_information"]')
        if product_info:
            labels = re.findall(r'<h3>(.*?)</h3>', html.tostring(product_info[0]).replace('\n', ''))
            data = re.findall(r'</h3>(.*?)(?:<h3>|</div>)', html.tostring(product_info[0]).replace('\n', ''))
            for k,x in enumerate(data):
                tree = html.fromstring(x)
                specs.update({labels[k].strip(): " ".join([x.strip() for x in tree.xpath('//*/text()')]).strip()})
        return specs if specs else None


    def _image_urls(self):
        image_url = self.tree_html.xpath('//meta[@property="og:image"]/@content')
        if image_url:
            return image_url

    def _image_count(self):
        return 1

    def _price(self):
        price = self.tree_html.xpath('//span[contains(@class, "big-price")]/text()')
        if price:
            return price[0]

    def _price_amount(self):
        price = self._price()
        if price:
            price = price.replace(",", "")
            price_amount = re.findall(r"[\d\.]+", price)[0]
            return float(price_amount)

    def _price_currency(self):
        return 'GBP'

    def _categories(self):
        categories = self.tree_html.xpath('//div[@id="breadcrumb"]//a/span[2]/text()')
        if categories:
            return categories

    def _brand(self):
        brand = self.tree_html.xpath('//div[@class="brand"]/p/text()')
        return brand[0] if brand else 'Iceland'

    def _sku(self):
        sku = self.tree_html.xpath('//*[@data-sku]/@data-sku')
        if sku:
            return sku[0]

    def _ingredients(self):
        ingredient_info = []
        ingredients = self.tree_html.xpath('//div[preceding-sibling::h1[text()="Ingredients"]]/p[1]//text()')
        if ingredients:
            ingredient_info = ingredients[0].split(",")
        return ingredient_info if ingredient_info else None

    def _average_review(self):
        average_review = self.tree_html.xpath('//span[@class="ib mR5 bold"]/text()')
        if average_review:
            return round(float(average_review[0]), 2)

    def _review_count(self):
        count = self.tree_html.xpath('//span[@class="ib mR5 lteGrey"]/text()')
        if count:
            count = count[0]
            count = int(re.findall(r'\d+', count)[0])
        return count if count else 0

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        self.reviews = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
        reviews_url = self.product_page_url + '/reviewhtml/all'
        r = requests.get(reviews_url, timeout=10)
        body = html.fromstring(r.text)
        raw_reviews = body.xpath('//span[contains(@style, "width")]/@style')

        if raw_reviews:
            for review in raw_reviews:
                review = int(re.findall(r'\d+', review)[0]) / 20
                self.reviews[5 - review][1] += 1
        else:
            self.reviews = None

        return self.reviews

    def _nutrition_fact_count(self):
        nutrition_fact_count = 0
        nutrition_block = self.tree_html.xpath('//div[@id="product_nutrition"]//table//tr')
        for nutrition in nutrition_block:
            item = nutrition.xpath('.//td/text()')
            if item and len(item) > 1 and re.match(r'^\d+\.?\d*.*?', item[-1]):
                nutrition_fact_count += 1
        return nutrition_fact_count if not nutrition_fact_count == 0 else None

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if '("product[0].productInfo.badge", ["unavailable"])' in html.tostring(self.tree_html):
            return 1
        return 0

    DATA_TYPES = {
        "product_id": _product_id,

        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "specs": _specs,
        "sku": _sku,
        "ingredients": _ingredients,
        "nutrition_fact_count": _nutrition_fact_count,

        "image_urls": _image_urls,
        "image_count": _image_count,

        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        "price": _price,
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "site_online": _site_online,

        "categories": _categories,
        "brand": _brand,
    }
