#!/usr/bin/python

from extract_webgrocer_data import WebGrocerScraper


class HarristeeterScraper(WebGrocerScraper):

    NUTRITION_URL = "https://{0}/api/product/v5/product/{1}/store/{2}/nutrition"

    def __init__(self, **kwargs):
        WebGrocerScraper.__init__(self, **kwargs)

        self._set_proxy()

    SITE = 'shop.harristeeter.com'
