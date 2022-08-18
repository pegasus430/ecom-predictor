# !/usr/bin/python

import re
import requests
from urlparse import urljoin
from extract_data import Scraper


class JumboMobileScraper(Scraper):
    INVALID_URL_MESSAGE = "Expected URL format is https://mobile.jumbo.com/<product-id>"
    PRODUCT_LINK = "http://mobileapi.jumbo.com/api/products/"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.product_json = {}

    def get_mobile_entrypoint(self, url):
        pattern = 'https?://mobile.jumbo.com/(.+)'
        product_id = re.match(pattern, url).group(1)

        url = urljoin(self.PRODUCT_LINK, product_id.encode('utf-8'))
        return url

    def _extract_page_tree(self):
        for i in range(self.MAX_RETRIES):
            try:
                url = self.get_mobile_entrypoint(self.product_page_url)
                self.json = requests.get(url).json()
                self.product_json = self.json.get('product', {}).get('data')
                return
            except:
                continue

    def check_url_format(self):
        m = re.match('https?://mobile.jumbo.com/.*', self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if not self.json or 'Lookup Not Found' in self.json.get('message', ''):
            return True
        return False

    def _product_id(self):
        return self.product_json.get('id')

    def _product_name(self):
        return self.product_json.get('title')

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _description(self):
        return self.product_json.get('detailsText')

    def _image_urls(self):
        image_urls = self.product_json.get('imageInfo', {}).get('details')
        image_urls = [image.get('url') for image in image_urls if '720x720' in image.get('url')]

        primary_view_image_urls = self.product_json.get('imageInfo', {}).get('primaryView')
        for image in primary_view_image_urls:
            if '720x720' in image.get('url'):
                image_urls.append(image.get('url'))

        if image_urls:
            return image_urls

    def _image_count(self):
        if self._image_urls():
            return len(self._image_urls())

        return 0

    def _price(self):
        label = self.product_json.get('promotion', {}).get('label')

        try:
            price = float(self.product_json.get('prices').get('price').get('amount'))
            price = price / 100
        except:
            return None

        if label:
            if 'gratis' in label:
                price = price / 2
            elif 'korting' in label:
                pattern = r'(\d*)'
                bonus = re.findall(pattern, label)
                if bonus:
                    bonus = bonus[0]
                    try:
                        bonus = float(bonus) / 100
                    except:
                        bonus = 0
                    price = round((1 - bonus) * price, 2)
            elif 'voor' in label:
                pattern = r'[\d\,]+'
                try:
                    amount = re.findall(pattern, label)[0]
                    bonus = re.findall(pattern, label)[1]
                    bonus = bonus.replace(',', '.')
                    price = round(float(bonus) / float(amount), 2)
                except:
                    return None

        return price

    def _price_currency(self):
        currency = self.product_json.get('prices', {}).get('price', {}).get('currency')
        return currency

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _categories(self):
        return [self._category_name()] if self._category_name() else None

    def _category_name(self):
        return self.product_json.get('topLevelCategory')

    def _brand(self):
        return self.product_json.get('promotion', {}).get('name')

    DATA_TYPES = {
        "product_id": _product_id,
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,

        "image_count": _image_count,
        "image_urls": _image_urls,

        "price": _price,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        "categories": _categories,
        "category_name": _category_name,
        "brand": _brand
    }
