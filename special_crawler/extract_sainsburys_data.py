#!/usr/bin/python

import re
import json
import urllib
import requests
import urlparse

import traceback
from lxml import html
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class SainsburysScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    REVIEW_URL = "http://sainsburysgrocery.ugc.bazaarvoice.com/8076-en_gb/{}/reviews.djs?format=embeddedhtml"

    LOGIN_URL = "https://www.sainsburys.co.uk/webapp/wcs/stores/servlet/Logon"

    LOGIN_PAGE = "https://www.sainsburys.co.uk/webapp/wcs/stores/servlet/LogonView" \
                 "?catalogId=10122&langId=44&storeId=10151&logonCallerId=LogonButton&URL=TopCategoriesDisplayView"

    LOGIN_DATA = {
        "storeId": 10151,
        "remember_me": "true",
        "currentViewName": "PostCodeCheckBeforeAddToTrolleyView",
        "reLogonURL": "https://www.sainsburys.co.uk/shop/LogonView?logonCallerId=LogonButton"
                      "&isDeliveryPoscodeValid=false&storeId=10151&messageAreaId=rhsLogonMessageArea",
        "URL": "TopCategoriesDisplayView",
        "isDeliveryPoscodeValid": "false",
        "messageAreaId": "rhsLogonMessageArea",
        "logonCallerId": "LogonButton",
        "callToPostSSOLogon": "true",
        "logonId": "c-lbaltazar@contentanalyticsinc.com",
        "logonPassword": "CA-Laura-2017"
    }

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self._set_proxy()

        self.product_page_url = re.sub('http://', 'https://', self.product_page_url)

    @staticmethod
    def _fix_url(url):
        data = urlparse.urlparse(url)
        fixed_url = '{scheme}://{netloc}{path}'.format(
            scheme=data.scheme,
            netloc=data.netloc,
            path='/'.join([urllib.quote_plus(x) for x in data.path.split('/')])
        )
        if data.query:
            fixed_url += '?{}'.format(data.query)
        return fixed_url

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.Session() as s:
                    # Set auth cookies ##TODO remove this account and register new one
                    self._request(self.LOGIN_PAGE, session=s)
                    self._request(self.LOGIN_URL, session=s, verb='post', data=json.dumps(self.LOGIN_DATA))

                    response = self._request(self.product_page_url, session=s, log_status_code=True)

                    if response.ok:
                        content = response.text
                        self.tree_html = html.fromstring(content)
                        return
                    else:
                        self.product_page_url = self._fix_url(self.product_page_url)

            except Exception as e:
                if self.lh:
                    self.lh.add_list_log('errors', str(e))

                print traceback.format_exc()

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')

        if itemtype and itemtype[0] == "product":
            return False

        return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = re.findall(r"productId:\s'(\d+)", html.tostring(self.tree_html))
        return product_id[0] if product_id else None

    def _review_id(self):
        product_id = re.findall(r"productId:\s'(.*?)',", html.tostring(self.tree_html))
        return product_id[0] if product_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _get_product_name(self):
        product_name = self.tree_html.xpath("//div[@class='productTitleDescriptionContainer']//h1/text()")
        return product_name[0] if product_name else None

    def _product_name(self):
        product_name = self._get_product_name()
        brand = self._brand()
        if product_name:
            product_name = product_name.replace(brand, '').strip() if brand else product_name.strip()
            return product_name if product_name else None

    def _product_title(self):
        return self._product_name()

    def _brand(self):
        product_name = self._get_product_name()
        if product_name:
            return guess_brand_from_first_words(product_name)

    def _short_and_long_description(self):
        description = self.tree_html.xpath('//div[@class="productText"]')
        if not description:
            description = self.tree_html.xpath(
                '//h3[text()="Description"]/parent::div[contains(@class,"productText")]'
            )
        if not description:
            description = self.tree_html.xpath(
                '//h3[text()="Description"]/following-sibling::p'
            )
        if description:
            description = description[0].text_content().replace(u'\xa0', u' ')
            description = re.sub(r'Description', ' ', description)
            description = re.sub(r'\s+', ' ', description).strip()

        if description:
            return description.split(u'\u00a0')

        short_desc = self._clean_text(''.join(
            self.tree_html.xpath('//div[@class="mainProductInfo"]'
                                 '//div[@id="information"]/text()')
        ))

        long_desc = self._clean_text(''.join(
            self.tree_html.xpath('//div[@class="mainProductInfo"]'
                                 '//div[@id="information"]/p/descendant::text()')
        ))

        return [short_desc, long_desc]

    def _description(self):
        description = self._short_and_long_description()
        if description[0]:
            return description[0]

    def _long_description(self):
        description = self._short_and_long_description()
        if len(description) > 1 and description[1]:
            return description[1]

    def _ingredients(self):
        ingredients_list = []
        ingredients_info = self.tree_html.xpath("//ul[@class='productIngredients']//li")
        for ing_html in ingredients_info:
            include_span = ing_html.xpath(".//span/text()")
            include_li = ing_html.xpath('./text()')
            if include_span:
                ingredients_list.append(include_span[0])
            elif include_li:
                ingredients_list.append(include_li[0].replace(',', ''))
        if not ingredients_list:
            ingredients_info = self.tree_html.xpath(
                '//strong[contains(text(), "INGREDIENTS:")]/parent::p'
            )
            if ingredients_info:
                text = ingredients_info[0].text_content().replace('INGREDIENTS:', '')
                ingredients_list = re.findall(r'(.*?\)|.*?|),', text)
                ingredients_list.append(re.search(r'%s,\s(.*?)$' % ingredients_list[-1], text).group(1))

        return [x.strip() for x in ingredients_list] if ingredients_list else None

    def _manufacturer(self):
        manufacturer = self.tree_html.xpath('//h3[text()="Manufacturer"]/following-sibling::div//p/text()')
        manufacturer = ''.join(manufacturer) if manufacturer else None
        return manufacturer

    def _nutrition_facts(self):
        table = self.tree_html.xpath('//table[@class="nutritionTable"]')
        if table:
            table = table[0]
        else:
            return None
        keys = table.xpath('./thead/tr/th[position()>1]/text()')
        rows = table.xpath('./tbody/tr[position()]')
        if not rows:
            rows = table.xpath('./tr')
        header = None
        data = []
        for row in rows:
            header_value = row.xpath('./th[@class="rowHeader"]/text()')
            values = []
            if not header_value:
                header_value = header
            else:
                header_value = header_value[0]
                header = header_value
            for idx, key in enumerate(keys):
                value = row.xpath('./td[{}]/text()'.format(str(idx+1)))
                value = value[0] if value else None
                cell = (key, value)
                values.append(cell)
            data.append((header_value, values))
        return data if data else None

    def _warnings(self):
        warnings = self.tree_html.xpath('//p[strong/text()="Warnings:"]/following-sibling::p/text()')
        return warnings[0] if warnings else None

    def _preparation(self):
        return int(bool(
            self.tree_html.xpath('//h3[contains(text(), "Preparation")]')
        ))

    def _country_of_origin(self):
        return int(bool(
            self.tree_html.xpath('//h3[contains(text(), "Country of Origin")]')
        ))

    def _packaging(self):
        return int(bool(
            self.tree_html.xpath('//h3[contains(text(), "Packaging")]')
        ))

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_url_list = []
        grocery_site_name = 'http://www.sainsburys.co.uk'

        image_urls = self.tree_html.xpath("//div[@id='productImageHolder']/img/@src")

        if image_urls:
            for image_url in image_urls:
                image_url_list.append(grocery_site_name + image_url)

        return image_url_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath("//p[@class='pricePerUnit']/text()")
        return self._clean_text(price[0]) if price else None

    def _price_currency(self):
        return 'GBP'

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//ul[@id='breadcrumbNavList']//li//a//span/text()")
        return categories if categories else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "description": _description,
        "long_description": _long_description,
        "brand": _brand,
        "ingredients": _ingredients,
        "manufacturer": _manufacturer,
        "warnings": _warnings,
        "preparation": _preparation,
        "country_of_origin": _country_of_origin,
        "packaging": _packaging,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        }
