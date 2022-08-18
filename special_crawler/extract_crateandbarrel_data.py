#!/usr/bin/python

import re
import urlparse

from extract_data import Scraper
from spiders_shared_code.crateandbarrel_variants import CrateandbarrelVariants


class CrateandbarrelScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.crateandbarrel.com/.*?/[\w\d]+"

    REVIEW_URL = 'http://api.bazaarvoice.com/data/batch.json' \
                       '?passkey=ikuyof7cllxe0ctfrkp7ow23y' \
                       '&apiversion=5.5' \
                       '&displaycode=7258-en_us' \
                       '&resource.q0=products' \
                       '&filter.q0=id%3Aeq%3A{}' \
                       '&stats.q0=reviews' \
                       '&filteredstats.q0=reviews' \
                       '&filter_reviews.q0=contentlocale%3Aeq%3Aen_US' \
                       '&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen_US'

    def check_url_format(self):
        m = re.match(r"^https?://www.crateandbarrel.com/.*?/[\w\d]+", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        pid = self.tree_html.xpath(
            '//meta[@property="og:type" and @content="product"]')
        return not bool(pid)

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
        product_name = self.tree_html.xpath('//h1[@id="productNameHeader"]/text()')
        if not product_name:
            product_name = self.tree_html.xpath('//h1[@class="productHeader"]/text()')
        return product_name[0] if product_name else None

    def _product_title(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _description(self):
        short_description = self.tree_html.xpath('//*[contains(@class,"hwDetailsP")]//text()')
        if short_description:
            return " ".join([text.strip() for text in short_description]).strip()

    def _variants(self):
        self.variants = CrateandbarrelVariants()
        self.variants.setupCH(self.tree_html, self.product_page_url)
        variants = self.variants._variants()
        return variants

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = self.tree_html.xpath('//li[@class="thumbnailImage"]//img/@src')
        image_list = [urlparse.urljoin(url, urlparse.urlparse(url).path) for url in image_list]
        if image_list:
            return image_list

        if not image_list:
            return self.tree_html.xpath('//img[contains(@class,"hwProductImage")]/@src')

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
        FLOATING_POINT_RGEX = re.compile('\d{1,3}[,\.\d{3}]*\.?\d*')
        price = self.tree_html.xpath(
            '//meta[@property="og:price:amount"]/@content'
        )[0]
        price = re.search(FLOATING_POINT_RGEX, price)
        return price.group() if price else None

    def _price_amount(self):
        return float(self._price())

    def _price_currency(self):
        currency = self.tree_html.xpath(
            '//meta[@property="og:price:currency"]/@content'
        )
        return currency[0] if currency else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath("//link[@itemprop='availability']/@href")[0].strip() == "http://schema.org/InStock":
            return 0

        return 1

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//div[@id="SiteMapPath"]//a/text()')
        return categories

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service
    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \
\
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "title_seo": _title_seo, \
        "description": _description, \
        "variants": _variants, \
\
        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \
        "pdf_urls": _pdf_urls, \
\
        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
\
        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        }
