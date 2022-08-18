#!/usr/bin/python

import re
from lxml import html
import json

from extract_data import Scraper
from spiders_shared_code.lowesca_variants import LowesCaVariants


class LowesCAScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is https://www.lowes.ca/.*"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=pcmuj0pvxpdntavhu70avt4pk" \
            "&apiversion=5.5" \
            "&displaycode=11871-en_ca" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    API_URL = "https://media.flixcar.com/delivery/js/inpage/7074/b5/mpn/{prod_id}?&=7074&=b5&mpn={prod_id}&fl=us" \
              "&ssl=1&ext=.js"

    VIDEO_URL = "https://media.flixcar.com/delivery/inpage/show/7074/b5/{video_id}/json?c=jsonpcar7074b5{video_id}" \
                "&complimentary=0&type=.html"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.lcv = LowesCaVariants()
        self._set_proxy()

    def check_url_format(self):
        m = re.match(r"^https?://(www.)?lowes.ca/.*$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if len(self.tree_html.xpath('//div[contains(@itemtype, "Product")]')) < 1:
            return True
        self.lcv.setupCH(self.tree_html)
        return False

    ##########################################
    ############### CONTAINER : NONE

    ##########################################

    def _product_id(self):
        product_id = re.search("'prodid':(.*)}", html.tostring(self.tree_html)).group(1)
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//div[contains(@id, "prodTitle")]'
                                            '/h1[@itemprop="name"]/text()')
        if product_name:
            return product_name[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_title()

    def _model(self):
        model = re.search('model: (.*?)\',', html.tostring(self.tree_html))
        return model.group(1).replace('\'', '') if model else None

    def _description(self):
        description = self.tree_html.xpath('//div[contains(@id, "prodDesc")]//div[@class="mgb8"]/descendant::text()')
        return self._clean_text(''.join(description)) if description else None

    def _long_description(self):
        description = []
        short_description = self.tree_html.xpath('//div[contains(@id, "prodDesc")]//ul')
        for desc in short_description:
            description.append(html.tostring(desc))
        return self._clean_text(''.join(description)) if description else None

    def _sku(self):
        sku = self.tree_html.xpath('//meta[@itemprop="sku"]/@content')[0]
        return sku

    def _upc(self):
        upc = re.search("upc:'(\d+)'", html.tostring(self.tree_html))
        if upc:
            return upc.group(1)[:12].zfill(12)

    def _brand(self):
        brand = self.tree_html.xpath('//div[@itemprop="brand"]/meta[@itemprop="name"]/@content')
        return brand[0] if brand else None

    def _variants(self):
        return self.lcv._variants()

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = []
        for i in range(20):
            url = self._find_between(html.tostring(self.tree_html), 'arrAltImg['+str(i)+'] = {image:', ', caption').replace("\'", "")
            if url:
                image_list.append(url.replace('//', 'https://').replace('/t/', '/p400/'))
        return image_list

    def _video_urls(self):
        prod_id = self.tree_html.xpath('//div[@id="digitalDataInfo"]/@mfr_prod_id')

        data = self._request(self.API_URL.format(prod_id=prod_id[0]))

        video_id = re.findall('product:(.*?),', data.content)
        video_id = re.search('(\d+)', video_id[1], re.DOTALL).group(1)

        video_content = self._request(self.VIDEO_URL.format(video_id=video_id))
        data = re.search('"css(.*?)videos":true}', video_content.content, re.DOTALL)
        video_list = []
        if data:
            json_data = '{' + data.group() + '}'
            json_data = json.loads(json_data)
            html_content = html.fromstring(json_data.get('html'))

            videos = html_content.xpath('//a[@class="flix_jw_videoid"]/@data-jw')
            for video in videos:
                video_list.append('http:' + video)

        else:
            list = re.findall("player.vimeo.com(.*?)wmode", html.tostring(self.tree_html))
            if list:
                for video in list:
                    video_list.append('https://player.vimeo.com' + video.replace('?', ''))

        if not video_list:
            list = re.findall("'video','(.*?)','", html.tostring(self.tree_html))
            for video in list:
                if 'mp4' or 'flv' in video:
                    video_list.append('https://www.lowes.ca' + video.replace('\\\\', '\\'))
            youtube = re.findall("youtube.com(.*?)wmode", html.tostring(self.tree_html))
            if youtube:
                for y in youtube:
                    video_list.append('https://www.youtube.com' + y.split('?')[0])


        return video_list

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//div[@id="divPrice"]'
                                     '/text()')
        if price:
            return price[0].split('-')[0]

    def _price_currency(self):
        return 'CAD'

    def _in_stores(self):
        return 1

    def _site_online(self):
        not_site_online = self._find_between(html.tostring(self.tree_html), 'var isInStoreOnly = ', ';')
        return 0 if not_site_online == 'true' else 1

    def _site_online_out_of_stock(self):
        out_of_stock = self.tree_html.xpath('//meta[@itemprop="availability"]/@content')[0]
        if 'InStock' in out_of_stock:
           return 0
        return 1

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return self.tree_html.xpath('//div[@id="breadCrumbs"]//a/text()')

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "description": _description,
        "long_description": _long_description,
        "sku": _sku,
        "upc": _upc,
        "brand": _brand,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : SELLERS
        "price": _price,
        "price_currency": _price_currency,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
    }
