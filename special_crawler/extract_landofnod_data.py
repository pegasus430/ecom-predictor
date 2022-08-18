#!/usr/bin/python

import re
import urlparse
from lxml import html

from extract_data import Scraper


class LandofNodScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    FLOATING_POINT_RGEX = re.compile('\d{1,3}[,.\d{3}]*\.?\d*')

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.landofnod.com/.*"

    REVIEW_URL = 'http://api.bazaarvoice.com/data/batch.json' \
                       '?passkey=q12j4skivgb89bci049b3pwua' \
                       '&apiversion=5.5' \
                       '&resource.q0=products' \
                       '&filter.q0=id%3Aeq%3A{}' \
                       '&stats.q0=reviews' \
                       '&filteredstats.q0=reviews' \
                       '&filter_reviews.q0=contentlocale%3Aeq%3Aen_US' \
                       '&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen_US'

    def check_url_format(self):
        m = re.match(r"^https?://www.landofnod.com/.*?/[\w\d]+", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        pid = self.tree_html.xpath(
            '//p[contains(text(), "Unfortunately, we are unable to locate the product you are looking for.")]')
        return bool(pid)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        prod_id = self.tree_html.xpath(
            '//script[contains(text(), "Crate.Reviews.init")]/text()'
        )[0]
        prod_id = re.search(r'Crate\.Reviews\.init\(\'([\w\d]+)\'', prod_id)
        return prod_id.group(1) if prod_id else None

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//meta[@property="og:title" and @id="_fbTitle"]/@content')
        return product_name[0] if product_name else None

    def _product_title(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _description(self):
        return self.tree_html.xpath('//div[@class="productDescriptionCopy"] |'
                                    '//p[@id="_productDescription" or @class="productDescription"]'
                                    )[0].text_content().strip()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = self.tree_html.xpath('//img[contains(@class,"imgZoomImage") or @class="jsZoomLarge"]/@src')

        if images:
            return map(lambda i: re.sub('(wid|hei)=\d+', r'\1=550', i), images)

    def _pdf_urls(self):
        pdf_links = list(
        urlparse.urljoin(self.product_page_url, url)for url in set(self.tree_html.xpath("//a[contains(@href,'.pdf')]/@href"))
        )

        if pdf_links:
            return pdf_links

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath(
            '//meta[@property="og:price:amount"]/@content'
        )[0]
        price = re.search(self.FLOATING_POINT_RGEX, price)
        return price.group() if price else None

    def _price_amount(self):
        return float(self._price())

    def _price_currency(self):
        currency = self.tree_html.xpath(
            '//meta[@property="og:price:currency"]/@content'
        )
        return currency[0] if currency else None

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath('//div[@class="breadcrumbsInnerWrap"]//a/text()')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "description": _description,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "pdf_urls": _pdf_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        }
