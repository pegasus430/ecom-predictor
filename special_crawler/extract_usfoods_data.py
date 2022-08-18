#!/usr/bin/python

import re
import requests
import traceback

from lxml import html
from extract_data import Scraper


class UsfoodsScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www3.usfoods.com/<product-name>"

    HOME_URL = 'https://www3.usfoods.com/order/faces/oracle/webcenter/portalapp/pages/home/homePage.jspx'

    def _extract_page_tree(self):
        agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2987.98 Safari/537.36"
        headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'User-agent': agent,
                   'Accept-Language': 'en-US, en;q=0.8',
                   'Adf-Rich-Message': 'true',
                   'Connection': 'keep-alive',
                   'Host': 'www3.usfoods.com',
                   'Origin': 'https://www3.usfoods.com',
                   'Referer': 'https://www3.usfoods.com/order/faces/oracle/webcenter/portalapp/pages/login.jspx',
        }

        for i in range(3):
            # Use 'with' to ensure the session context is closed after use.
            try:
                with requests.Session() as s:
                    welcome_response = s.get(self.HOME_URL, timeout=20)
                    home_html = welcome_response.content
                    view_state = html.fromstring(home_html).xpath("//input[@name='javax.faces.ViewState']/@value")[0]
                    LOG_IN_URL = "https://www3.usfoods.com" + html.fromstring(home_html).xpath("//form[@id='f1']/@action")[0]

                    data = {"it9": "CONTENTANALYTICS", "it1": "Victory16", "it2": "1440x900", "it3": "Netscape",
                            "it4": "5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.98 Safari/537.36",
                            "it5": "true", "it6": "Linux x86_64",
                            "org.apache.myfaces.trinidad.faces.FORM": "f1",
                            "javax.faces.ViewState": view_state,
                            "event": "cb1", "event.cb1": "<m xmlns='http://oracle.com/richClient/comm'><k v='type'><s>action</s></k></m>"
                            }

                    s.post(LOG_IN_URL, data=data, headers=headers, timeout=20)
                    r = s.get(self.product_page_url, headers=headers, timeout=20)

                    if self.lh:
                        self.lh.add_log('status_code', r.status_code)

                    if r.status_code != 200:
                        self.ERROR_RESPONSE['failure_type'] = r.status_code
                        self.is_timeout = True
                        return

                    self.tree_html = html.fromstring(r.content)

            except:
                print traceback.format_exc()

    def check_url_format(self):
        m = re.match(r"^https?://www3.usfoods.com/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        return False

    def _product_id(self):
        product_id = self.tree_html.xpath("//span[@class='x242']/text()")
        if product_id:
            product_id = re.search('\d+', product_id[0])
        return product_id.group() if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//span[@class='x2cg']/text()")
        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _description(self):
        description = self.tree_html.xpath("//span[@class='x246']/text()")
        return description[1] if len(description) > 1 else None

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@id='pt1:r1:0:r1:0:pt1:pgl88']//span/text()")
        return ' '.join(long_description) if long_description else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//table[@id='pt1:r1:0:r1:0:pt1:c6:dc_pgl6']//img[@class='x12x']/@src")
        if not image_urls:
            image_urls = self.tree_html.xpath("//div[contains(@class, 'x2cu')]//img[@class='xjd']/@src")
        return image_urls

    def _ingredients(self):
        ingredients = self.tree_html.xpath("//div[@id='pt1:r1:0:r1:0:pt1:pgl11']//span[@class='x242']/text()")
        return ingredients[0].split(',') if ingredients else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price_amount = 0.0
        price_data = self.tree_html.xpath("//div[@class='x1a']//span[@class='x246']/text()")
        if price_data:
            price_amount = re.search('\d+\.\d*', price_data[-1])
        if price_amount:
            return float(price_amount.group())

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "description": _description,
        "long_description": _long_description,
        "ingredients": _ingredients,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock
    }
