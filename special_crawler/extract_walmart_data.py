#!/usr/bin/python

import io
import re
import sys
import json
import random
import requests
import urlparse
import traceback
from PIL import Image
from lxml import html, etree
from HTMLParser import HTMLParser
import spiders_shared_code.canonicalize_url
from extract_data import Scraper, deep_search, cached
from spiders_shared_code.walmart_variants import WalmartVariants
from requests.exceptions import ProxyError, ConnectionError, TooManyRedirects


class WalmartScraper(Scraper):

    """Implements methods that each extract an individual piece of data for walmart.com
        Attributes:
            product_page_url (inherited): the URL for the product page being scraped
        Static attributes:
            DATA_TYPES (dict):
            DATA_TYPES_SPECIAL (dict):  structures containing the supported data types to be extracted as keys
                                        and the methods that implement them as values

            INVALID_URL_MESSAGE: string that will be used in the "InvalidUsage" error message,
                                 should contain information on what the expected format for the
                                 input URL is.

            BASE_URL_REQ_WEBCOLLAGE (string):
            BASE_URL_PDFREQ_WEBCOLLAGE (string):
            BASE_URL_REVIEWSREQ (string):   strings containing necessary hardcoded URLs for extracting walmart
                                            videos, pdfs and reviews
    """

    # base URL for request containing video URL from webcollage
    BASE_URL_VIDEOREQ_WEBCOLLAGE = "http://json.webcollage.net/apps/json/walmart?callback=jsonCallback&environment-id=live&cpi="
    # base URL for request containing video URL from webcollage
    BASE_URL_VIDEOREQ_WEBCOLLAGE_NEW = "http://www.walmart-content.com/product/idml/video/%s/WebcollageVideos"
    # base URL for request containing video URL from sellpoints
    BASE_URL_VIDEOREQ_SELLPOINTS = "http://www.walmart.com/product/idml/video/%s/SellPointsVideos"
    # base URL for request containing video URL from sellpoints
    BASE_URL_VIDEOREQ_SELLPOINTS_NEW = "http://www.walmart-content.com/product/idml/video/%s/SellPointsVideos"
    # base URL for request containing pdf URL from webcollage
    BASE_URL_PDFREQ_WEBCOLLAGE = "http://content.webcollage.net/walmart/smart-button?ignore-jsp=true&ird=true&channel-product-id="
    # base URL for request for product reviews - formatted string
    BASE_URL_REVIEWSREQ = 'http://walmart.ugc.bazaarvoice.com/1336a/%20{0}/reviews.djs?format=embeddedhtml'
    # base URL for product API
    BASE_URL_PRODUCT_API = "http://www.walmart.com/product/api/{0}"
    # base URL for electrode API
    BASE_URL_ELECTRODE_API = "https://www.walmart.com/product/electrode/api/state/content/{0}"
    # base URL for terra firma API
    BASE_URL_TERRA_FIRMA_API = "https://www.walmart.com/terra-firma/item/{0}"

    WALMART_SELLER_ID = 'F55CDC31AB754BB68FE0B39041159D63'

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://(www.)walmart.com/.*/[/<optional-part-of-product-name>]/<product_id>"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.additional_requests = False
        if kwargs.get('additional_requests'):
            self.additional_requests = kwargs.get('additional_requests') in ['1', 1]

        self.get_image_dimensions = True
        if kwargs.get('get_image_dimensions'):
            self.get_image_dimensions = kwargs.get('get_image_dimensions') in ['1', 1]

        # image fields
        self.image_urls = None
        self.image_res = None
        self.image_dimensions = None
        self.zoom_image_dimensions = None
        self.extracted_image_urls = False

        # whether electrode api json has been extracted
        self.extracted_electrode_json = False
        self.electrode_json = None

        # whether terra firma api json has been extracted
        self.extracted_terra_firma = False
        self.terra_firma = {}

        self.temp_price_cut = 0
        self.temporary_unavailable = 0

        # whether it's the new layout
        self.is_alternative = False

        self.is_bundle = False
        self.failure_type = None

        # offers and variant offers
        self.offers = []
        self.variant_offers = []

        # javascript function found in a script tag
        # containing various info on the product.
        # Currently used for seller info (but useful for others as well)
        self.extracted_product_info_jsons = False
        self.product_info_json = {}
        self.product_info_json_for_description = {}
        self.product_choice_info_json = None
        self.product_api_json = None
        self.key_fields_list = ["upc", "price", "description", "long_description"]

        self.is_bundle_product = False

        self.wv = WalmartVariants()

        self.proxies_enabled = True
        self.use_electrode_api = False

        if self.proxies_enabled and not self.use_electrode_api:
            self._set_proxy()

    def _request(self, url, log_status_code = False):
        if 'walmart.com' in url:
            return super(WalmartScraper, self)._request(url, log_status_code = log_status_code, use_proxies = True)
        else:
            return super(WalmartScraper, self)._request(url, log_status_code = log_status_code, use_proxies = False) 

    @cached
    def _extract_page_tree(self):
        # request https instead of http
        if re.match('http://', self.product_page_url):
            self.product_page_url = 'https://' + re.match('http://(.+)', self.product_page_url).group(1)

        for i in range(5):

            # Reset error fields

            self.is_timeout = False

            self.ERROR_RESPONSE['failure_type'] = None

            if self.lh:
                self.lh.add_log('status_code', None)

            try:
                if self.use_electrode_api:
                    electrode_url = self.BASE_URL_ELECTRODE_API.format(self._product_id())
                    resp = self._request(electrode_url, log_status_code = True)

                    if resp.status_code != 200:
                        continue

                    self.product_info_json = resp.json()

                    selected_product_id = self.product_info_json['productBasicInfo']['selectedProductId']
                    self.selected_product = self.product_info_json['product']['products'][selected_product_id]
                    self.is_alternative = True

                    return

                try:
                    resp = self._request(self.product_page_url, log_status_code = True)
                except TooManyRedirects:
                    self.ERROR_RESPONSE['failure_type'] = '404'
                    break

                prod_id = self.product_page_url.split('?')[0].split('/')[-1]
                redirected_prod_id = resp.url.split('?')[0].split('/')[-1]

                if prod_id != redirected_prod_id:
                    self.is_timeout = True
                    self.ERROR_RESPONSE['failure_type'] = 'Redirect'
                    return

                if resp.status_code != 200:
                    print 'Got response %s for %s with headers %s' % (resp.status_code, self.product_page_url, resp.headers)
                    self.ERROR_RESPONSE['failure_type'] = resp.status_code

                    if resp.status_code == 520:
                        # If response is 520, consider that 'temporarily unavailable'
                        self.temporary_unavailable = 1

                    # Retry some statuses
                    elif resp.status_code in [320, 403]:
                        continue
                    else:
                        break

                try:
                    # replace NULL characters
                    contents = self._clean_null(resp.text)
                    self.page_raw_text = contents
                    self.tree_html = html.fromstring(contents.decode('utf8'))
                except UnicodeError, e:
                    # if string was not utf8, don't deocde it
                    print 'Error decoding', self.product_page_url, e

                    # replace NULL characters
                    contents = self._clean_null(resp.text)
                    self.page_raw_text = contents
                    self.tree_html = html.fromstring(contents)

                try:
                    self._extract_product_info_json(force=True)
                except Exception as e:
                    print 'Error extracting product info json for %s: %s %s' % \
                        (self.product_page_url, type(e), e)

                # Retry some failure types
                try:
                    self._failure_type()
                    if self.failure_type in ['No product name']:
                        print 'GOT FAILURE TYPE %s for %s' % (self.failure_type, \
                            self.product_page_url)
                        self.is_timeout = True
                        self.ERROR_RESPONSE['failure_type'] = self.failure_type
                        continue
                except Exception, e:
                    print 'Error getting failure type', self.product_page_url, e
                    continue

                return

            except ProxyError, e:
                if self.lh:
                    self.lh.add_list_log('errors', str(e))

                self.is_timeout = True
                self.ERROR_RESPONSE['failure_type'] = 'proxy'
                return

            except ConnectionError, e:
                if self.lh:
                    self.lh.add_list_log('errors', str(e))

                if 'Max retries exceeded' in str(e):
                    self.is_timeout = True
                    self.ERROR_RESPONSE['failure_type'] = 'max_retries'
                    return

            except Exception, e:
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

        self.is_timeout = True

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.walmart(url)

    def check_url_format(self):
        if re.search('walmart.com/col', self.product_page_url):
            return False
        m = re.match("https?://(www\.)?walmart\.com(/.*)?/[0-9]+(\?.*)?", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self._version() == 'electrode':
            return False

        try:
            self.wv.setupCH(self.tree_html)
        except:
            pass

        try:
            self._failure_type()
        except Exception, e:
            print 'Error getting failure type', self.product_page_url, e
            return True

        if self.failure_type:
            self.ERROR_RESPONSE["failure_type"] = self.failure_type

            return True

        self.offers = self._get_offers()
        self.variant_offers = self._get_offers(False)

        return False

    def _pre_scrape(self):
        self._extract_webcollage_contents()

    def _filter_key_fields(self, field_name, value=None):
        if value:
            return value

        if self.product_api_json:
            try:
                if field_name in self.key_fields_list:
                    if field_name == "upc":
                        return self.product_api_json["product"]["upc"] if self.product_api_json["product"]["upc"] else self.product_api_json["product"]["wupc"]
                    if field_name == "price":
                        return self.product_api_json["product"]["buyingOptions"]["price"]["displayPrice"]
                    if field_name == "description":
                        return self.product_api_json["product"]["mediumDescription"]
                    if field_name == "long_description":
                        return self.product_api_json["product"]["longDescription"]
            except Exception, e:
                print "Error (Walmart - _filter_key_fields)" + str(e)

        return None

    def _product_id(self):
        """Extracts product id of walmart product from its URL
        Returns:
            string containing only product id
        """
        if self._version() == 'electrode':
            url = self.product_page_url.split('?')[0]
            return re.search('(\d+)$', url).group(1)
        elif self._version() == "Walmart v1":
            product_id = self._canonical_link().split('/')[-1]
            return product_id
        elif self._version() == "Walmart v2":
            product_id = self._canonical_link().split('/')[-1]
            return product_id

    def _video_urls(self):
        video_urls = []

        videos = deep_search('videos', self.product_info_json_for_description)

        if videos:
            for video in videos[0]:
                large = video.get('versions', {}).get('LARGE') or video.get('versions', {}).get('large')
                if large:
                    video_urls.append(re.sub('^//', '', large))

        if video_urls:
            return video_urls

    def _flixmedia(self):
        if "media.flix" in etree.tostring(self.tree_html):
            return 1
        else:
            return 0

    def _rich_content(self):
        return self.rich_content

    def _pdf_urls(self):
        pdf_urls = []

        for v in self.product_info_json.get('product', {}).get('idmlMap', {}).values():
            for v2 in v.get('modules', {}).get('WebcollageDocuments', {}).values():
                docs = v2.get('values')[0][0].get('url', {}).get('values')
                if docs:
                    pdf_urls.append(docs[0])

        if pdf_urls:
            return pdf_urls

    def _best_seller_category(self):
        category = self.tree_html.xpath("//div[@class='ranking']//a/text()")
        return category[0] if category else None

    def _product_name(self):
        if self.is_alternative:
            product_name = self.selected_product.get('productAttributes', {}).get('productName')

            if not product_name:
                # this is backup in case selected_product is not selected properly
                for product in self.product_info_json.get('product', {}).get('products', {}).values():
                    product_name = product.get('productAttributes', {}).get('productName')
 
            if product_name:
                return re.sub('\s+', ' ', product_name) # remove extra spaces from product name

        try:
            # assume new design
            product_name_node = self.tree_html.xpath("//h1[contains(@class, 'product-name')]")

            if not product_name_node:
                # assume old design
                product_name_node = self.tree_html.xpath("//h1[contains(@class, 'productTitle')]")

            if not product_name_node:
                product_name_node = self.tree_html.xpath("//h1[@itemprop='name']/span")

            if not product_name_node:
                product_name_node = self.tree_html.xpath("//h1[contains(@class, 'prod-ProductTitle')]/div")

            if product_name_node:
                return product_name_node[0].text_content().strip()
        except Exception, e:
            print 'Error extracting product name', self.product_page_url, e

    def _site_version(self):
        if self.use_electrode_api:
            return 0
        elif self.is_alternative:
            return 2
        return 1

    # extract walmart no
    def _walmart_no(self):
        if self.is_alternative:
            return self.selected_product.get('productAttributes', {}).get('walmartItemNumber')

        if self._version() == "Walmart v2" and self.is_bundle_product:
            product_info_json = self._extract_product_info_json()
            return product_info_json["analyticsData"]["productId"]
        else:
            return self.tree_html.xpath("//tr[@class='js-product-specs-row']/td[text() = 'Walmart No.:']/following-sibling::td/text()")[0].strip()

    # extract meta tags exclude http-equiv
    def _meta_tags(self):
        meta_tags = [m.values() for m in self.tree_html.xpath('//meta[not(@http-equiv)]')]
        return [[self._clean_text(t) for t in m] for m in meta_tags]

    def _meta_tag_count(self):
        return len(self._meta_tags())

    # extract meta "brand" tag for a product from its product page tree
    # ! may throw exception if not found
    def _meta_brand_from_tree(self):
        """Extracts meta 'brand' tag for a walmart product
        Returns:
            string containing the tag's content, or None
        """
        if self.is_alternative:
            return self.selected_product.get('productAttributes', {}).get('brand')

        if self._version() == "Walmart v1":
            return self.tree_html.xpath("//meta[@itemprop='brand']/@content")[0]

        if self._version() == "Walmart v2":
            if self.is_bundle_product:
                product_info_json = self._extract_product_info_json()
                return product_info_json["analyticsData"]["brand"]
            else:
                return self.tree_html.xpath("//span[@itemprop='brand']/text()")[0]

    def _seller_ranking(self):
        ranking_list = self.tree_html.xpath("//div[@class='Grid-col item-ranks']//ol/li[@class='item-rank']/span[contains(@class, 'rank')]/text()")
        breadcrumb_list = self.tree_html.xpath("//div[@class='Grid-col item-ranks']//ol")
        seller_ranking = []

        for index, ranking in enumerate(ranking_list):
            category_name = ""

            for sub_category_name in breadcrumb_list[index].xpath("./li[@class='breadcrumb']/a/text()"):
                category_name = category_name + sub_category_name + " > "

            category_name = category_name[:-3]
            seller_ranking.append({"category": category_name, "ranking": int(ranking[1:].replace(",", ""))})

        if seller_ranking:
            return seller_ranking

    def _get_description_separator_index(self, description):
        product_name = self._product_name().split(',')[0]
        product_name_bold = '<b>' + product_name
        product_name_strong = '<strong>' + product_name

        has_product_name = False

        product_name_regex = '(<b>|<strong>)[^<]*(</b>|</strong>)[(<br>)\s":]*(</p>)?(<br>)*(<ul>|<li>)'

        if product_name_bold in description or product_name_strong in description \
            or re.search(product_name_regex, description, re.DOTALL):

            has_product_name = True

        possible_end_indexes = []

        for item in [product_name_bold, product_name_strong, '<h3>', '<section class="product-about']:
            if item in description:
                possible_end_indexes.append(description.find(item))

        for item in ['<dl>', '<ul>', '<li>']:
             if not has_product_name and item in description:
                possible_end_indexes.append(description.find(item))

        if not (product_name_bold in description or product_name_strong in description):
            match = re.search(product_name_regex, description, re.DOTALL)
            if match:
                possible_end_indexes.append(match.start())

        if possible_end_indexes:
            end_index = min(possible_end_indexes)
        else:
            end_index = None

        short_description = description[:end_index]

        while len(short_description) > 1000:
            if '<p>' in short_description:
                end_index = short_description.rfind('<p>')
                short_description = description[:end_index]
            else:
                break

        return end_index

    def _clean_description(self, description):
        description = self._clean_html( html.tostring(description))

        description = re.sub('^<div[^>]*>', '', description)
        description = re.sub('</div>$', '', description)

        description = re.sub('<a href.*?>(.*?)</a>', r'\1', description)
        description = re.sub(' style="color:\w+"', '', description)

        # recursively remove empty elements
        while True:
            old_description = description
            description = re.sub(r'<(\S+)[^>]*></\1?>', '', description)
            if description == old_description:
                break

        return description

    def _clean_alt_desc(self, description):
        if description:
            # remove links
            description = re.sub('<a href.*?>(.*?)</a>', r'\1', description)
            # remove attributes
            description = re.sub('(<\w+)[^>]*?(/?>)', r'\1\2', description)
            # remove div and span tags
            description = re.sub('</?div>|</?span>', '', description)
            # remove &nbsp;
            description = re.sub('&nbsp;', ' ', description)
            # unescape entities like &amp;
            description = HTMLParser().unescape(description)

            return description.strip()

    def _shelf_description(self):
        try:
            shelf_description_html = self.tree_html.xpath("//div[contains(@class,'ProductPage-short-description-body')]")

            if shelf_description_html:
                shelf_description = html.tostring(shelf_description_html[0])
                shelf_description = re.match('<div.*?>(.*)</div>', shelf_description, re.DOTALL).group(1)

                if shelf_description:
                    shelf_description = HTMLParser().unescape(shelf_description)
                    shelf_description = re.sub('<img[^>]+?>', '', shelf_description) # remove images
                    return self._clean_alt_desc(shelf_description)

            return self._clean_alt_desc(self.product_info_json_for_description.get('shortDescription'))
        except:
            print traceback.format_exc()

    def _short_description(self):
        desc = None

        product_short_description = deep_search('product_short_description', self.product_info_json_for_description)
        if product_short_description:
            desc = product_short_description[0].get('values')
            if desc:
                desc = self._clean_alt_desc(desc[0])

        if not desc:
            medium_desc = self.selected_product.get('productAttributes', {}).get('mediumDescription')

            # if medium_desc is not well formed, don't return it
            if medium_desc:
                try:
                    html.fromstring(medium_desc) 
                except lxml.etree.ParserError:
                    medium_desc = None

            desc = self._clean_alt_desc(medium_desc)

        if desc:
            return self._exclude_javascript_from_description(desc)

    def _long_description(self):
        desc = None

        for v in self.product_info_json_for_description.get('product', {}).get('idmlMap', {}).values():
            desc = v.get('modules', {}).get('LongDescription', {}).get('product_long_description', {}).get('values')
            if desc:
                desc = self._clean_alt_desc(desc[0])
                break

        if not desc:
            detailed_desc = self.selected_product.get('productAttributes', {}).get('detailedDescription')

            # if detailed_desc is not well formed, don't return it
            if detailed_desc:
                try:
                    html.fromstring(detailed_desc)
                except lxml.etree.ParserError:
                    detailed_desc = None

            if detailed_desc:
                desc = detailed_desc

        if desc:
            return self._exclude_javascript_from_description(desc)

    def _short_and_long_description(self):
        short_description = self._short_description()

        if short_description and short_description.endswith('...'):
            short_description = None

        long_description = self._long_description()

        if long_description and long_description.lower() == 'long description is not available':
            long_description = None

        if long_description and long_description == self._product_name():
            if short_description:
                short_description += ' ' + long_description
            else:
                short_description = long_description
            long_description = None

        if not short_description:
            short_description = long_description
            long_description = None

        if short_description:
            separator_index = self._get_description_separator_index(short_description)

            if separator_index and not long_description:
                long_description = short_description[separator_index:]
                short_description = short_description[:separator_index]

        return short_description, long_description

    def _short_description_wrapper(self):
        return self._short_and_long_description()[0]

    def _long_description_wrapper(self):
        return self._short_and_long_description()[1]

    def _set_variant_properties(self, variant, product_id, variants_map):
        variant['properties'] = {}

        for property_data in variants_map.values():
            variant_datas = property_data.get('variants', {}).values()

            for variant_data in variant_datas:
                property_name = variant_data.get('categoryId')

                if 'color' in property_name:
                    property_name = 'color'
                elif 'size' in property_name:
                    property_name = 'size'
                elif 'number_of_pieces' in property_name:
                    property_name = 'count'

                value = variant_data.get('name')

                if product_id in variant_data.get('products', []):
                    variant['properties'][property_name] = value

    def _variants(self):
        if self._no_longer_available():
            return None

        if self.is_alternative:
            products = self.product_info_json.get('product', {}).get('products', {})

            variants = []
            primary_product_id = self.product_info_json.get('product', {}).get('primaryProduct')

            try:
                variants_map = self.product_info_json.get('product', {}).get('variantCategoriesMap', {}).get(primary_product_id, {})
            except:
                variants_map = {}

            for product in products.values():
                variant = {}

                # get variant 'selected' status
                variant_id = product.get('usItemId')
                selected_id = self.selected_product.get('usItemId')
                variant['selected'] = selected_id == variant_id

                # get variant url
                url = urlparse.urljoin(self.product_page_url, '/ip/{}'.format(variant_id))
                variant['url'] = url

                # get variant price
                variant['price'] = self._get_alternative_price(product)

                # get variant properties
                product_id = product.get('productId')
                self._set_variant_properties(variant, product_id, variants_map)

                # get variant stock status
                variant['in_stock'] = any(self._is_in_stock(o) for o in self.offers
                                          if o.get('id') in product.get('offers', []))

                # only include if variant has properties
                if variant.get('properties'):
                    variants.append(variant)

            return variants if len(variants) > 1 else None

        return self.wv._variants()

    def _swatches(self):
        if self._no_longer_available():
            return None

        swatches = []

        for product in self.product_info_json.get('product', {}).get('variantCategoriesMap', {}).values():
            for attribute in product.values():
                if attribute.get('type') == 'SWATCH':
                    swatch_name = attribute['id']

                    if swatch_name == 'actual_color':
                        swatch_name = 'color'

                    for variant in attribute['variants'].values():
                        hero_image = variant['swatchImageUrl']
                        hero_image = [hero_image] if hero_image != '/static/img/no-image-sm.jpg' else []

                        swatch = {
                            swatch_name: variant['name'],
                            'hero_image': hero_image,
                            'hero': len(hero_image)
                        }

                        swatches.append(swatch)

        if swatches:
            return swatches

    def _swatch_image_missing(self):
        swatches = self._swatches()

        if swatches:
            for swatch in swatches:
                if not swatch['hero_image']:
                    return 1

            return 0

    def _bundle(self):
        return int(self.is_bundle)

    def _bundle_components(self):
        product_id_list = self.tree_html.xpath("//div[@class='bundle-see-more-container']//div[@class='clearfix greybar-body']/@id")
        product_id_list = [id.split("I")[1] for id in product_id_list]
        product_id_list = list(set(product_id_list))

        '''
        if product_id_list:
            bundle_component_list = []

            for id in product_id_list:
                try:
                    product_json = json.loads(self._request(self.BASE_URL_PRODUCT_API.format(id)).content)
                    bundle_component_list.append({"upc": product_json["analyticsData"]["upc"], "url": "http://www.walmart.com" + product_json["product"]["canonicalUrl"]})
                except:
                    continue

            if bundle_component_list:
                return bundle_component_list
        '''

        return None

    def _style(self):
        return self.wv._style()

    def _get_alternative_price(self, product, is_main = False):
        price = None

        if is_main:
            if self.is_bundle:
                meta_data = self.product_info_json.get('product', {}).get('choiceBundleMetaData', {})
                min_price = meta_data.get('minPrice', {}).get('price')
                max_price = meta_data.get('maxPrice', {}).get('price')
                if min_price and max_price:
                    return "${0} - ${1}".format(min_price, max_price)

            price_ranges = self.product_info_json.get('product', {}).get('priceRanges')

            if price_ranges:
                price_range = price_ranges.values()[0]
                min_price = price_range['minPrices'].get('CURRENT', {}).get('price')
                max_price = price_range['maxPrices'].get('CURRENT', {}).get('price')
                if min_price and max_price:
                    return "${0} - ${1}".format(min_price, max_price)

        if is_main:
            offers = self.offers
        else:
            offers = self.variant_offers

        price_maps = [
            o.get('pricesInfo', {}).get('priceMap')
            for o in offers
            if o.get('id') in product.get('offers', [])
            and o.get('pricesInfo', {}).get('priceMap')
        ]

        if not price_maps and offers:
            offers = self.product_info_json.get('product', {}).get('offers', {}).values()
            price_maps = [o.get('pricesInfo', {}).get('priceMap', {}) for o in offers
                          if self._is_in_stock(o)]

        if price_maps:
            price = price_maps[0].get('CURRENT', {}).get('price')
            if is_main and price_maps[0].get('WAS'):
                self.temp_price_cut = 1

        else:
            price = self.product_info_json.get('product', {}).get('midasContext', {}).get('price')

        if price:
            return '${:2,.2f}'.format(price)

    # extract product price from its product product page tree
    def _price_from_tree(self):
        """Extracts product price
        Returns:
            string containing the product price, with decimals, no currency
        """

        if self.is_alternative:
            return self._get_alternative_price(self.selected_product, True)

        if self._version() == "Walmart v1":
            try:
                if self.is_bundle_product:
                    return "$" + re.findall(r"\d*\.\d+|\d+", self.tree_html.xpath("//div[@class='PricingInfo']")[0].text_content().replace(",", ""))[0]

                body_raw = "" . join(self.tree_html.xpath("//form[@name='SelectProductForm']//script/text()")).strip()
                body_clean = re.sub("\n", " ", body_raw)
                body_jpart = re.findall("\{\ itemId.*?\}\s*\] }", body_clean)[0]
                sIndex = body_jpart.find("price:") + len("price:") + 1
                eIndex = body_jpart.find("',", sIndex)

                if "camelPrice" not in body_jpart[sIndex:eIndex] and not self._in_stock():
                    return "out of stock - no price given"

                if "camelPrice" not in body_jpart[sIndex:eIndex] and self._in_stores_only():
                    return "in stores only - no online price"

                try:
                    return self.tree_html.xpath("//span[contains(@class, 'camelPrice')]")[0].text_content().strip()
                except:
                    pass

                try:
                    script_bodies = self.tree_html.xpath("//script/text()")
                    price_html = None

                    for script in script_bodies:
                        if "var DefaultItem =" in script or "var DefaultItemWidget =" in script:
                            price_html = script
                            break

                    if not price_html:
                        raise Exception

                    start_index = end_index = 0

                    start_index = price_html.find(",\nprice: '") + len(",\nprice: '")
                    end_index = price_html.find("',\nprice4SAC:")
                    price_html = price_html[start_index:end_index]
                    price_html = html.fromstring(price_html)
                    price = price_html.text_content()
                    price = re.findall("\$\d*\.\d+|\d+", price_html.text_content().replace(",", ""))

                    if not price:
                        raise Exception

                    return price[0]
                except:
                    pass

                return None
            except:
                pass

        if self._version() == "Walmart v2":
            try:
                if self.is_bundle_product:
                    product_info_json = self._extract_product_info_json()

                    if product_info_json["buyingOptions"]["maxPrice"]["currencyAmount"] == product_info_json["buyingOptions"]["minPrice"]["currencyAmount"]:
                        return "${0}".format(product_info_json["buyingOptions"]["minPrice"]["currencyAmount"])
                    elif product_info_json["buyingOptions"]["maxPrice"]["currencyAmount"] > product_info_json["buyingOptions"]["minPrice"]["currencyAmount"]:
                        return "${0}-${1}".format(product_info_json["buyingOptions"]["minPrice"]["currencyAmount"], product_info_json["buyingOptions"]["maxPrice"]["currencyAmount"])
                    else:
                        return "${0}".format(product_info_json["buyingOptions"]["minPrice"]["currencyAmount"])
                else:
                    price = self._clean_html(self.tree_html.xpath("//div[@itemprop='price']")[0].text_content())

                    if price:
                        return price
                    else:
                        if not self._in_stock():
                            return "out of stock - no price given"
                        else:
                            return None
            except:
                pass

            try:
                return self.product_info_json["buyingOptions"]["price"]["currencyUnitSymbol"] + str(self.product_info_json["buyingOptions"]["price"]["currencyAmount"])
            except:
                pass

            try:
                electrode_json = self._extract_electrode_json()

                if electrode_json['product'].get('priceRanges'):
                    price_range = electrode_json['product']['priceRanges'].values()[0]

                    if price_range['minPrices'].get('CURRENT'):
                        min_price = price_range['minPrices']['CURRENT']['price']
                        max_price = price_range['maxPrices']['CURRENT']['price']

                        return "${0} - ${1}".format(min_price, max_price)

                for offer in electrode_json['product']['offers'].values():
                    price_map = offer['pricesInfo'].get('priceMap')

                    if price_map:
                        if price_map.get('LIST') and price_map['LIST']['price'] != price_map['CURRENT']['price']:
                            self.temp_price_cut = 1
                        return "${0}".format(price_map['CURRENT']['price'])

            except Exception as e:
                print 'ERROR GETTING PRICE', e
                pass

            if self._filter_key_fields("price"):
                return self._filter_key_fields("price")

        return None

    def _price_amount(self):
        """Extracts numercial value of product price in
        Returns:
            the numerical value of the price - floating-point number (null if there is no price)
        """

        price_info = self._price_from_tree()

        if price_info is None or price_info == "out of stock - no price given" or price_info == \
                "in stores only - no online price":
            return None
        else:
            price = re.findall(r"\d*\.\d+|\d+", price_info.replace(",", ""))
            return float(price[0])

    def _price_currency(self):
        """Extracts currency of product price in
        Returns:
            price currency symbol
        """
        return "USD"

    # extract htags (h1, h2) from its product product page tree
    def _htags_from_tree(self):
        """Extracts 'h' tags in product page
        Returns:
            dictionary with 2 keys:
            h1 - value is list of strings containing text in each h1 tag on page
            h2 - value is list of strings containing text in each h2 tag on page
        """

        htags_dict = {}

        # add h1 tags text to the list corresponding to the "h1" key in the dict
        htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
        # add h2 tags text to the list corresponding to the "h2" key in the dict
        htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))

        return htags_dict

    def _model(self):
        for spec_name, spec_value in (self._specs() or {}).iteritems():
            if spec_name.lower() == 'model':
                return spec_value

    def _model_meta(self):
        for meta_tag in self._meta_tags():
            if meta_tag[0] == 'model':
                return meta_tag[1]

    def _mpn(self):
        for spec_name, spec_value in (self._specs() or {}).iteritems():
            if spec_name in ['Manufacturer Part Number', 'manufacturer_part_number']:
                return spec_value

    def _categories(self):
        if self.is_alternative:
            categories_data = self.selected_product.get('productAttributes', {}).get(
                'productCategory', {}).get('path')
            if categories_data:
                return [category.get('name') for category in categories_data]

    def _shelf_links_by_level(self):
        # assume new page design
        if self._version() == "Walmart v2":
            categories_list = self.tree_html.xpath("*//ol[@class='breadcrumb-list breadcrumb-list-mini']//li[@class='breadcrumb']//a/span/text()")
            shelf_link_list = self.tree_html.xpath("*//ol[@class='breadcrumb-list breadcrumb-list-mini']//li[@class='breadcrumb']//a/@href")

            shelf_links_by_level = [{"name": categories_list[index], "level": index + 1, "link": "http://www.walmart.com" + shelf_link} for index, shelf_link in enumerate(shelf_link_list)]

            if shelf_links_by_level:
                return shelf_links_by_level

    def _specs(self):
        specs_dict = {}

        for v in self.product_info_json.get('product', {}).get('idmlMap', {}).values():
            specs = v.get('modules', {}).get('Specifications', {}).get('specifications', {}).get('values')
            if specs:
                for spec in specs[0]:
                    for s in spec.values():
                        specs_dict[s['displayName']] = s['values'][0]

        return specs_dict if specs_dict else None

    # extract product seller meta tag content from its product product page tree
    # ! may throw exception if not found
    def _seller_meta_from_tree(self):
        """Extracts sellers of product extracted from 'seller' meta tag, and their availability
        Returns:
            dictionary with sellers as keys and availability (true/false) as values
        """

        sellers = self.tree_html.xpath("//div[@itemprop='offers']")

        sellers_dict = {}
        for seller in sellers:
            # try to get seller if any, otherwise ignore this div
            try:
                avail = (seller.xpath(".//meta[@itemprop='availability']/@content")[0] == "http://schema.org/InStock")
                sellers_dict[seller.xpath(".//meta[@itemprop='seller']/@content")[0]] = avail
            except IndexError:
                pass

        return sellers_dict

    # TODO: more optimal - don't extract this twice
    # TODO: add docstring
    def _owned_meta_from_tree(self):
        seller_dict = self._seller_from_tree()
        owned = seller_dict['owned']
        return owned

    # TODO: more optimal - don't extract this twice
    # TODO: add docstring
    def _marketplace_meta_from_tree(self):
        seller_dict = self._seller_from_tree()
        marketplace = seller_dict['marketplace']
        return marketplace

    def _wupc(self):
        return self.selected_product.get('wupc')

    def _upc(self):
        return self._gtin().lstrip('0')[:12].zfill(12)

    def _gtin(self):
        gtin = self.selected_product.get('upc') or \
                self.selected_product.get('productAttributes', {}).get('sku')

        # only return gtin if it only contains digits
        if gtin and re.match('\d+$', gtin):
            return gtin.zfill(14)

    # extract product seller information from its product product page tree
    def _seller_from_tree(self):
        """Extracts seller info of product extracted from 'Buy from ...' elements on page
        Returns:
            dictionary with 2 values:
            owned - True if owned by walmart.com, False otherwise
            marketplace - True if available on marketplace, False otherwise
        """

        seller_info = {}
        sellers = self._seller_meta_from_tree()

        # owned if has seller Walmart.com and availability for it is true
        seller_info['owned'] = 1 if ('Walmart.com' in sellers.keys() and sellers['Walmart.com']) else 0
        # found on marketplace if there are other keys other than walmart and they are in stock
        # TODO:
        #      more sophisticated checking of availability for marketplace? (values are more than just InStock/OutOfStock)
        #      (because for walmart they should only be available when in stock)
        # remove Walmart key as we already checked for it
        if 'Walmart.com' in sellers.keys():
            del sellers['Walmart.com']
        # seller_info['marketplace'] = 1 if (len(sellers.keys()) > 0 and any(sellers.values())) else 0
        seller_info['marketplace'] = 1 if len(sellers.keys()) > 0 else 0

        return seller_info

    def _average_review(self):
        if self._review_count():
            return round(self._get_alternate_review_data()['average_rating'], 2)

    def _review_count(self):
        if self._reviews():
            return self._get_alternate_review_data()['num_of_reviews']
        return 0

    def _get_alternate_review_data(self):
        selected = self.product_info_json_for_description.get('product', {}).get('selected', {}).get('product')
        review_data = self.product_info_json_for_description.get('product', {}).get('reviews', {}).get(selected, {})

        if review_data:
            num_of_reviews = review_data.get('totalReviewCount', 0)
            average_rating = review_data.get('averageOverallRating', 0)

            rating_by_star = [
                [5, review_data.get('ratingValueFiveCount', 0)],
                [4, review_data.get('ratingValueFourCount', 0)],
                [3, review_data.get('ratingValueThreeCount', 0)],
                [2, review_data.get('ratingValueTwoCount', 0)],
                [1, review_data.get('ratingValueOneCount', 0)]
            ]

            buyer_reviews = {'rating_by_star': rating_by_star,
                             'average_rating': average_rating,
                             'num_of_reviews': num_of_reviews}

            return buyer_reviews

        return {}

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        review_data = self._get_alternate_review_data()

        # If there are no reviews, try fetching the page again
        if not review_data:
            self._extract_page_tree()
            review_data = self._get_alternate_review_data()

        if review_data.get('num_of_reviews'):
            self.reviews = review_data['rating_by_star']
            return self.reviews

    def _rollback(self):
        if self._version() == "Walmart v1":
            rollback = self.tree_html.xpath("//div[@class='ItemFlagRow']/img[@alt='Rollback']")
        elif self._version() == "Walmart v2":
            rollback = self.tree_html.xpath('//div[contains(@class, "js-product-offer-summary")]//'
                                            'span[contains(@class,"flag-rollback")]')

        if not rollback:
            return 0
        else:
            return 1

    def _no_longer_available(self):
        if self.is_alternative:
            # if it sold online but has no price, then it is no longer available
            if self._site_online() and not self._price_from_tree():
                return 1
            # if it has no offers, then it is no longer available
            if self.offers:
                return 0
            return 1

        try:
            txt = self.tree_html.xpath("//div[contains(@class, 'prod-no-buying-option')]")[0].text_content().lower()

            if "information unavailable" in txt or "this item is no longer available" in txt:
                return True
        except:
            pass

        if self.tree_html.xpath('//*[contains(@class, "invalid") and contains(text(), "tem not available")]'):
            return True

        if self.tree_html.xpath('//*[contains(@class, "NotAvailable") and contains(text(), "ot Available")]'):
            return True

        return False

    def _temporary_unavailable(self):
        return self.temporary_unavailable

    def _temp_price_cut(self):
        if self.is_alternative:
            self._price_from_tree()
            return self.temp_price_cut

        self._extract_product_info_json()

        if self.product_info_json and self.product_info_json.get('buyingOptions'):
            if self.product_info_json['buyingOptions'].get('listPrice'):
                return 1
            if self.product_info_json['buyingOptions'].get('wasPrice'):
                return 1
            if self.product_info_json['buyingOptions'].get('price', {}).get('priceType') == 'REDUCED':
                return 1

            return 0

        return self.temp_price_cut

    def _free_pickup_today(self):
        self._extract_product_info_json()

        if self.product_info_json and self.product_info_json.get('buyingOptions'):
            if 'pickupToggleLabel' in self.product_info_json['buyingOptions']:
                if self.product_info_json['buyingOptions']['pickupToggleLabel'] == 'FREE pickup today':
                    return 1

        return 0

    def _buying_option(self):
        self._extract_product_info_json()

        if self.product_info_json and "buyingOptions" not in self.product_info_json:
            return 0

        return 1

    def _image_alt_text(self):
        image_alt_text = []

        for image in self._image_urls() or []:
            image_alt_text.append(self._product_name())

        if image_alt_text:
            return image_alt_text

    def _no_image(self, url):
        if re.match(".*no.image\..*", url):
            return True
        else:
            try:
                return Scraper._no_image(self, url, True)
            except:
                return True

    def _image_size(self, url):
        try:
            image_bytes = self._request(url).content
            image = Image.open(io.BytesIO(image_bytes))
            return image.size
        except Exception as e:
            print '%s ERROR GETTING IMAGE SIZE %s: %s' % (type(e), url, e)
            return [0, 0]

    def _image_urls_new(self):
        variants = deep_search('variants', self.product_info_json.get('product', {}).get('variantCategoriesMap', {}))

        image_keys = self.selected_product.get('images', [])
        images = self.product_info_json.get('product', {}).get('images', {})

        if variants and len(variants) > 1:
            for variant in variants[0].values():
                if variant.get('selected') and variant.get('images'):
                    image_keys = variant['images']
                    break

        if not images:
            image_keys = self.product_info_json.get('terra', {}).get('images', {}).keys()
            images = self.product_info_json.get('terra', {}).get('images')

        if self.is_bundle:
            image_urls = []
            for section in self.product_info_json['product'].get('sections', []):
                image_url = section['components'][0]['productImageUrl'].split('?')[0]
                if image_url not in image_urls:
                    image_urls.append(image_url)
            if image_urls:
                return [i for i in image_urls if not self._no_image(i)]
            if self.product_info_json['product'].get('bundlePrimaryImage'):
                return [self.product_info_json['product']['bundlePrimaryImage']]

        image_urls = []

        image_res = []
        image_dimensions = []
        zoom_image_dimensions = []

        for image_key in image_keys:
            image = images.get(image_key, {})

            if self.is_bundle and len(images) > 1 and not \
                    (image.get('rank') == 1 and image.get('type') == 'PRIMARY'):
                continue

            image_sizes = image.get('assetSizeUrls', {})

            if len(image_sizes) == 1:
                main_image_url = image_sizes.get(image_sizes.keys()[0])
            else:
                main_image_url = image_sizes.get('main') or image_sizes.get('DEFAULT')

            if main_image_url:
                if self._no_image(main_image_url):
                    continue

                main_image_url = main_image_url.split('?', 1)[0]

                if self.get_image_dimensions:
                    image_size = self._image_size(main_image_url)

                    image_res.append(image_size)

                    if image_size[0] >= 500 and image_size[1] >= 500:
                        image_dimensions.append(1)
                    else:
                        image_dimensions.append(0)

                image_urls.append(main_image_url)

            if image_sizes.get('zoom'):
                zoom_image_dimensions.append(1)
            else:
                zoom_image_dimensions.append(0)

        self.image_res = image_res
        self.image_dimensions = image_dimensions
        self.zoom_image_dimensions = zoom_image_dimensions

        return image_urls

    def _image_urls(self):
        if self.extracted_image_urls:
            return self.image_urls

        self.extracted_image_urls = True

        try:
            self.image_urls = self.remove_duplication_keeping_order_in_list(self._image_urls_new())
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', 'Error extracting images: {}'.format(e))

        for _ in range(2):
            if not self.image_urls:
                if self.lh:
                    self.lh.add_list_log('errors', 'No image urls')

                self._extract_page_tree()
                self.image_urls = self.remove_duplication_keeping_order_in_list(self._image_urls_new())

        return self.image_urls

    def _image_res(self):
        self._image_urls()
        return self.image_res

    def _image_dimensions(self):
        self._image_urls()
        return self.image_dimensions

    def _zoom_image_dimensions(self):
        self._image_urls()
        return self.zoom_image_dimensions

    def _extract_product_info_json(self, force=False):
        """Extracts body of javascript function
        found in a script tag on each product page,
        that contains various usable information about product.
        Stores function body as json decoded dictionary in instance variable.
        Returns:
            function body as dictionary (containing various info on product)
        """
        if self.extracted_product_info_jsons and not force:
            return self.product_info_json

        self.extracted_product_info_jsons = True

        '''
        try:
            product_api_json = self._request(self.BASE_URL_PRODUCT_API.format(self._product_id())).content
            self.product_api_json = json.loads(product_api_json)
        except Exception, e:
            try:
                product_api_json = self._exclude_javascript_from_description(product_api_json)
                product_api_json = product_api_json.replace("\n", "").replace("\r", "")
                self.product_api_json = json.loads(product_api_json)
            except:
                print "Error (Loading product json from Walmart api)", e
                self.product_api_json = None
        '''

        if self._version() == "Walmart v2":
            if self.is_bundle_product:
                try:
                    product_info_json = self._find_between(html.tostring(self.tree_html), 'define("product/data",', ");\n")
                    product_info_json = json.loads(product_info_json)
                    self.product_info_json = product_info_json
                except:
                    product_info_json = self._find_between(html.tostring(self.tree_html), 'define("product/data",', '); define("ads/data", _WML.MIDAS_CONTEXT)')
                    product_info_json = json.loads(product_info_json)
                    self.product_info_json = product_info_json

                try:
                    product_choice_info_json = self._find_between(self.page_raw_text, 'define("choice/data",', ");\n")
                    product_choice_info_json = json.loads(product_choice_info_json)
                    self.product_choice_info_json = product_choice_info_json
                except:
                    pass

                if not self.product_choice_info_json:
                    try:
                        product_choice_info_json = self._find_between(self.page_raw_text, 'define("non-choice/data",', ");\n")
                        product_choice_info_json = json.loads(product_choice_info_json)
                        self.product_choice_info_json = product_choice_info_json
                    except:
                        pass

                return self.product_info_json
            else:
                try:
                    self.product_info_json = json.loads(re.search('define\("product\/data",[\n\s](.+?)\)?;?\n', self.page_raw_text).group(1))
                except:
                    _JS_DATA_RE = re.compile(
                        r'window\.__WML_REDUX_INITIAL_STATE__\s*=\s*(\{.+?\})(\s*;\s*})?\s*;\s*<\/script>', re.DOTALL)
                    js_data = re.search(_JS_DATA_RE, self.page_raw_text)
                    self.product_info_json = json.loads(js_data.group(1))
                    self.product_info_json_for_description = self.product_info_json

                    if not self.product_info_json.get('product', {}).get('selected', {}).get('product'):
                        product_info_json = self.tree_html.xpath('//script[@id="atf-content"]/text()')
                        if product_info_json:
                            self.product_info_json = json.loads(product_info_json[0])['atf-content']
                        else:
                            product_info_json = self.tree_html.xpath('//script[@id="content"]/text()')
                            if product_info_json:
                                self.product_info_json = json.loads(product_info_json[0])['content']

                        product_info_json = self.tree_html.xpath('//script[@id="btf-content"]/text()')
                        if product_info_json:
                            self.product_info_json_for_description = json.loads(product_info_json[0])['btf-content']
                        else:
                            self.product_info_json_for_description = self.product_info_json

                    selected = self.product_info_json.get('product', {}).get('selected', {})

                    selected_product_id = selected.get('lastSuccessfullyFetchedProduct')

                    if selected.get('status') == 'FETCHED':
                        selected_product_id = selected.get('product') or selected_product_id

                    self.selected_product = self.product_info_json.get('product', {}).get('products', {}).get(selected_product_id, {})

                    if not self.selected_product:
                        self.selected_product = self.product_info_json.get('product', {}).get('primaryProduct', {})

                    if self.selected_product.get('productAttributes', {}).get('classType') == 'BUNDLE' and \
                            not self.selected_product.get('bundleType') == 'INFLEXIBLE_KIT':
                        self.is_bundle = True

                    self.is_alternative = True

                    return self.product_info_json


    def _extract_electrode_json(self):
        if self.extracted_electrode_json:
            return self.electrode_json

        self.extracted_electrode_json = True

        electrode_url = self.BASE_URL_ELECTRODE_API.format(self._product_id())
        self.electrode_json = self._request(electrode_url).json()

        return self.electrode_json

    def _extract_terra_firma(self):
        if self.extracted_terra_firma:
            return self.terra_firma

        self.extracted_terra_firma = True

        primary_product_id = self.selected_product.get('primaryProductId')

        if primary_product_id:
            for i in range(3):
                try:
                    terra_firma_url = self.BASE_URL_TERRA_FIRMA_API.format(primary_product_id)
                    terra_firma = self._request(terra_firma_url).json()
 
                    self.terra_firma = terra_firma.get('payload', {}).get('idmlMap', {}).get(primary_product_id, {})

                    return
                except Exception as e:
                    print traceback.format_exc()

                    if self.lh:
                        self.lh.add_list_log('errors', 'Error extracting terra firma: {}'.format(e))

    # ! may throw exception if not found
    def _owned_from_script(self):
        """Extracts 'owned' (by walmart) info on product
        from script tag content (using an object in a js function).
        Returns:
            1/0 (product owned/not owned)
        """

        if not self.product_info_json:
            pinfo_dict = self._extract_product_info_json()
        else:
            pinfo_dict = self.product_info_json

        seller = pinfo_dict['analyticsData']['sellerName']

        # TODO: what if walmart is not primary seller?
        if (seller == "Walmart.com"):
            return 1
        else:
            return 0

    # ! may throw exception if not found
    def _marketplace_from_script(self):
        """Extracts 'marketplace' sellers info on product
        from script tag content (using an object in a js function).
        Returns:
            1/0 (product has marketplace sellers/has not)
        """

        if not self.product_info_json:
            pinfo_dict = self._extract_product_info_json()
        else:
            pinfo_dict = self.product_info_json

        if not pinfo_dict.get('buyingOptions'):
            electrode_json = self._extract_electrode_json()
            sold_by = electrode_json['product']['idmlMap'].values()[0]['modules']['GeneralInfo']['sold_by']['values']
            if 'Marketplace' in sold_by:
                return 1
            return 0

        # TODO: what to do when there is no 'marketplaceOptions'?
        #       e.g. http://www.walmart.com/ip/23149039
        try:
            marketplace_seller_info = pinfo_dict['buyingOptions']['marketplaceOptions']

            if not marketplace_seller_info:
                if pinfo_dict["buyingOptions"]["seller"]["walmartOnline"]:
                    marketplace_seller_info = None
                elif not pinfo_dict["buyingOptions"]["seller"]["walmartOnline"]:
                    marketplace_seller_info = pinfo_dict["buyingOptions"]["seller"]["name"]
        except Exception:
            # if 'marketplaceOptions' key was not found,
            # check if product is owned and has no other sellers
            owned = self._owned_from_script()
            other_sellers = pinfo_dict['buyingOptions']['otherSellersCount']
            if owned and not other_sellers:
                return 0
            else:
                # didn't find info on this
                return None

        # if list is empty, then product is not available on marketplace
        if marketplace_seller_info:
            return 1
        else:
            return 0

    def _in_stores(self):
        """Extracts whether product is available in stores.
        Returns 1/0
        """

        if self.is_alternative:
            if self.offers and 'STORE' in self.offers[0].get('offerInfo', {}).get('offerType'):
                return 1
            return 0

        if self._version() == "Walmart v1":
            return self._in_stores_v1()

        if self._version() == "Walmart v2":
            return self._in_stores_v2()

    def _in_stores_out_of_stock(self):
        if self._in_stores() == 1:
            if self.is_alternative:
                if self._no_longer_available():
                    return 1
                for offer in self.offers:
                    if 'STORE' in offer.get('offerInfo', {}).get('offerType') and \
                            self._is_in_stock(offer):
                        return 0
                return 1

            available_stores = self.product_api_json.get("product", {}).get("buyingOptions", {}).get("pickupOptions", [])
            available_stores = available_stores if available_stores else []

            for store in available_stores:
                if store["displayArrivalDate"].lower().strip() != "out of stock":
                    return 0

            for seller in self.product_info_json["buyingOptions"]["marketplaceOptions"]:
                if seller["seller"]["displayName"].lower() == "walmart store" and seller["available"]:
                    return 0

            return 1

        return None

    def _in_stores_v1(self):
        try:
            if self._find_between(self.page_raw_text, "isBuyableInStore:", ",").strip() == "true":
                return 1

            try:
                onlinePriceText = "".join(self.tree_html.xpath("//tr[@id='WM_ROW']//div[@class='onlinePriceWM']//text()"))
                if "In stores only" in onlinePriceText:
                    return 1
            except:
                pass
        except:
            pass

        return 0

    def _in_stores_v2(self):
        try:
            pinfo_dict = self._extract_product_info_json()
            pickupable = pinfo_dict.get("buyingOptions", {}).get("pickupable", False)

            if pickupable:
                return 1

            sold_only_at_store = pinfo_dict.get("buyingOptions", {}).get("storeOnlyItem", False)



            available_stores = pinfo_dict.get("analyticsData", {}).get("storesAvail", [])
            available_stores = available_stores if available_stores else []

            for store in available_stores:
                if int(store["isAvail"]) == 1:
                    return 1

            # The product is site online as marketplace sellers(means walmart is one of marketplace seller of this product
            sellers = self._marketplace_sellers_from_script()

            if sellers:
                sellers = [seller.lower() for seller in sellers]

                if "walmart store" in sellers:
                    return 1

            marketplace_seller_names = self.tree_html.xpath("//div[contains(@data-automation-id, 'product-mp-seller-name')]")

            if marketplace_seller_names:
                for marketplace in marketplace_seller_names:
                    if "walmart store" in marketplace.text_content().lower().strip():
                        return 1

        except Exception:
            pass

        return 0

    def _stores_available_from_script_old_page(self):
        """Extracts whether product is available in stores.
        Works on old page version.
        Returns 1/0
        """

        body_raw = "" . join(self.tree_html.xpath("//form[@name='SelectProductForm']//script/text()")).strip()
        body_clean = re.sub("\n", " ", body_raw)
        body_jpart = re.findall("\{\ itemId.*?\}\s*\] }", body_clean)[0]

