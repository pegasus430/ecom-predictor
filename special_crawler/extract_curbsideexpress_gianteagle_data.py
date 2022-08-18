#!/usr/bin/python

from extract_webgrocer_data import WebGrocerScraper


class CurbSideExpressGiantEagleScraper(WebGrocerScraper):

    API_URL = 'https://{0}/api/product/v7/product/store/{1}/sku/{2}'

    SITE = 'curbsideexpress.gianteagle.com'
