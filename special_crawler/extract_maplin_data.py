#!/usr/bin/python
#  -*- coding: utf-8 -*-

import re
import json

from extract_data import Scraper


class MaplinScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.maplin.co.uk/p/<product-id>"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=p8bkgbkwhg9r9mcerwvg75ebc" \
            "&apiversion=5.5" \
            "&displaycode=19113-en_gb" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    def check_url_format(self):
        m = re.match(r"^http://www\.maplin\.co\.uk/p/([a-zA-Z0-9\-]+)?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//div[@itemtype="http://schema.org/Product"]')

        if not itemtype:
            return True

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.tree_html.xpath("//input[@name='productCodePost']/@value")[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath("//h1[@itemprop='name']")[0].text

    def _product_title(self):
        return self.tree_html.xpath("//h1[@itemprop='name']")[0].text

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()
    
    def _upc(self):
        return self.tree_html.xpath("//span[@itemprop='sku']//text()")[0].strip()

    def _features(self):
        rows = self.tree_html.xpath("//table[@class='product-specs']//tr")
        
        # list of lists of cells (by rows)
        cells = map(lambda row: row.xpath(".//*//text()"), rows)
        # list of text in each row
        cells = cells[1:]
        rows_text = map(\
            lambda row: ":".join(\
                map(lambda cell: cell.strip(), row)\
                ), \
            cells)
        all_features_text = rows_text
        all_features_text = [r for r in all_features_text if len(self._clean_text(r)) > 0]
        # return dict with all features info
        return all_features_text

    def _description_helper(self):
        description = "\n".join(self.tree_html.xpath("(//div[@class='product-summary']//ul)[2]//li//text()")).strip()
        return description

    def _description(self):
        description = self._description_helper()
        if len(description) < 1:
            return self._long_description_helper()
        return description

    def _long_description_helper(self):
        long_description = "\n".join(self.tree_html.xpath("//div[@class='productDescription']//text()")).strip()
        script = "\n".join(self.tree_html.xpath("//div[@class='productDescription']//script//text()")).strip()
        h4_txt = "\n".join(self.tree_html.xpath("//div[@id='tab_overview']//h4//text()")).strip()
        long_description = long_description.replace(script, "")
        if len(h4_txt) > 0:
            long_description = h4_txt + "\n" + long_description
        return long_description

    def _long_description(self):
        description = self._description_helper()
        if len(description) < 1:
            return None
        return self._long_description_helper()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []
        rows = self.tree_html.xpath("//ul[@id='carousel_alternate']//li/a/@data-cloudzoom")
        for row in rows:
            jsn = json.loads(row)
            try:
                image_urls.append(jsn["zoomImage"])
            except:
                pass
        # image_url = self.tree_html.xpath("//ul[@id='carousel_alternate']//img/@src")
        return image_urls

    def _video_urls(self):
        video_url = self.tree_html.xpath("//ul[@id='carousel_alternate']//a[@class='gallery-video']/@href")
        if len(video_url) == 0:
            return None
        return video_url

    def _pdf_urls(self):
        pdfs = self.tree_html.xpath("//a[contains(@href,'.pdf')]")
        pdf_hrefs = []
        for pdf in pdfs:
            try:
                if pdf.attrib['title'] == 'Terms & Conditions':
                    continue
            except KeyError:
                pass
            pdf_hrefs.append("http://www.maplin.co.uk%s" % pdf.attrib['href'])
        if len(pdf_hrefs) == 0:
            return None
        return pdf_hrefs

    def _webcollage(self):
        return 0

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################
    def _price(self):
        price = self.tree_html.xpath("//meta[@itemprop='price']/@content")[0].strip()
        currency = self.tree_html.xpath("//meta[@itemprop='priceCurrency']/@content")[0].strip()
        if price and currency:
            return "%s %s" % (currency, price)
        else:
            return None

    def _price_amount(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        return float(price_amount)

    def _price_currency(self):
        price = self._price()
        price = price.replace(",", "")
        price_amount = re.findall(r"[\d\.]+", price)[0]
        price_currency = price.replace(price_amount, "")
        if price_currency == "$":
            return "USD"
        elif price_currency == "£":
            return "GBP"
        return price_currency

    def _in_stores(self):
        # available to purchase in stores, 1/0
        rows = self.tree_html.xpath("//input[contains(@class,'grey discontinued')]")
        if len(rows) > 0:
            return 0
        rows = self.tree_html.xpath("//div[contains(@class,'prod_add_to_cart')]//input[contains(@class,'emailwhenstock')]")
        if len(rows) > 0:
            return 0
        return 1

    def _marketplace(self):
        return 0

    def _site_online(self):
        # site_online: the item is sold by the site (e.g. "sold by Amazon") and delivered directly, without a physical store.
        rows = self.tree_html.xpath("//input[contains(@class,'grey discontinued')]")
        if len(rows) > 0:
            return 1
        rows = self.tree_html.xpath("//div[contains(@class,'prod_add_to_cart')]//input[contains(@class,'emailwhenstock')]")
        if len(rows) > 0:
            return 1
        lis = self.tree_html.xpath("//ul[contains(@class,'stock-status')]//li")
        for li in lis:
            txt = li.xpath(".//text()")[0].strip()
            i_class = li.xpath(".//i/@class")[0].strip()
            if txt == "Home Delivery" and i_class == "icon-ok-sign":
                return 1
            elif txt == "Home Delivery" and i_class == "icon-remove-sign":
                return 0
        return 1

    def _site_online_out_of_stock(self):
        #  site_online_out_of_stock - currently unavailable from the site - binary
        if self._site_online() == 0:
            return None
        rows = self.tree_html.xpath("//input[contains(@class,'grey discontinued')]")
        if len(rows) > 0:
            return 1
        rows = self.tree_html.xpath("//div[contains(@class,'prod_add_to_cart')]//input[contains(@class,'emailwhenstock')]")
        if len(rows) > 0:
            return 1
        lis = self.tree_html.xpath("//ul[contains(@class,'stock-status')]//li")
        for li in lis:
            txt = li.xpath(".//text()")[0].strip()
            i_class = li.xpath(".//i/@class")[0].strip()
            if txt == "Home Delivery" and i_class == "icon-ok-sign":
                return 0
            elif txt == "Home Delivery" and i_class == "icon-remove-sign":
                return 1
        return 0

    def _web_only(self):
        txts = self.tree_html.xpath("//div[contains(@class,'product-images')]//p[contains(@class,'tab-webonly')]//text()")
        if "Web only" in txts:
            return 1
        return 0

    def _home_delivery(self):
        rows = self.tree_html.xpath("//ul[contains(@class,'stock-status')]//li")
        for row in rows:
            txt = row.xpath(".//text()")[0].strip()
            if "Home Delivery" in txt:
                i_tag = row.xpath(".//i[contains(@class,'icon-ok-sign')]")
                if len(i_tag) > 0:
                    return 1
        return 0

    def _click_and_collect(self):
        rows = self.tree_html.xpath("//ul[contains(@class,'stock-status')]//li")
        for row in rows:
            txt = row.xpath(".//text()")[0].strip()
            if "Click & Collect" in txt:
                i_tag = row.xpath(".//i[contains(@class,'icon-ok-sign')]")
                if len(i_tag) > 0:
                    return 1
        return 0

    def _dsv(self):
        txts = self.tree_html.xpath("//div[@id='product-ctas']//div//text()")
        if "Shipped from an alternative warehouse" in txts:
            return 1
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################
    def _categories(self):
        all = self.tree_html.xpath("//ul[contains(@class, 'breadcrumb')]//li//span/text()")
        out = all[1:-1]#the last value is the product itself, and the first value is "home"
        out = [self._clean_text(r) for r in out]
        #out = out[::-1]
        return out

    def load_universal_variable(self):
        js_content = ' '.join(self.tree_html.xpath('//script//text()'))

        universal_variable = {}
        universal_variable["manufacturer"] = re.findall(r'"manufacturer": "(.*?)"', js_content)[0]
        return universal_variable

    def _brand(self):
        return self.load_universal_variable()["manufacturer"]

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################
    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service
    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id" : _product_id, \

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name, \
        "product_title" : _product_title, \
        "title_seo" : _title_seo, \
        "features" : _features, \
        "description" : _description, \
        "long_description" : _long_description, \

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls, \
        "video_urls" : _video_urls, \
        "webcollage" : _webcollage, \
        "pdf_urls" : _pdf_urls, \

        # CONTAINER : SELLERS
        "price" : _price, \
        "price_amount" : _price_amount, \
        "price_currency" : _price_currency, \
        "web_only" : _web_only, \
        "home_delivery" : _home_delivery, \
        "click_and_collect" : _click_and_collect, \
        "dsv" : _dsv, \
        "in_stores" : _in_stores, \
        "marketplace": _marketplace, \
        "site_online" : _site_online, \
        "site_online_out_of_stock" : _site_online_out_of_stock, \

        # CONTAINER : CLASSIFICATION
        "categories" : _categories, \
        "brand" : _brand, \
        }