#        body_dict = json.loads(body_jpart)

        sIndex = body_jpart.find("isInStore") + len("isInStore") + 2
        eIndex = body_jpart.find(",", sIndex)

        if body_jpart[sIndex:eIndex] == "true":
            return 1
        else:
            return 0

    def _get_alternative_marketplaces(self):
        # if there is one seller, structure of json is different
        needed_data = self.product_info_json.get('product', {}).get('offers')
        if needed_data:
            if needed_data.get("availabilityStatus"):
                values = [needed_data]
            else:
                values = needed_data.values()
        else:
            values = []
        # https://www.walmart.com/nco/Prego-Ready-Meals-Roasted-Tomato--Vegetables-Penne-9-oz-Pack-of-2/47969283
        # marketplaces list has False element in the list, instead of dict (why?)
        marketplaces_data = filter(lambda item: isinstance(item, dict), values)

        marketplaces_names = {}
        sellers = self.product_info_json.get('product', {}).get('sellers', {})
        sellers = sellers.values() if not sellers.get('sellerId') else [sellers]
        for seller in sellers:
            seller_id = seller.get('sellerId')
            seller_name = seller.get('sellerDisplayName')
            marketplaces_names[seller_id] = {
                'name': seller_name,
                'catalog_seller_id': seller.get('catalogSellerId')
            }

        marketplaces = []
        for marketplace in marketplaces_data:
            offer_id = marketplace.get('id')
            seller_id = marketplace.get('sellerId')
            price = marketplace.get(
                'pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('price', 0)
            currency = marketplace.get(
                'pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('currencyUnit')
            name = marketplaces_names.get(seller_id).get('name')
            catalog_seller_id = marketplaces_names.get(seller_id).get('catalog_seller_id')
            # CON-28527
            # get lowest shipping price
            if marketplace.get('fulfillment', {}).get('freeShippingThresholdPrice') and name == "Walmart.com":
                shipping_price = 0
            else:
                shipping_prices = marketplace.get('fulfillment', {}).get('shippingOptions', [])
                shipping_prices = [p.get("fulfillmentPrice", {}).get(
                    "price", 0) for p in shipping_prices]
                if shipping_prices:
                    shipping_price = min(shipping_prices)
                else:
                    shipping_price = 0
            try:
                totalprice = float(shipping_price) + float(price)
            except:
                totalprice = price
            if offer_id in self.selected_product.get('offers'):
                marketplaces.append({'name': name,
                                     'price': price,
                                     'currency': currency,
                                     'totalprice': totalprice,
                                     'seller_id': seller_id,
                                     'catalog_seller_id': catalog_seller_id
                                     })

        # CON-28527
        # marketplaces order matters - by default they are sorted by price + shipping price
        sorted_marketplaces = sorted(marketplaces, key=lambda k: k['totalprice'])
        # remove totalprice from sorted_marketplaces
        for market in sorted_marketplaces:
            market.pop('totalprice', None)
        return sorted_marketplaces

    def _get_offers(self, is_main=True):
        try:
            offers = self.product_info_json.get('terra', {}).get('offers', {}).values()

            if not offers:
                offers = self.product_info_json.get('product', {}).get('offers', {}).values()

            # get offers order
            selected_product_id = self.selected_product.get('productId')
            offers_order = self.product_info_json.get('offersOrder', {}).get(selected_product_id) or []
            offers_order = [o.get('id') for o in offers_order if o]

            # sort offers by order in offers_order
            offers = sorted(offers, key=lambda o: offers_order.index(o.get('id')) \
                    if o.get('id') in offers_order else len(offers_order))

            filtered_offers = []

            online_offers = filter(lambda o: 'ONLINE' in o.get('offerInfo', {}).get('offerType'), offers)
            in_stock_offers = filter(lambda o: self._is_in_stock(o), offers)
            in_stock_online_offers = filter(lambda o: o in online_offers and o in in_stock_offers, offers)
            store_only_offers = filter(lambda o: o.get('offerInfo', {}).get('offerType') == 'STORE_ONLY', offers)

            INVALID_OFFER_TYPES = ['NON_TRANSACTABLE_STORE_ONLY', 'DISPLAY_ONLY']

            valid_offers = filter(lambda o: o.get('offerInfo', {}).get('offerType') not in INVALID_OFFER_TYPES, offers)

            for offer in offers:
                # if it's a marketplace offer
                if offer.get('sellerId') and offer.get('sellerId') != self.WALMART_SELLER_ID:
                    midas_price = self.product_info_json.get('product', {}).get('midasContext', {}).get('price')

                    # if there is no midas price, don't include it (because product is actually INLA)
                    if not midas_price:
                        continue

                    # if it's not in stock
                    if not self._is_in_stock(offer):
                        price = offer.get('pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('price')

                        # only include it if there are no in stock offers, it is online, and its price matches the midas price
                        if not in_stock_offers and offer in online_offers and price == midas_price:
                            filtered_offers.append(offer)
                            # then break
                            break

                        continue

                # if it's not in stock
                if not self._is_in_stock(offer) and is_main:
                    # if there are other in stock, online offers, don't include it
                    if in_stock_online_offers:
                        continue

                offer_type = offer.get('offerInfo', {}).get('offerType')

                # if it is an invalid offer, only inlcude it if there are no valid offers and it is the first offer
                if offer_type in INVALID_OFFER_TYPES:
                    if len(valid_offers) == 0 and offer == offers[0]:
                        filtered_offers.append(offer)

                else:
                    filtered_offers.append(offer)

            return filtered_offers
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', 'Error getting offers: {}'.format(e))

            return []

    # ! may throw exception if not found
    def _marketplace_sellers_from_script(self):
        """Extracts list of marketplace sellers for this product.
        Works on new page version.
        Returns:
            list of strings representing marketplace sellers,
            or None if none found / not relevant
        """

        pinfo_dict = self._extract_product_info_json()

        if pinfo_dict.get('buyingOptions'):
            sellers_dict = pinfo_dict["buyingOptions"]["marketplaceOptions"]
            return map(lambda d: d["seller"]["displayName"], sellers_dict)

        electrode_json = self._extract_electrode_json()
        for product in electrode_json['product']['products'].values():
            if product.get('offers'):
                terra_firma = self._extract_terra_firma()

                sellers_dict = terra_firma['payload']['sellers']
                return map(lambda d: d['sellerDisplayName'], sellers_dict.values())

    # ! may throw exception if not found
    def _marketplace_prices_from_script(self):
        """Extracts list of marketplace sellers for this product.
        Works on new page version.
        Returns:
            list of strings representing marketplace sellers,
            or None if none found / not relevant
        """

        if not self.product_info_json:
            pinfo_dict = self._extract_product_info_json()
        else:
            pinfo_dict = self.product_info_json

        prices = []

        if pinfo_dict.get('analyticsData'):
            sellers_dict = pinfo_dict["analyticsData"]["productSellersMap"]

            for seller in sellers_dict:
                if seller["sellerName"].lower() not in ["walmart.com", "walmart store"]:
                    prices.append(float(seller["price"]))

        else:
            terra_firma = self._extract_terra_firma()
            for offer in terra_firma['payload']['offers'].values():
                prices.append(offer['pricesInfo']['priceMap']['CURRENT']['price'])

        return prices if prices else None

    def _marketplace_lowest_price(self):
        marketplace_prices = self._marketplace_prices()

        if marketplace_prices is None:
            return None

        return min(marketplace_prices)

    def _parse_marketplaces_data_alternative(self):
        # if there is one seller, structure of json is different
        needed_data = self.product_info_json.get('product', {}).get('offers')
        if needed_data:
            if needed_data.get("availabilityStatus"):
                # pprint.pprint([needed_data])
                values = [needed_data]
            else:
                # pprint.pprint(needed_data.values())
                values = needed_data.values()
        else:
            values = []
        # https://www.walmart.com/nco/Prego-Ready-Meals-Roasted-Tomato--Vegetables-Penne-9-oz-Pack-of-2/47969283
        # marketplaces list has False element in the list, instead of dict (why?)
        return filter(lambda item: isinstance(item, dict), values)

    def _in_stock_old(self):
        """Extracts info on whether product is available to be
        bought on the site, from any seller (marketplace or owned).
        Works on old page design
        Returns:
            1/0 (available/not available)
        """

        sellers = self._seller_meta_from_tree()

        try:
            mp_seller_na_msg_3 = self.tree_html.xpath("//span[@id='MP_SELLER_NA_MSG_3']/@style")[0].replace(" ", "")

            if mp_seller_na_msg_3 == "display:block;":
                return 0
        except Exception:
            pass

        available = any(sellers.values())

        return 1 if available else 0

    def _marketplace(self):
        """Extracts info on whether product is found on marketplace
        Uses functions that work on both old page design and new design.
        Will choose whichever gives results.
        Returns:
            1/0 (marketplace sellers / no marketplace sellers)
        """
        if self.is_alternative:
            for offer in self.offers:
                if offer.get('sellerId') and offer.get('sellerId') != self.WALMART_SELLER_ID:
                    return 1
            return 0

        # assume new design
        # _owned_from_script() may throw exception if extraction fails
        # (causing the service to return None for "owned")
        try:
            marketplace_new = self._marketplace_from_script()
        except Exception:
            marketplace_new = None

        if marketplace_new is None:
            try:
                # try to extract assuming old page structure
                marketplace_new = self._marketplace_meta_from_tree()
            except Exception:
                marketplace_new = None

        if marketplace_new is None:
            marketplace_new = 0

        return marketplace_new

    def _marketplace_sellers(self):
        """Extracts list of marketplace sellers for this product
        Works for both old and new page version
        Returns:
            list of strings representing marketplace sellers,
            or None if none found / not relevant
        """

        if self.is_alternative:
            sellers = self.product_info_json.get('product', {}).get('sellers', {})

            seller_names = []

            for offer in self.offers:
                seller_name = sellers.get(offer.get('sellerId'), {}).get('sellerDisplayName')
                if seller_name and not 'Walmart' in seller_name:
                    seller_names.append(seller_name)

            if seller_names:
                return seller_names

            return None

        if self._version() == "Walmart v2":
            sellers = self._marketplace_sellers_from_script()
            # filter out walmart
            sellers = filter(lambda s: s.lower() not in ["walmart.com", "walmart store"], sellers)

            if sellers:
                return sellers

            if self._marketplace_prices():
                pinfo_dict = self._extract_product_info_json()

                sellers = []
                sellers_dict = pinfo_dict["analyticsData"]["productSellersMap"]

                for seller in sellers_dict:
                    if seller["sellerName"] not in ["walmart.com", "walmart store"]:
                        if seller["sellerId"] == pinfo_dict["buyingOptions"]["seller"]["sellerId"] and seller["sellerName"] != \
                                pinfo_dict["buyingOptions"]["seller"]["displayName"]:
                            sellers.append(pinfo_dict["buyingOptions"]["seller"]["displayName"])
                        else:
                            sellers.append(seller["sellerName"])

                return sellers if sellers else None

        if self._version() == "Walmart v1":
            sellers = self._seller_meta_from_tree().keys()
            # filter out walmart
            sellers = filter(lambda s: s.lower() not in ["walmart.com", "walmart store"], sellers)

            return sellers if sellers else None

        return None

    def _marketplace_prices(self):
        """Extracts list of marketplace sellers for this product
        Works for both old and new page version
        Returns:
            list of strings representing marketplace sellers,
            or None if none found / not relevant
        """

        if self.is_alternative:
            if self._marketplace():
                prices = []

                for offer in self.offers:
                    if offer.get('sellerId') and offer.get('sellerId') != self.WALMART_SELLER_ID:
                        price = offer.get('pricesInfo', {}).get('priceMap', {}).get('CURRENT', {}).get('price')
                        prices.append(price)

                return prices
            return None

        if self._version() == "Walmart v2":
            prices = self._marketplace_prices_from_script()

            if not prices:
                return None

            return prices if prices else None

        if self._version() == "Walmart v1":
            # assume old page version
            sellers = self._marketplace_sellers()
            product_info_json_text = self._find_between(self.page_raw_text, "var DefaultItemWidget =", "addMethodsToDefaultItem(DefaultItemWidget);").strip()

            if not product_info_json_text:
                product_info_json_text = self._find_between(self.page_raw_text, "var DefaultItem =", "addMethodsToDefaultItem(DefaultItem);")

            if not sellers:
                return None

            if not "sellerName: '" + sellers[0] + "'," in product_info_json_text:
                return None

            price_html = html.fromstring(self._find_between(product_info_json_text, ",\nprice: '", "',\nprice4SAC:"))

            prices = [price_html.text_content()]

            prices = [float(price) for price in prices]

            return prices if prices else None

        return None

    def _marketplace_out_of_stock(self):
        """Extracts info on whether currently unavailable from any marketplace seller - binary
        Uses functions that work on both old page design and new design.
        Will choose whichever gives results.
        Returns:
            1/0
        """
        if self.is_alternative:
            if self._marketplace():
                for offer in self.offers:
                    if offer.get('sellerId') and offer.get('sellerId') != self.WALMART_SELLER_ID \
                            and self._is_in_stock(offer):
                        return 0
                return 1
            return None

        product_info_json = self._extract_product_info_json()

        if self._marketplace_sellers() and product_info_json.get('analyticsData'):
            for seller in product_info_json["analyticsData"]["productSellersMap"]:
                if seller["sellerName"].lower() not in ["walmart.com", "walmart store"] and int(seller["isAvail"]) == 1:
                    return 0

            availability = self.tree_html.xpath('//meta[@itemprop="availability"]/@content')
            if availability and availability[0] == 'InStock':
                return 0

            if product_info_json.get("buyingOptions", {}).get("allVariantsOutOfStock") == False:
                return 0

            return 1

        electrode_json = self._extract_electrode_json()

        for offer in electrode_json['product']['offers'].values():
            if offer['productAvailability']['availabilityStatus'] == 'IN_STOCK':
                return 1

        return 0

    def _get_primary_seller(self):
        sellers = self.product_info_json.get('product', {}).get('sellers', {})
        if self.offers:
            # return the first seller id, or Walmart if it is has none
            return sellers.get(self.offers[0].get('sellerId') or self.WALMART_SELLER_ID, {})
        return {}

    def _primary_seller(self):
        if self.is_alternative:
            return self._get_primary_seller().get('sellerDisplayName')

        if self._version() == "Walmart v1":
            return self.tree_html.xpath("//meta[@itemprop='seller']/@content")[0]

        if self._version() == "Walmart v2":
            self._extract_product_info_json()

            primary_seller = self.tree_html.xpath('//span[contains(@class,"primary-seller")]//b/text()')
            if primary_seller and primary_seller[0] == 'Walmart store':
                return "Walmart store"

            if self.product_info_json.get('buyingOptions'):
                return self.product_info_json["buyingOptions"]["seller"]["displayName"]

            terra_firma = self._extract_terra_firma()
            return terra_firma['payload']['sellers'].values()[0]['sellerDisplayName']

        return None

    def _seller_id(self):
        if self.is_alternative:
            return self._get_primary_seller().get('sellerId')

        self._extract_product_info_json()
        if self._primary_seller() == "Walmart store":
            return None

        if self.product_info_json.get('buyingOptions'):
            return self.product_info_json["buyingOptions"]["seller"]["sellerId"]

        terra_firma = self._extract_terra_firma()
        return terra_firma['payload']['sellers'].values()[0]['sellerId']

    def _us_seller_id(self):
        if self.is_alternative:
            return self._get_primary_seller().get('catalogSellerId')

        self._extract_product_info_json()
        if self._primary_seller() == "Walmart store":
            return None

        if self.product_info_json.get('buyingOptions'):
            return self.product_info_json["buyingOptions"]["seller"]["catalogSellerId"]

        terra_firma = self._extract_terra_firma()
        return terra_firma['payload']['sellers'].values()[0]['catalogSellerId']

    def _site_online(self):
        """Extracts whether the item is sold by the site and delivered directly
        Works on both old and new page version.
        Returns 1/0
        """

        if self.is_alternative:
            for offer in self.offers:
                if (not offer.get('sellerId') or offer.get('sellerId') == self.WALMART_SELLER_ID) and \
                        offer.get('offerInfo', {}).get('offerType') != 'STORE_ONLY':
                    return 1
            return 0

        if self._version() == "Walmart v1":
            return self._site_online_v1()

        if self._version() == "Walmart v2":
            return self._site_online_v2()

    def _site_online_v1(self):
        try:
            try:
                onlinePriceText = "".join(self.tree_html.xpath("//tr[@id='WM_ROW']//div[@class='onlinePriceWM']//text()"))
                if "In stores only" in onlinePriceText:
                    return 0
            except:
                pass

            if "walmart.com" in self._find_between(self.page_raw_text, "sellerName:", ",").lower() and \
                            self._find_between(self.page_raw_text, "isBuyableOnWWW:", ",").strip() == "true":
                return 1

            if "WalmartMainBody DynamicMode wmBundleItemPage" in self.page_raw_text:
                if "online" in (" " . join(self.tree_html.xpath("//tr[@id='WM_ROW']//div[@id='onlinePriceLabel']/text()"))).lower():
                    return 1
        except:
            pass

        return 0

    def _site_online_v2(self):
        # The product is site online according to the product json info
        pinfo_dict = self._extract_product_info_json()

        sold_only_at_store = pinfo_dict.get("buyingOptions", {}).get("storeOnlyItem", False)

        if sold_only_at_store:
            return 0

        walmart_online = pinfo_dict.get("buyingOptions", {}).get("seller", {}).get("walmartOnline", False)

        if walmart_online:
            return 1

        # The product is site online as marketplace sellers(means walmart is one of marketplace seller of this product
        sellers = self._marketplace_sellers_from_script()

        if sellers:
            sellers = [seller.lower() for seller in sellers]

            if "walmart.com" in sellers:
                return 1

        marketplace_seller_names = self.tree_html.xpath("//div[contains(@data-automation-id, 'product-mp-seller-name')]")

        if marketplace_seller_names:
            for marketplace in marketplace_seller_names:
                if "walmart.com" in marketplace.text_content().lower().strip():
                    return 1

        return 0

    def _is_in_stock(self, offer):
        return offer.get('productAvailability', {}).get('availabilityStatus') not in ['OUT_OF_STOCK', 'RETIRED']

    def _in_stock(self):
        if self._no_longer_available():
            return 0
        return super(WalmartScraper, self)._in_stock()

    def _site_online_out_of_stock(self):
        """Extracts whether currently unavailable from the site - binary
        Works on both old and new page version.
        Returns 1/0
        """

        if self._site_online() == 1:
            if self.is_alternative:
                if self._no_longer_available():
                    return 1
                for offer in self.offers:
                    if 'ONLINE' in offer.get('offerInfo', {}).get('offerType') and \
                            self._is_in_stock(self.offers[0]):
                        return 0
                return 1

            try:
                if self._version() == "Walmart v2":
                    if self.product_info_json["buyingOptions"]["displayArrivalDate"].lower() == "see dates in checkout":
                        return 0

                    if self.product_info_json['buyingOptions'].get('allVariantsOutOfStock') == False:
                        return 0

                    if self.product_info_json['buyingOptions'].get('available') == True:
                        return 0

                    marketplace_options = self.product_info_json.get("buyingOptions", {}).get("marketplaceOptions")

                    if marketplace_options:
                        for seller in marketplace_options:
                            if seller["seller"]["displayName"].lower() == "walmart.com" and seller["available"]:
                                return 0

                    return 1
                else:
                    site_online_out_of_stock = self.tree_html.xpath("//meta[@itemprop='availability']/@content")[0]

                    if "InStock" in site_online_out_of_stock:
                        return 0
                    elif "OutOfStock" in site_online_out_of_stock:
                        return 1
            except Exception:
                return None

        return None

    def _failure_type(self):
        # do not fail walmart shelf pages
        if self.__class__.__name__ == 'WalmartShelfScraper':
            return

        # if page is temporarily unavailable, do not consider that a failure
        if self.temporary_unavailable:
            return

        # we ignore bundle product
        if self.tree_html.xpath("//div[@class='js-about-bundle-wrapper']") or \
                        "WalmartMainBody DynamicMode wmBundleItemPage" in self.page_raw_text:
            self.is_bundle_product = True

        # we ignore video product
        if self.tree_html.xpath("//div[@class='VuduItemBox']"):
            self.failure_type = "Video on Demand"

        # we ignore non standard product(v1) like gift card for now
        if self.tree_html.xpath("//body[@id='WalmartBodyId']") and not self.tree_html.xpath\
                        ("//form[@name='SelectProductForm']"):
            if self.tree_html.xpath("//div[@class='PageTitle']/h1/text()") and "eGift Card" in self.tree_html.xpath("//div[@class='PageTitle']/h1/text()")[0]:
                self.failure_type = "E-Card"

        # we ignore incomplete product like http://www.walmart.com/ip/39783867
        if re.findall(r"<!(-+) preparation (-+)>", self.page_raw_text):
            self.failure_type = "Incomplete"

        try:
            if "/cp/" in self._canonical_link():
                self.failure_type = "Invalid url"
        except:
            if "/cp/" in self.product_page_url:
                self.failure_type = "Invalid url"

        try:
            if "/browse/" in self._canonical_link():
                self.failure_type = "Invalid url"
        except:
            if "/browse/" in self.product_page_url:
                self.failure_type = "Invalid url"

        # check existence of "We can't find the product you are looking for, but we have similar items for you to consider."
        text_list = self.tree_html.xpath("//body//text()")
        text_contents = " " .join(text_list)

        if "We can't find the product you are looking for, but we have similar items for you to consider." in text_contents:
            self.failure_type = "404"

        product_name = self._product_name()

        # If there is no product name, return failure
        if not product_name:
            self.failure_type = "No product name"
            return self.failure_type

        return self.failure_type

    def _version(self):
        """Determines if walmart page being read (and version of extractor functions
            being used) is old or new design.
        Returns:
            "Walmart v1" for old design
            "Walmart v2" for new design
        """
        if self.use_electrode_api:
            return 'electrode'

        # using the "keywords" tag to distinguish between page versions.
        # In old version, it was capitalized, in new version it's not
        if self.tree_html.xpath("//meta[@name='keywords']/@content"):
            return "Walmart v2"
        if self.tree_html.xpath("//meta[@name='Keywords']/@content"):
            return "Walmart v1"

        # we could not decide
        return 'Walmart v2'

    def _remove_html(self, s):
        return re.sub('<.*?>', '', s).strip()

    def _ingredients(self):
        if self.is_alternative:
            for v in self.product_info_json.get('product', {}).get('idmlMap', {}).values():
                ing = v.get('modules', {}).get('Ingredients', {}).get('ingredients', {}).get('values')
                if ing:
                    return [i.strip() for i in ing[0].split(',')]

            ingredients = self.selected_product.get('productAttributes', {}).get('ingredients')
            if ingredients and not ingredients.lower() in ['na', 'no']:
                return [i.strip() for i in ingredients.split(',')]

    def _warnings(self):
        if self.is_alternative:
            for v in self.product_info_json.get('product', {}).get('idmlMap', {}).values():
                warn = v.get('modules', {}).get('Warnings', {}).get('warnings', {}).get('values')
                if not warn:
                    warn = v.get('modules', {}).get('Warnings', {}).get('prop_65_warning_text', {}).get('values')
                if warn:
                    return warn[0]

            return self.selected_product.get('productAttributes', {}).get('warnings')

        warnings = self.tree_html.xpath("//section[contains(@class,'warnings')]/p[2]")

        if not warnings:
            warnings = self.tree_html.xpath("//section[contains(@class,'js-warnings')]/p[1]")

        if warnings:
            warnings = warnings[0]

            header = self.tree_html.xpath("//section[contains(@class,'js-warnings')]/p[1]/b/text()")

            if not header:
                header = warnings.xpath('./strong/text()')

            if header and 'Warning Text' in header[0]:
                for txt in warnings.xpath('./text()'):
                    if self._remove_html(txt):
                        return self._remove_html(txt)

    def _directions(self):
        if self.is_alternative:
            for v in self.product_info_json.get('product', {}).get('idmlMap', {}).values():
                inst = v.get('modules', {}).get('Directions', {}).get('instructions', {}).get('values')
                if inst:
                    return inst[0]

            return self.selected_product.get('productAttributes', {}).get('instructions')

        directions = self.tree_html.xpath("//section[contains(@class,'directions')]")

        if directions:
            directions = directions[0]

            directions_text = ''

            for e in directions:
                text_content = e.text_content().strip()

                if not e.tag == 'h3' and text_content and not text_content == 'Instructions:':
                    directions_text += re.sub('\s*<[^>]*>\s*Instructions:\s*<[^>]*>\s*', '', html.tostring(e)).strip()

            return self._remove_html(directions_text)

    def _canonical_link(self):
        canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

        if re.match("https?://www.walmart.com", canonical_link):
            return canonical_link
        else:
            return "http://www.walmart.com" + canonical_link

    def _get_nutrition_facts(self, v, nutrition_facts_list):
        if v.get('children'):
            for vc in v.get('children'):
                self._get_nutrition_facts(vc, nutrition_facts_list)
        else:
            nutrition_facts_list.append(v)

    def _nutrition_facts(self):
        self._extract_terra_firma()

        nutrition_facts = deep_search('NutritionFacts', self.terra_firma)

        if nutrition_facts:
            nutrition_facts = nutrition_facts[0] 

            nutrition_facts_list = []

            for k,v in nutrition_facts.iteritems():
                self._get_nutrition_facts(v, nutrition_facts_list)

            return nutrition_facts_list

    def _nutrition_fact_text_health(self):
        self._extract_terra_firma()

        if not self.terra_firma:
            return 2

        elif self._nutrition_facts():
            return 1

        return 0

    def _drug_facts(self):
        drug_facts = {}
        active_ingredient_list = []
        warnings_list = []
        directions_list = []
        inactive_ingredients = []
        questions_list = []

        try:
            div_active_ingredients = self.tree_html.xpath("//section[@class='active-ingredients']/div[@class='ingredient clearfix']")

            if div_active_ingredients:
                for div_active_ingredient in div_active_ingredients:
                    active_ingredient_list.append({"ingredients": div_active_ingredient.xpath("./div[@class='column1']")[0].text_content().strip(), "purpose": div_active_ingredient.xpath("./div[@class='column2']")[0].text_content().strip()})
                drug_facts["Active Ingredients"] = active_ingredient_list
        except:
            pass

        try:
            ul_warnings = self.tree_html.xpath("//h6[@class='section-heading warnings']/following-sibling::*[1]")

            if ul_warnings:
                warnings_title_list = ul_warnings[0].xpath("./li/strong/text()")
                warnings_text_list = ul_warnings[0].xpath("./li/text()")

                for index, warning_title in enumerate(warnings_title_list):
                    warnings_list.append([warning_title.strip(), warnings_text_list[index].strip()])

                if warnings_list:
                    drug_facts["Warnings"] = warnings_list
        except:
            pass

        try:
            p_directions = self.tree_html.xpath("//h6[@class='section-heading' and contains(text(), 'Directions')]/following-sibling::*[1]")

            if p_directions:
                directions_text = p_directions[0].text_content().strip()
                drug_facts["Directions"] = directions_text
        except:
            pass

        try:
            p_inactive_ingredients = self.tree_html.xpath("//h6[@class='section-heading' and contains(text(), 'Inactive Ingredients')]/following-sibling::*[1]")

            if p_inactive_ingredients:
                inactive_ingredients = p_inactive_ingredients[0].text_content().strip().split(", ")

                if inactive_ingredients:
                    drug_facts["Inactive Ingredients"] = inactive_ingredients
        except:
            pass

        try:
            p_questions = self.tree_html.xpath("//h6[@class='section-heading' and contains(text(), 'Questions?')]/following-sibling::*[1]")

            if p_questions:
                questions_text = p_questions[0].text_content().strip()
                drug_facts["Questions?"] = questions_text
        except:
            pass

        if not drug_facts:
            return None

        return drug_facts

    def _drug_fact_count(self):
        drug_fact_key_list = ["Active Ingredients", "Directions", "Inactive Ingredients", "Questions?", "Warnings"]

        drug_facts = self._drug_facts()

        try:
            count = 0

            for key in drug_fact_key_list:
                if key in drug_facts:
                    if isinstance(drug_facts[key], str):
                        count = count + 1
                    else:
                        count = count + len(drug_facts[key])

            return count
        except:
            return 0

        return 0

    def _drug_fact_text_health(self):
        drug_fact_main_key_list = ["Active Ingredients", "Directions", "Inactive Ingredients", "Warnings"]

        drug_facts = self._drug_facts()

        if not drug_facts:
            return 0

        for key in drug_fact_main_key_list:
            if key not in drug_facts:
                return 1
            else:
               if len(drug_facts[key]) == 0:
                   return 1

        return 2

    def _supplement_facts(self):
        supplement_facts = None

        if not self.tree_html.xpath("//div[@class='supplement-section']"):
            return None

        supplement_facts = {"supplement-header": None, "supplement-facts": None}

        supplement_head_block = self.tree_html.xpath("//div[@class='supplement-header']/div")
        supplement_head = []

        for item in supplement_head_block:
            head_string = item.text_content().strip()

            if not head_string:
                continue

            index = re.search("\d", head_string)

            if index:
                key = head_string[:index.start()].strip()
                value = head_string[index.start():].strip()
            else:
                key = head_string
                value = None

            supplement_head.append([key, value])

        supplement_facts["supplement-header"] = supplement_head

        supplement_table_block = self.tree_html.xpath("//table[@class='supplement-table']/tbody/tr")
        supplement_table_info = []

        for item in supplement_table_block:
            data = item.xpath("./td/text()")

            try:
                key = item.xpath("./td[1]/text()")[0].strip()

                if not key:
                    continue

                absolute_value = item.xpath("./td[2]/text()")
                relative_value = item.xpath("./td[3]/text()")

                if absolute_value:
                    absolute_value = absolute_value[0].strip()
                else:
                    absolute_value = ""

                if relative_value:
                    relative_value = relative_value[0].strip()
                else:
                    relative_value = ""

                supplement_table_info.append([data[0], {"absolute": absolute_value, "relative": relative_value}])
            except:
                continue

        supplement_facts["supplement-facts"] = supplement_table_info

        return supplement_facts

    def _supplement_fact_count(self):
        supplement_facts = self._supplement_facts()

        if not supplement_facts:
            return 0

        return len(supplement_facts["supplement-header"]) + len(supplement_facts["supplement-facts"])

    def _supplement_fact_text_health(self):
        if not self.tree_html.xpath("//div[@class='supplement-section']"):
            return 0

        supplement_fact_count = self._supplement_fact_count()
        element_count = len(self.tree_html.xpath("//div[@class='supplement-header']/div")) + len(self.tree_html.xpath("//table[@class='supplement-table']/tbody/tr"))

        if supplement_fact_count != element_count:
            return 1

        supplement_facts = self._supplement_facts()

        if len(supplement_facts["supplement-header"]) < 2:
            return 1

        for header in supplement_facts["supplement-header"]:
            if not header[1].strip():
                return 1

        for fact in supplement_facts["supplement-facts"]:
            if not fact[1]["absolute"].strip():
                return 1

        return 2

    def _comparison_chart(self):
        if self.tree_html.xpath('//button[text()="Comparison Chart"]'):
            return 1
        return 0

    def _btv(self):
        if self.tree_html.xpath('//div[contains(@class,"btv-module")]'):
            return 1
        return 0

    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        """Cleans a piece of text of html entities
        Args:
            original text (string)
        Returns:
            text stripped of html entities
        """

        return re.sub("&nbsp;|&#160;|\s+", " ", text).strip()

    def _clean_html(self, html):
        html = self._clean_text(html)
        #html = re.sub('<(\S+)[^>]*>', r'<\1>', html)
        html = re.sub('\s+', ' ', html)
        html = re.sub('> <', '><', html)
        return html

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service
    #
    # data extracted from product page
    # their associated methods return the raw data
    """Contains as keys all data types that can be extracted by this class
    Their corresponding values are the methods of this class that handle the extraction of
    the respective data types. All these methods must be defined (except for 'load_time' value)

    The keys of this structure are data types that can be extracted solely from the page source
    of the product page.
    """

    DATA_TYPES = {
        # Info extracted from product page
        "site_version": _site_version,
        "upc": _upc,
        "wupc": _wupc,
        "gtin": _gtin,
        "product_name": _product_name,
        "product_id": _product_id,
        "walmart_no": _walmart_no,
        "meta_tags": _meta_tags,
        "meta_tag_count": _meta_tag_count,
        "canonical_link": _canonical_link,
        "brand": _meta_brand_from_tree,
        "description": _short_description_wrapper,
        "seller_ranking": _seller_ranking,
        "long_description": _long_description_wrapper,
        "shelf_description": _shelf_description,
        "variants": _variants,
        "swatches": _swatches,
        "swatch_image_missing": _swatch_image_missing,
        "bundle": _bundle,
        "bundle_components": _bundle_components,
        "ingredients": _ingredients,
        "directions" : _directions,
        "warnings" : _warnings,
        "nutrition_fact_text_health": _nutrition_fact_text_health,
        "drug_facts": _drug_facts,
        "drug_fact_count": _drug_fact_count,
        "drug_fact_text_health": _drug_fact_text_health,
        "supplement_facts": _supplement_facts,
        "supplement_fact_count": _supplement_fact_count,
        "supplement_fact_text_health": _supplement_fact_text_health,
        "price": _price_from_tree,
        "price_amount": _price_amount,
        "price_currency": _price_currency,
        "htags": _htags_from_tree,
        "model": _model,
        "model_meta": _model_meta,
        "mpn": _mpn,
        "specs": _specs,
        "rollback": _rollback,
        "free_pickup_today": _free_pickup_today,
        "buying_option": _buying_option,
        "in_stores": _in_stores,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "marketplace": _marketplace,
        "marketplace_prices" : _marketplace_prices,
        "marketplace_sellers": _marketplace_sellers,
        "marketplace_out_of_stock": _marketplace_out_of_stock,
        "marketplace_lowest_price" : _marketplace_lowest_price,
        "pdf_urls" : _pdf_urls,
        "primary_seller": _primary_seller,
        "seller_id": _seller_id,
        "us_seller_id": _us_seller_id,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,
        "no_longer_available": _no_longer_available,
        "temporary_unavailable": _temporary_unavailable,
        "temp_price_cut": _temp_price_cut,
        "video_urls": _video_urls,
        "best_seller_category": _best_seller_category,
        "flixmedia": _flixmedia,
        "rich_content": _rich_content,
        "comparison_chart": _comparison_chart,
        "btv": _btv,
        "image_urls": _image_urls,
        "image_res": _image_res,
        "image_dimensions": _image_dimensions,
        "zoom_image_dimensions": _zoom_image_dimensions,
        "image_alt_text": _image_alt_text,
        "categories": _categories,
        "shelf_links_by_level": _shelf_links_by_level,
        "scraper": _version,
        }

    # special data that can't be extracted from the product page
    # associated methods return already built dictionary containing the data
    """Contains as keys all data types that can be extracted by this class
    Their corresponding values are the methods of this class that handle the extraction of
    the respective data types. All these methods must be defined (except for 'load_time' value)

    The keys of this structure are data types that can't be extracted from the page source
    of the product page and need additional requests.
    """

    DATA_TYPES_SPECIAL = {
    }


if __name__=="__main__":
    WD = WalmartScraper()
    print WD.main(sys.argv)
