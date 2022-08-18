#!/usr/bin/python

import re
import requests
import urlparse
import traceback

from lxml import html
from extract_data import Scraper

from spiders_shared_code.homedepot_variants import HomeDepotVariants


class HomeDepotScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.homedepot.com/(p or s)/(<product-name>/)<product-id>"

    REVIEW_URL = "http://homedepot.ugc.bazaarvoice.com/1999aa/{0}/reviews.djs?format=embeddedhtml"

    QUESTIONS_URL = 'https://homedepot.ugc.bazaarvoice.com/answers/1999aa/product/{product_id}/' \
                    'questions.djs?format=embeddedhtml&page={page}'

    ITEMS_URL = "http://www.homedepot.com/p/svcs/frontEndModel/{prod_id}"

    STORE_URL = "http://www.homedepot.com/l/Union-Vauxhall/NJ/Vauxhall/07088/915"

    ITEM_IRG_URL = "https://www.homedepot.com/p/svcs/getProductIrgData?itemId={prod_id}&irgCount=3"

    STORE_COOKIE = "C4%3D915%2BUnion%252FVauxhall%20-%20Vauxhall%2C%20NJ%2B%3A%3BC4_EXP" \
                   "%3D1536944608%3A%3BC24%3D07088%3A%3BC24_EXP%3D1536944608%3A%3BC34%3" \
                   "D32.0%3A%3BC34_EXP%3D1505495014%3A%3BC39%3D1%3B7%3A00-20%3A00%3B2%3" \
                   "B6%3A00-22%3A00%3B3%3B6%3A00-22%3A00%3B4%3B6%3A00-22%3A00%3B5%3B6%3" \
                   "A00-22%3A00%3B6%3B6%3A00-22%3A00%3B7%3B6%3A00-22%3A00%3A%3BC39_EXP%" \
                   "3D1505412208"

    THREESIXTY_URL = "https://www.thdstatic.com/spin/{sid}/{id}/{fid}.spin"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.product_json = {}
        self.product_irg_json = {}
        self.variants_data = []
        self.hdv = HomeDepotVariants()

    def _extract_page_tree(self):
        with requests.Session() as session:
            page_html = self._get_page(session)
            self.tree_html = html.fromstring(page_html)
            product_json = self._extract_product_json(session)
            self.product_json = product_json
            self._extract_product_irg_json(session)
            self._get_variants_data(session)

    def check_url_format(self):
        m = re.match(r"https?://www.homedepot.com/(p|s)/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        try:
            if not self.product_json:
                return True
            if self._no_longer_available():
                return False
            itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')
            if itemtype and itemtype[0].strip() == 'product':
                return False
        except Exception as e:
            if self.lh:
                self.lh.add_list_log('errors', str(e))

            print traceback.format_exc()

    def _pre_scrape(self):
        self.hdv.setupCH(self.tree_html)
        self._extract_questions_content()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _get_page(self, session, product_url=None):
        session.cookies.set('THD_PERSIST', self.STORE_COOKIE, domain='.homedepot.com', path='/')
        r = self._request(
            product_url or self.product_page_url,
            session=session,
            log_status_code=True
        )
        if r.status_code != 200:
            self.ERROR_RESPONSE['failure_type'] = r.status_code
            self.is_timeout = True
            return
        return r.content

    def _get_variants_data(self, session):
        color_option_ids = self.tree_html.xpath(
            '//div[contains(@class, "product_sku_Overlay_ColorSwatch")]//li/@data-itemid'
        )
        for color_option_id in color_option_ids:
            tmp = {}
            if color_option_id == self._product_id():
                tmp['html'] = self.tree_html
            else:
                url = re.sub('/\d+', '/%s' % color_option_id, self.product_page_url)
                tmp['html'] = html.fromstring(self._get_page(session, product_url=url))
            available_options = tmp['html'].xpath(
                '//ul[contains(@class, "listOptions")]//a[@class="enabled"]/@data-itemid'
            )
            tmp['options'] = []
            if available_options:
                for option in available_options:
                    opt_data = {}
                    if option == self._product_id():
                        opt_data['selected'] = True
                        opt_data['json'] = self.product_json
                    else:
                        opt_data['selected'] = False
                        opt_data['json'] = self._extract_product_json(session, product_id=option)
                    tmp['options'].append(opt_data)
            else:
                opt_data = {}
                if color_option_id == self._product_id():
                    opt_data['selected'] = True
                    opt_data['json'] = self.product_json
                else:
                    opt_data['selected'] = False
                    opt_data['json'] = self._extract_product_json(session, product_id=color_option_id)
                tmp['options'].append(opt_data)
            self.variants_data.append(tmp)

    def _extract_product_json(self, session, product_id=None):
        try:
            r = self._request(
                self.ITEMS_URL.format(prod_id=product_id or self._product_id()),
                session = session
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print traceback.format_exc()
            raise Exception('Error getting product json: {}'.format(e))

    def _extract_product_irg_json(self, session):
        try:
            r = self._request(
                self.ITEM_IRG_URL.format(prod_id=self._product_id()),
                session = session
            )
            if r.status_code == 200:
                self.product_irg_json = r.json()
        except Exception as e:
            print traceback.format_exc()
            raise Exception('Error getting product irg json: {}'.format(e))

    def _product_id(self):
        product_id = self.tree_html.xpath('//h2[@class="product_details"]//span[@itemprop="productID"]/text()')

        if product_id:
            return product_id[0]

        return re.findall(r'\d+$', self.product_page_url)[0]

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        title = self.tree_html.xpath('//h1[@class="product-title__title"]/text()')
        return title[0] if title else None

    def _model(self):
        return self.product_json['primaryItemData']["info"]["modelNumber"]

    def _sku(self):
        return self.product_json.get('primaryItemData', {}).get("info", {}).get("specialOrderSKU")

    def _upc(self):
        return self.tree_html.xpath('//upc/text()')[0]

    def _features(self):
        features_td_list = self.tree_html.xpath('//table[contains(@class, "tablePod tableSplit")]//td')
        features_list = []

        for index, val in enumerate(features_td_list):
            if (index + 1) % 2 == 0 and features_td_list[index - 1].xpath(".//text()")[0].strip():
                features_list.append(features_td_list[index - 1].xpath(".//text()")[0].strip() + " " + features_td_list[index].xpath(".//text()")[0].strip())

        if features_list:
            return features_list

    def _remove_tags(self, html_string):
        html_string = re.sub('\s+', ' ', html_string).strip()
        return re.sub('<([^\s>]+)[^>]*>', r'<\1>', html_string)

    def _description(self):
        description_block = self.tree_html.xpath("//div[contains(@class, 'main_description')]")[0]
        short_description = ""

        for description_item in description_block:
            if description_item.tag == "ul":
                break

            short_description = short_description + html.tostring(description_item)

        short_description = self._remove_tags(short_description)

        if short_description:
            return short_description

    def _long_description(self):
        description_block = self.tree_html.xpath("//div[contains(@class, 'main_description')]")[0]
        long_description = ""
        long_description_start = False

        for description_item in description_block:
            if description_item.tag == "ul":
                long_description_start = True

            if long_description_start:
                long_description = long_description + html.tostring(description_item)

        long_description = self._remove_tags(long_description)

        if long_description:
            return long_description

    def _shelf_description(self):
        shelf_description = self.tree_html.xpath("//div[contains(@class, 'buybox__salient-points')]//ul")
        if shelf_description:
            shelf_description = self._clean_text(html.tostring(shelf_description[0]))
            return self._remove_tags(shelf_description)

    def _rich_content(self):
        return 1 if self.tree_html.xpath('//div[@id="rich-content-container"]') else 0

    def _specs(self):
        specs = {}
        nodes = self.tree_html.xpath("//div[@id='specsContainer']")
        get_value = lambda x: x[0].strip() if x else None
        for node in nodes:
            names, values = [], []
            for spec_node in node.xpath(".//div[contains(@class, 'specs__cell')]"):
                if spec_node.get('class', '').strip().endswith('--label'):
                    name = get_value(spec_node.xpath('./text()'))
                    names.append(name)
                elif spec_node.get('class', '').strip().endswith('specs__cell'):
                    value = get_value(spec_node.xpath('./text()'))
                    values.append(value)
            specs.update(
                dict(zip(names, values)))

        if specs:
            return specs

    def _swatches(self):
        return self.hdv.swatches()

    def _variants(self):
        return self.hdv.variants(self.variants_data)

    def _no_longer_available(self):
        discontinued = self.product_json.get('primaryItemData', {}).get('itemAvailability', {}).get('discontinuedItem')
        return int(discontinued)

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        media_list = self.product_json.get('primaryItemData', {}).get('media', {}).get('mediaList')
        image_list = []

        width_list = [int(media_item.get('width', 0)) for media_item in media_list]
        if width_list:
            max_width = max(width_list)
            for media_item in media_list:
                if media_item["mediaType"].startswith("IMAGE") and int(media_item["width"]) == max_width:
                    image_list.append(media_item["location"])

        return image_list if image_list else None

    def _in_page_360_image_urls(self):
        threesixty = self._json_search('name', '360 Images', 'value', self.product_json)
        image_urls = [
            self.THREESIXTY_URL.format(
                sid=x.split('_')[0][-2:],
                id=x.split('_')[0],
                fid=x.replace('_', '_S'))
            for x in threesixty
        ]
        return image_urls if image_urls else None

    def _video_urls(self):
        media_list = self.product_json.get('primaryItemData', {}).get('media', {}).get('mediaList')
        video_list = []

        for media_item in media_list:
            if "video" in media_item:
                video_list.append(media_item["video"])

        if video_list:
            return video_list

    def _pdf_urls(self):
        pdf_urls = self.tree_html.xpath(
            '//div[@id="moreinfo_wrapper"]'
            '//ul[contains(@class, "list")]//a[@class="list__link"]/@href'
        )
        return [urlparse.urljoin(self.product_page_url, pdf_url) for pdf_url in pdf_urls] if pdf_urls else None

    def _document_names(self):
        document_names = self.tree_html.xpath(
            '//div[@id="moreinfo_wrapper"]'
            '//ul[contains(@class, "list")]//a[@class="list__link"]/text()'
        )
        return document_names if document_names else None

    def _collection_count(self):
        return len(self.product_irg_json.get('IRGITEMIDS', {}).get('COLLECTION', []))

    def _accessories_count(self):
        return len(self.product_irg_json.get('IRGITEMIDS', {}).get('ACCESSORY', []))

    def _coordinating_items_count(self):
        return len(self.product_irg_json.get('IRGITEMIDS', {}).get('COOR_ITEMS', []))

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        return float(self.tree_html.xpath('//input[@id="ciItemPrice"]/@value')[0])

    def _temp_price_cut(self):
        return self.product_json['primaryItemData']["itemExtension"]["localStoreSku"]["pricing"]["itemOnSale"]

    def _in_stores(self):
        in_stores = self.product_json.get('primaryItemData', {}).get("storeSkus", [{}])[0]\
                    .get("storeAvailability", {}).get("availableInLocalStore")
        return int(in_stores)

    def _site_online(self):
        if self.product_json['primaryItemData']["info"]["onlineStatus"]:
            return 1
        return 0

    def _site_online_out_of_stock(self):
        for message in self.product_json['primaryItemData']["storeSkus"][0]["storeAvailability"]["itemAvilabilityMessages"]:
            if message["messageValue"] == u'Out Of Stock Online':
                return 1
        return 0

    def _in_stores_out_of_stock(self):
        return 1 - self._in_stores()

    def _marketplace(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        for dimension in self.product_json.get('primaryItemData', {}).get('dimensions'):
            if dimension.get('isDefaultBreadCrumb'):
                return [a['name'] for a in dimension['ancestors']]

    def _brand(self):
        return self.product_json.get('primaryItemData', {}).get('info', {}).get('brandName')

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        text = re.sub("[\n\t]", "", text)
        text = re.sub(r" +", " ", text)
        return text.strip()

    def _json_search(self, needle, search_val, search_key, haystack):
        found = []

        if isinstance(haystack, dict):
            if needle in haystack.keys() and haystack[needle] == search_val:
                if search_key in haystack.keys():
                    found.append(haystack[search_key])
    
            elif len(haystack.keys()) > 0:
                for key in haystack.keys():
                    result = self._json_search(needle, search_val, search_key, haystack[key])
                    found.extend(result)
    
        elif isinstance(haystack, list):
            for node in haystack:
                result = self._json_search(needle, search_val, search_key, node)
                found.extend(result)
    
        return found

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id" : _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name" : _product_name,
        "model" : _model,
        "upc" : _upc,
        "sku" : _sku,
        "features" : _features,
        "description" : _description,
        "long_description" : _long_description,
        "shelf_description": _shelf_description,
        "specs": _specs,
        "swatches" : _swatches,
        "variants" : _variants,
        "no_longer_available" : _no_longer_available,
        "rich_content": _rich_content,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls" : _image_urls,
        "in_page_360_image_urls" : _in_page_360_image_urls,
        "video_urls" : _video_urls,
        "pdf_urls" : _pdf_urls,
        "collection_count" : _collection_count,
        "accessories_count" : _accessories_count,
        "coordinating_items_count" : _coordinating_items_count,
        "document_names" : _document_names,

        # CONTAINER : SELLERS
        "price_amount" : _price_amount,
        "temp_price_cut" : _temp_price_cut,
        "in_stores" : _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace" : _marketplace,

        # CONTAINER : CLASSIFICATION
        "categories" : _categories,
        "brand" : _brand,
    }
