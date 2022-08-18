# -*- coding: utf-8 -*-#
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import urllib
import traceback

from scrapy import Request
from scrapy.log import WARNING

from product_ranking.spiders.amazon import AmazonProductsSpider


class AmazonPrimeProductsSpider(AmazonProductsSpider):
    name = 'amazonprime_products'

    SIGNIN_URL = 'https://www.amazon.com/ap/signin?_encoding=UTF8&openid.assoc_handle=usflex&openid.claimed_id' \
                 '=http://specs.openid.net/auth/2.0/identifier_select&openid.identity' \
                 '=http://specs.openid.net/auth/2.0/identifier_select&openid.mode' \
                 '=checkid_setup&openid.ns=http://specs.openid.net/auth/2.0&openid.ns.pape' \
                 '=http://specs.openid.net/extensions/pape/1.0&openid.pape.max_auth_age=0' \
                 '&openid.return_to=https://www.amazon.com/?ref_=nav_custrec_signin'

    SIGNIN_POST = 'https://www.amazon.com/ap/signin'

    PRIME_USERNAME = 'caiprime@contentanalyticsinc.com'
    PRIME_PASSWORD = '414Brannan'

    prime_cookies = {
        "csm-hit": "09RVG4WB2W1A49JWXZAF+s-SG1ZK0EEPNPE4EM514DG|1508280606345",
        "lc-acbuk": "en_US",
        "session-id": "262-4982414-1378213",
        "session-token": "HpCcW+sdWDFyPSCoK4eXCWx/4l80uQUT7ENiLgZm6PKo8gt5JEPQEkmrn6GjcQWLuaqg290oRMJV/" \
                         "ALy3aPOmIDtNQdoJzN3NgvHG9tnHrX0S/CYJQIzInNRayWpmV0zSRJz9hWSp0JAL2sMuEGdmbMySn5+cvGXATbn12J+T5" \
                         "new4TDbTDvDh5rheu80zDNbUUFXcX2ltdjRnMJU8hwjsq2rSRgNsrSuDPaZBgaokUsHYeRSOz71cypjymXq6YG",
        "ubid-acbuk": "130-5580928-3829627",
        "x-wl-uid": "1HPg4fV/XDO302Z/+f3weGk++t2wfaDxkL22GyVI21Mu8kGqHKB2m8PLFZV0nYsLbmBMLPFT5xgc="
    }

    def __init__(self, *args, **kwargs):
        super(AmazonPrimeProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(self.SIGNIN_URL,
                      callback=self.login_handler)

    def login_handler(self, response):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept-Language': 'en-US,en;q=0.8',
            "Host": "www.amazon.com",
            "Origin": "https://www.amazon.com",
            "Referer": self.SIGNIN_URL,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, '
                          'like Gecko) Chrome/65.0.3325.181 Safari/537.36',
        }

        payload = None
        try:
            payload = {
                'appActionToken': response.xpath("//input[@name='appActionToken']/@value").extract()[0],
                'appAction': 'SIGNIN',
                'openid.pape.max_auth_age': response.xpath("//input[@name='openid.pape.max_auth_age']/@value").extract()[0],
                'openid.return_to': response.xpath("//input[@name='openid.return_to']/@value").extract()[0],
                'prevRID': response.xpath("//input[@name='prevRID']/@value").extract()[0],
                'openid.identity': response.xpath("//input[@name='openid.identity']/@value").extract()[0],
                'openid.assoc_handle': response.xpath("//input[@name='openid.assoc_handle']/@value").extract()[0],
                'openid.mode': response.xpath("//input[@name='openid.mode']/@value").extract()[0],
                'openid.ns.pape': response.xpath("//input[@name='openid.ns.pape']/@value").extract()[0],
                'prepopulatedLoginId': '',
                'failedSignInCount': response.xpath("//input[@name='failedSignInCount']/@value").extract()[0],
                'openid.claimed_id': response.xpath("//input[@name='openid.claimed_id']/@value").extract()[0],
                'pageId': response.xpath("//input[@name='pageId']/@value").extract()[0],
                'openid.ns': response.xpath("//input[@name='openid.ns']/@value").extract()[0],
                'email': self.PRIME_USERNAME,
                'create': '0',
                'password': self.PRIME_PASSWORD,
            }
        except:
            self.log('Error while parsing payload: {}'.format(traceback.format_exc()), WARNING)

        if payload:
            yield Request(self.SIGNIN_POST,
                          method="POST",
                          body=urllib.urlencode(payload),
                          headers=headers,
                          cookies=self.prime_cookies,
                          callback=self._start_requests)

    def _start_requests(self, response):
        return super(AmazonPrimeProductsSpider, self).start_requests()
