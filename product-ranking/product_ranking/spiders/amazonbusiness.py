from __future__ import division, absolute_import, unicode_literals

import re
import traceback

from scrapy.http import Request
from scrapy.conf import settings
from scrapy import FormRequest
from scrapy.log import ERROR

from product_ranking.spiders.amazonfresh import AmazonFreshProductsSpider


class AmazonBusinessProductsSpider(AmazonFreshProductsSpider):
    name = "amazonbusiness_products"

    SIGNIN_URL = 'https://www.amazon.com/ap/signin?_encoding=UTF8&openid.assoc_handle=usflex&openid.claimed_id' \
                 '=http://specs.openid.net/auth/2.0/identifier_select&openid.identity' \
                 '=http://specs.openid.net/auth/2.0/identifier_select&openid.mode' \
                 '=checkid_setup&openid.ns=http://specs.openid.net/auth/2.0&openid.ns.pape' \
                 '=http://specs.openid.net/extensions/pape/1.0&openid.pape.max_auth_age=0' \
                 '&openid.return_to=https://www.amazon.com/?ref_=nav_custrec_signin'
    AFTER_SIGNIN_URL = "https://www.amazon.com/ap/signin"

    def __init__(self, zip_code='94117', *args, **kwargs):
        settings.overrides['DUPEFILTER_CLASS'] = 'product_ranking.spiders.amazonfresh.CustomDupeFilter'
        self.zip_code = zip_code
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/60.0.3112.78 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.8",
            "Host": "www.amazon.com",
            "Origin": "https://www.amazon.com",
            "Referer": "https://www.amazon.com/ap/signin?_encoding=UTF8&openid.assoc_handle=usflex&openid.claimed_id" \
                       "=http://specs.openid.net/auth/2.0/identifier_select&openid.identity" \
                       "=http://specs.openid.net/auth/2.0/identifier_select&openid.mode" \
                       "=checkid_setup&openid.ns=http://specs.openid.net/auth/2.0&openid.ns.pape" \
                       "=http://specs.openid.net/extensions/pape/1.0&openid.pape.max_auth_age=0" \
                       "&openid.return_to=https://www.amazon.com/?ref_=nav_custrec_signin"
        }
        super(AmazonBusinessProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(
            self.WELCOME_URL,
            callback=self.pre_login_handler
        )

    def pre_login_handler(self, response):
        return FormRequest(
            self.CSRF_TOKEN_URL,
            method="GET",
            callback=self.login_handler,
            dont_filter=True,
        )

    def login_handler(self, response):
        csrf_token = re.findall(r'csrfToken\":\"([^\"]+)', response.body)
        if not csrf_token:
            self.log('Can\'t find csrf token.', ERROR)
            return None
        return FormRequest(
            self.ZIP_URL,
            formdata={
                'token': csrf_token[0],
                'zipcode': self.zip_code
            },
            callback=self.sign_in,
            dont_filter=True
        )

    def sign_in(self, response):
        return Request(
            url=self.SIGNIN_URL,
            callback=self.sigin_in_handle,
            dont_filter=True,
        )

    def sigin_in_handle(self, response):
        try:
            appActionTaken = response.xpath('//input[@name="appActionToken"]/@value')[0].extract()
            appAction = response.xpath('//input[@name="appAction"]/@value')[0].extract()
            max_auth_age = response.xpath('//input[@name="openid.pape.max_auth_age"]/@value')[0].extract()
            identity = response.xpath('//input[@name="openid.identity"]/@value')[0].extract()
            pageId = response.xpath('//input[@name="pageId"]/@value')[0].extract()
            return_to = response.xpath('//input[@name="openid.return_to"]/@value')[0].extract()
            prevRID = response.xpath('//input[@name="prevRID"]/@value')[0].extract()
            assoc_handle = response.xpath('//input[@name="openid.assoc_handle"]/@value')[0].extract()
            mode = response.xpath('//input[@name="openid.mode"]/@value')[0].extract()
            pape = response.xpath('//input[@name="openid.ns.pape"]/@value')[0].extract()
            failedSignInCount = response.xpath('//input[@name="failedSignInCount"]/@value')[0].extract()
            claimed_id = response.xpath('//input[@name="openid.claimed_id"]/@value')[0].extract()
            ns = response.xpath('//input[@name="openid.ns"]/@value')[0].extract()

            return FormRequest(
                url=self.AFTER_SIGNIN_URL,
                formdata={
                    "appActionToken": appActionTaken,
                    "appAction": appAction,
                    "openid.pape.max_auth_age": max_auth_age,
                    "openid.return_to": return_to,
                    "prevRID": prevRID,
                    "openid.identity": identity,
                    "openid.assoc_handle": assoc_handle,
                    "openid.mode": mode,
                    "openid.ns.pape": pape,
                    "prepopulatedLoginId": "",
                    "failedSignInCount": failedSignInCount,
                    "openid.claimed_id": claimed_id,
                    "pageId": pageId,
                    "openid.ns": ns,
                    "email": "alli@contentanalyticsinc.com",
                    "create": "0",
                    "password": "Greece12",
                },
                callback=self.after_login,
                headers=self.headers,
                dont_filter=True,
            )
        except:
            self.log("Sign In Error".format(traceback.format_exc()))