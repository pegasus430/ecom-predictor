#!/usr/bin/python

import traceback
import re, json, requests
from extract_data import Scraper


class SearsScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http://www.sears.com/.*"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.product_info_json = {}
        self.variant_info_jsons = {}
        self.price_json = []

    def check_url_format(self):
        if re.match(r"^http://www\.sears\.com/.*", self.product_page_url):
            return True
        return False

    def _extract_product_info_json(self, product_id=None):
        if product_id is None:
            product_id = re.search('p-(.*)', self.product_page_url).group(1)
            json_info_container = self.product_info_json
        else:
            json_info_container = self.variant_info_jsons.setdefault(product_id, {})

        if not json_info_container:
            for i in range(3):
                try:
                    with requests.Session() as s:
                        url = 'http://www.sears.com/content/pdp/config/products/v1/products/' + product_id + '?site=sears'
                        h = self._request(url, session=s).json()
                        json_info_container = h.get('data')
                        self.product_info_json = json_info_container
                except:
                    print traceback.format_exc()

        return json_info_container

    def not_a_product(self):
        self._extract_product_info_json()

        if self.product_info_json['productstatus']['isDeleted']:
            return True

        return False

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_info_json['product']['id']

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.product_info_json['product']['name']

    def _product_title(self):
        return self.tree_html.xpath('//div[@class="product-content"]/h1/text()')[0]

    def _title_seo(self):
        return self.product_info_json['product']['seo']['title']

    def _model(self):
        if self.product_info_json.get('offer'):
            return self.product_info_json['offer']['modelNo']
        else:
            return self.product_info_json['product']['mfr']['modelNo']

    def _upc(self):
        if self.product_info_json.get('offer'):
            return self.product_info_json['offer']['altIds']['upc']

    def _specs(self):
        specs = {}

        for group in self.product_info_json['product']['specs']:
            for attr in group['attrs']:
                specs[attr['name']] = attr['value']

        if specs:
            return specs

    def _features(self):
        features = []

        if self.product_info_json['product'].get('curatedContents'):
            for g in self.product_info_json['product']['curatedContents']['curatedGrp']:
                for c in g['content']:
                    if c['type'] == 'copy':
                        features.append(c['name'] + ': ' + c['data'])

        if features:
            return features

    def _description(self):
        return self.product_info_json['product']['desc'][0]['val']

    def _long_description(self):
        return self.product_info_json['product']['desc'][0]['val']

    def _variants(self):
        variants = []

        if self.product_info_json.get('attributes'):
            for variant in self.product_info_json['attributes']['variants']:
                v = {
                    'in_stock': variant['isAvailable'],
                    'price': self._price_amount(),
                    'properties': {},
                    'selected': False
                }

                for attribute in variant['attributes']:
                    v['properties'][attribute['name']] = attribute['value']

                variants.append(v)

        else:
            for swatch in self.product_info_json['offer']['assocs']['linkedSwatch']:

                variant = {
                    # 'product_id': swatch['id'],
                    'price': self._price_amount(),
                    'properties': {},
                    'selected': False,
                    # 'url': 'http://www.sears.com' + swatch['url'] + '/p-' + swatch['id']
                }

                info = self._extract_product_info_json(swatch['id'])

                variant['in_stock'] = (
                    info['offerstatus']['isAvailable'] if info.get('offerstatus') else
                    (
                        any(info['offermapping']['fulfillment'].values()) if
                        info.get('offermapping', {}).get('fulfillment') else False
                    )
                )

                for spec in info['product']['specs']:
                    if 'color' in spec['grpName'].lower():
                        for attr in spec['attrs']:
                            if attr['name'].lower().startswith('color'):
                                variant['properties']['color'] = attr['val']
                                break
                        break

                variants.append(variant)

        if variants:
            return variants

    def _swatches(self):
        swatches = []

        if not self.product_info_json.get('attributes'):
            return

        for attribute in self.product_info_json['attributes']['attributes']:
            if attribute['name'] == 'Color':
                for value in attribute['values']:
                    s = {
                        'color': value['name'],
                        'hero': 1,
                        'hero_image': value['primaryImage']['src'],
                        'swatch_name': 'color',
                        'thumb': 1,
                        'thumb_image': value['swatchImage']['src']
                    }

                    swatches.append(s)

        if swatches:
            return swatches

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        images = []

        for group in self.product_info_json['product']['assets']['imgs']:
            for image in group['vals']:
                images.append(image['src'])

        if images:
            return images

    def _video_urls(self):
        videos = []

        for video in self.product_info_json['product']['assets'].get('videos', []):
            videos.append(video['link']['attrs']['href'])

        if videos:
            return videos

    def _pdf_urls(self):
        pdfs = []

        for pdf in self.product_info_json['product']['assets'].get('attachments', []):
            pdfs.append(pdf['link']['attrs']['href'])

        if pdfs:
            return pdfs

    def _webcollage(self):
        atags = self.tree_html.xpath("//a[contains(@href, 'webcollage.net/')]")

        if len(atags) > 0:
            return 1

        return 0

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self):
        reviews = []

        i = 5

        for value in self.tree_html.xpath('//ul[@class="ratings-graph"]/li/a/text()'):
            reviews.append([i, re.match('\((\d+)\)', value).group(1)])
            i -= 1

        if reviews:
            return reviews

    def _review_count(self):
        return int(self.tree_html.xpath('//span[@itemprop="reviewCount"]/text()')[0])

    def _average_review(self):
        return float(self.tree_html.xpath('//meta[@itemprop="ratingValue"]/@content')[0])

    def _max_review(self):
        return int(self.tree_html.xpath('//meta[@itemprop="bestRating"]/@content')[0])

    def _min_review(self):
        return int(self.tree_html.xpath('//meta[@itemprop="worstRating"]/@content')[0])

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        self._extract_product_info_json()
        price = 0
        if 'uid' in self.product_info_json['productstatus']:
            uid = self.product_info_json['productstatus']['uid']
            product_id = self.product_info_json['product']['id']
            price_url = "http://www.sears.com/content/pdp/v1/products/" + product_id + "/variations/" + uid + "/ranked-sellers?site=sears"
            data = self._request(price_url).json()
            price = data['data']['sellers']['groups'][0]['offers'][0]['totalPrice']

        if price == 0:
            ssin = self.product_info_json['productstatus']['ssin']
            headers = {'AuthID': 'aA0NvvAIrVJY0vXTc99mQQ=='}
            price_url = 'http://www.sears.com/content/pdp/products/pricing/v2/get/price/display/json?ssin={}&priceMatch=Y&memberType=G&urgencyDeal=Y&site=SEARS'.format(
                ssin)
            price_data = self._request(price_url, headers=headers).json()
            price = price_data['priceDisplay']['response'][0]['prices']['finalPrice']['min']

        return '$' + str(price) if price else None

    def _marketplace(self):
        return 0

    def _home_delivery(self):
        if self.price_json.get('attributes'):
            if self.price_json['attributes']['variants'][0].get('isDeliveryAvail'):
                return 1
            return 0
        if self.price_json['data']['Offer']['offermapping']['fulfillment']['delivery']:
            return 1
        return 0

    def _in_stores(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if not self._site_online():
            return None

        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        return map(lambda c: c['name'], self.product_info_json['productmapping']['primaryWebPath'])

    def _brand(self):
        if self.price_json.get('offer'):
            return self.price_json['data']['Offer']['offer']['brandName']
        else:
            return self.product_info_json['product']['brand']['name']

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################
    # clean text inside html tags - remove html entities, trim spaces


    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "product_title" : _product_title,
        "title_seo" : _title_seo,
        "specs" : _specs,
        "features" : _features,
        "description" : _description,
        "model" : _model,
        "long_description" : _long_description,
        "variants" : _variants,
        "swatches" : _swatches,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "pdf_urls" : _pdf_urls,
        "video_urls" : _video_urls,
        "webcollage" : _webcollage,

        # CONTAINER : SELLERS
        "price" : _price,
        "marketplace": _marketplace,
        "home_delivery" : _home_delivery,
        "in_stores" : _in_stores,
        "site_online" : _site_online,
        "site_online_out_of_stock" : _site_online_out_of_stock,

         # CONTAINER : REVIEWS
        "review_count" : _review_count,
        "average_review" : _average_review,
        "max_review" : _max_review,
        "min_review" : _min_review,
        "reviews" : _reviews,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
        }
