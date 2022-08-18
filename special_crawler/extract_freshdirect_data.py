#!/usr/bin/python
#  -*- coding: utf-8 -*-

import re
import requests
from extract_data import Scraper
import traceback
import urlparse

from lxml import html
from product_ranking.guess_brand import guess_brand_from_first_words


class FreshDirectScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www\.freshdirect\.com/(.*)"

    SET_ZIPCODE_URL = 'https://www.freshdirect.com/api/locationhandler.jsp?action=setZipCode&zipcode={}'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.zip_code = kwargs.get('zip_code')
        if not self.zip_code:
            self.zip_code = '10001'

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.Session() as s:
                    if not self._set_location(s):
                        raise Exception('Can\'t set location')
                    resp = self._request(
                        self.product_page_url,
                        session=s,
                        log_status_code=True
                    )
                    if resp.status_code != 200:
                        self.ERROR_RESPONSE['failure_type'] = resp.status_code
                        if resp.status_code != 404:
                            continue
                    self.page_raw_text = resp.content
                    self.tree_html = html.fromstring(self.page_raw_text)
                    return
            except Exception as e:
                if self.lh:
                    self.lh.add_list_log('errors', str(e))
                print traceback.format_exc(e)
        self.is_timeout = True

    def _set_location(self, session):
        r = self._request(
            self.SET_ZIPCODE_URL.format(self.zip_code),
            headers={'x-requested-with':'XMLHttpRequest'},
            session=session
        )
        return r.status_code == 200

    def check_url_format(self):
        m = re.match(r"^https?://www\.freshdirect\.com/.*$", self.product_page_url)
        return not not m

    def not_a_product(self):
        if len(self.tree_html.xpath("//div[@class='main-image']//img")) < 1:
            return True
        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################
    def _product_id(self):
        product_id = self.tree_html.xpath("//input[@name='productId']/@value")[0].strip()
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################
    def _product_name(self):
        return self._product_title()

    def _product_title(self):
        try:
            title = self.tree_html.xpath("//h1[@class='pdpTitle']/text()")[0].strip()
        except IndexError:
            title = self.tree_html.xpath('//span[@itemprop="name"]/text()')[0].strip()
        return title

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _description(self):
        description = self.tree_html.xpath("//div[contains(@class,'pdp-accordion-description')]//text()")
        return description[0] if description else None

    def _ingredients(self):
        ingredients = self.tree_html.xpath('//li[contains(@class, "dp-accordion-ingredients")]//td/text()')
        if ingredients:
            return [x.strip() for x in re.split(r',\s*(?![^()]*\))', ingredients[0])]

    def _nutrition_facts(self):
        nutrition_facts = self.tree_html.xpath('//div[@id="drugpanel"]//td[@class="text9"]/text()')
        return [x for x in nutrition_facts if x.strip() != ''] if nutrition_facts else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        images = self.tree_html.xpath("//p[@class='thumbnails']//img")
        if not images:
            images = self.tree_html.xpath("//div[@class='main-image']//img")

        for image in images:
            large_image = image.xpath("./@data-large-url")
            if large_image and self._clean_text(large_image[0]):
                image_urls.append(urlparse.urljoin(self.product_page_url, large_image[0]))
            else:
                image_urls.append(urlparse.urljoin(self.product_page_url, image.xpath("./@src")[0]))

        return image_urls

    def _pdf_urls(self):
        pdfs = self.tree_html.xpath("//a[contains(@href,'.pdf')]")
        pdf_hrefs = []
        for pdf in pdfs:
            pdf_hrefs.append(pdf.attrib['href'])
        return pdf_hrefs

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################
    #populate the reviews_tree variable for use by other functions
    def _average_review(self):
        average_review = self.tree_html.xpath("//ul[@class='ratings']"
                                              "//b[contains(@class,'expertrating')]//text()")[0].strip()
        average_review = re.search('Rating (\d+)/10', average_review)
        return float(average_review.group(1)) / 2.0 if average_review else None

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath("//div[@class='pdp-price']//text()")
        price = filter(None, [x.strip() for x in price])[0]
        price = re.findall(r"(\$[\d\.]+)", price, re.DOTALL)[0]
        return price

    def _in_stores(self):
        return 0

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        rows = self.tree_html.xpath("//div[@class='pdp-atc']//button[@data-component='ATCButton']")
        if len(rows) > 0:
            return 0
        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        all = self.tree_html.xpath("//ul[@class='breadcrumbs']//li//text()")
        out = [self._clean_text(r) for r in all]
        if len(out) < 1:
            return None
        return out

    def _brand(self):
        return guess_brand_from_first_words(self._product_title())

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces

    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################
    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service
    DATA_TYPES = {
        # CONTAINER: NONE
        "product_id": _product_id,

        # CONTAINER: PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,
        "ingredients": _ingredients,

        # CONTAINER: PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "pdf_urls": _pdf_urls,

        # CONTAINER: SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER: REVIEWS
        "average_review": _average_review,

        # CONTAINER: CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
    }
