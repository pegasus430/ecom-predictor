# -*- coding: utf-8 -*-
#!/usr/bin/python

import re
import json
import urlparse
import traceback

from lxml import html
from extract_data import Scraper


class HomedepotcaScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.homedepot.ca/en/home/<product-name>"

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json?passkey=i2qqfxgqsb1f86aabybalrdvf' \
                 '&apiversion=5.5&displaycode=1998-en_ca&resource.q0=products&filter.q0=id:eq:{0}' \
                 '&stats.q0=questions,reviews'

    API_URL = 'https://www.homedepot.ca/homedepotcacommercewebservices/v2/' \
              'homedepotca/products/{0}/localized/9999'

    IMAGE_URL = 'http://images.homedepot.ca/is/image/homedepotcanada/{0}_image_set?req=set,json,UTF-8' \
                '&$pipGallery$&labelkey=label&handler=s7classics7sdkJSONResponse'

    SWF_STREAM_URL = 'https://secure.brightcove.com/services/viewer/federated_f9?&playerID={player_id}&' \
                     'isVid=true&isUI=true&dynamicStreaming=true&%40videoPlayer={video_id}&autoStart=true'

    def select_browser_agents_randomly(self):
        return 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots) Chrome'

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.images = []
        self.is_images_checked = False

    def check_url_format(self):
        m = re.match(r"https?://www.homedepot.ca/en/home/.*", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()
        self.product_info = self._fetch_product_info()

    def not_a_product(self):
        self.product_json = self._product_json()

        if not self.product_info:
            return True

        return False

    def _fetch_product_info(self):
        product_id = self._product_id()

        try:
            return self._request(self.API_URL.format(product_id)).json()
        except Exception as e:
            print('Error in Fetching Product Info: {}'.format(e))

    def _product_json(self):
        product_info = self._find_between(html.tostring(self.tree_html), 'AdobeTracking =', ';').strip()
        try:
            return json.loads(product_info)
        except:
            print traceback.format_exc()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        try:
            product_id = self.product_json['product']['productId']
        except:
            product_id = self.tree_html.xpath('//a[@id="jsProductData"]/@data-base-code')
            if product_id:
                product_id = product_id[0].strip()

        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        try:
            product_name = self.product_json['pageData']['pageName']
        except:
            product_name = None

        return product_name

    def _product_title(self):
        product_title = self.tree_html.xpath("//title/text()")
        if product_title:
            try:
                product_title = product_title[0].split('|')[0].strip()
            except:
                product_title = self._product_name()

        return product_title

    def _title_seo(self):
        return self.tree_html.xpath("//meta[@property='og:title']/@content")[0].strip()

    def _description(self):
        short_description = self.tree_html.xpath(
            "//div[contains(@class, 'product-accordion-content')]"
            "//div[@itemprop='description']/text()"
        )
        short_description = ''.join(short_description)

        return self._clean_text(short_description)

    def _long_description(self):
        long_description = self.tree_html.xpath(
            "//div[contains(@class, 'product-accordion-content')]//ul")

        if long_description:
            long_description = self._clean_text(html.tostring(long_description[0]))

        return long_description

    def _specs(self):
        specs = {}
        spec_groups = self.tree_html.xpath('//div[@class="product-spec"]//tbody//tr')
        for spec_group in spec_groups:
            infos = spec_group.xpath('.//td/text()')
            if len(infos) >= 4:
                specs[infos[0]] = infos[1]
                specs[infos[2]] = infos[3]

        return specs if specs else None

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if self.is_images_checked:
            return self.images

        self.is_images_checked = True
        image_list = None
        product_id = self._product_id()

        try:
            images_info = self._request(self.IMAGE_URL.format(product_id)).content
            images_json = json.loads(self._find_between(images_info, 's7classics7sdkJSONResponse(', ',"");'))
            image_list = images_json['set']['item']
        except Exception as e:
            print('Error while parsing Image Urls: {}'.format(traceback.format_exc(e)))

        if not image_list:
            return None

        image_base_url = 'https://images.homedepot.ca/is/image/'
        if isinstance(image_list, dict):
            try:
                self.images.append(urlparse.urljoin(image_base_url, image_list['i']['n'].strip()))
            except Exception as e:
                print(traceback.format_exc(e))
        elif isinstance(image_list, list):
            for image in image_list:
                try:
                    self.images.append(urlparse.urljoin(image_base_url, image['i']['n'].strip()))
                except Exception as e:
                    print(traceback.format_exc(e))

        self.images = filter(None, self.images)

        return self.images

    def _video_urls(self):
        # swf stream url, checked with standalone flash player
        # http://www.adobe.com/support/flashplayer/debug_downloads.html (projector)
        video_urls = []
        player_id = re.search(r'id:\ \'(.*?)\'', self.page_raw_text)
        video_data = self.tree_html.xpath(
            '//a[@class="video-watch"]/@data-video-id'
        )
        if player_id and video_data:
            for video_id in video_data:
                video_urls.append(
                    self.SWF_STREAM_URL.format(
                        player_id=player_id.group(1),
                        video_id=video_id
                    )
                )
        return video_urls if video_urls else None


    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        bv_id = self.tree_html.xpath("//div[@id='bazaar-voice-vars']/@data-product-id")

        if bv_id:
            review_url = self.REVIEW_URL.format(bv_id[0].strip())
            return super(HomedepotcaScraper, self)._reviews(review_url = review_url)


    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        try:
            price = self.product_info['optimizedPrice']['displayPrice']['formattedValue']
        except:
            price = None

        return price

    def _price_amount(self):
        try:
            price = float(self.product_info['optimizedPrice']['displayPrice']['value'])
        except:
            price = None

        return price

    def _price_currency(self):
        return 'CAD'

    def _in_stores(self):
        return int('select store for availability' in
                   self.product_info.get('optimizedPrice', {}).get('availabilityMsg', '').lower())

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return int(self.product_info.get('onlineStock', {}).get('stockLevel', 0) == 0)

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath(
            "//ol[@class='breadcrumb']//li//a/text()"
        )

        return categories[1:] if categories else None

    def _brand(self):
        brand = self.tree_html.xpath(
            "//h3[@class='pip-product-brand']//span[@itemprop='manufacturer']/text()"
        )
        if brand:
            return self._clean_text(brand[0])

    def _sku(self):
        sku_info = self.tree_html.xpath(
            "//div[@class='product-info']//div/text()"
        )
        sku_info = self._clean_text(''.join(sku_info))
        sku = re.search('SKU: (\d+)', sku_info)

        if sku:
            return sku.group(1)

        sku_info = self.tree_html.xpath(
            "//div[@class='product-models']/text()"
        )
        sku = re.search('SKU # (\d+)', self._clean_text(''.join(sku_info)))

        return sku.group(1) if sku else None

    def _model(self):
        model_info = self.tree_html.xpath(
            "//div[@class='product-overview']//h2//span[@class='sub']/text()"
        )
        model_info = self._clean_text(''.join(model_info))
        model = re.search(r'Model # (.*?)Store', model_info)
        if model:
            return model.group(1)

        model = re.search('Model: (.*?) ', html.tostring(self.tree_html), re.DOTALL)
        if model:
            return model.group(1)

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "description" : _description,
        "long_description" : _long_description,
        "sku" : _sku,
        "model": _model,
        "specs" : _specs,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "video_urls": _video_urls,

        # CONTAINER : REVIEWS
        "reviews" : _reviews,

        # CONTAINER : SELLERS
        "price" : _price,
        "price_amount" : _price_amount,
        "price_currency" : _price_currency,
        "in_stores" : _in_stores,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
