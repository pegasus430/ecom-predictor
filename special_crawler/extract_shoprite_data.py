#!/usr/bin/python

from extract_webgrocer_data import WebGrocerScraper


class ShopriteScraper(WebGrocerScraper):

    SITE = 'shop.shoprite.com'

    API_URL = 'https://{0}/api/product/v7/chains/FBFB139/stores/{1}/skus/{2}'

    HEADERS = {
        "Accept": "application/vnd.mywebgrocer.wakefern-product+json",
        "Authorization": None
    }
