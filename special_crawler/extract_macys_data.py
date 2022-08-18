#!/usr/bin/python

import re
import json
from lxml import html
from extract_data import Scraper

from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.macys_variants import MacysVariants, normalize_product_json_string


class MacysScraper(Scraper):
    ##########################################
    # PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www(1)\.macys\.com/shop/(.*)"

    REVIEW_URL = 'http://macys.ugc.bazaarvoice.com/7129aa/{}/reviews.djs?format=embeddedhtml'

    WEBCOLLAGE_POWER_PAGE = 'https://scontent.webcollage.net/macys/power-page?ird=true&channel-product-id={}'

    HEADERS = {
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en-US,en;q=0.8,nl;q=0.6,fr;q=0.4',
        'upgrade-insecure-requests': '1',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'authority': 'www.macys.com'
    }

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.mv = MacysVariants()

        self.product_json = {}
        self.is_product_json_checked = False

        self.is_bundle = False

    def select_browser_agents_randomly(self):
        return 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots) Chrome'

    def check_url_format(self):
        m = re.match(r"https?://www1?\.macys\.com/shop/(.*)", self.product_page_url)
        return bool(m)

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries(use_session=True)

    def _extract_product_json(self):
        if self.is_product_json_checked:
            return self.product_json

        self.is_product_json_checked = True

        try:
            if self.is_bundle:
                product_json = self.tree_html.xpath("//script[@id='pdpMainData' and @type='application/json']/text()")
                if product_json:
                    self.product_json = json.loads(product_json[0])['productDetail']
            else:
                product_json = self.tree_html.xpath(
                    "//script[@id='productMainData' and @type='application/json']/text()"
                )
                if product_json:
                    self.product_json = json.loads(normalize_product_json_string(product_json[0]))
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', str(e))

    def not_a_product(self):
        if len(self.tree_html.xpath("//*[contains(@class, 'productTitle')]")) < 1:
            return True

        if len(self.tree_html.xpath("//div[@id='viewCollectionItemsButton']")) > 0:
            self.is_bundle = True

        self.mv.setupCH(self.tree_html, self.is_bundle)

        self._extract_product_json()

        return False

    def _pre_scrape(self):
        self._extract_webcollage_contents()

    ##########################################
    # CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//*[contains(@class,"productID")]'
                                          '[contains(text(), "Web ID:")]/text()')
        if product_id:
            product_id = ''.join([c for c in product_id[0] if c.isdigit()])
        return product_id

    ##########################################
    # CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        prod_name = self.tree_html.xpath("//h1[contains(@class, 'productName')]//text()")

        if not prod_name:
            prod_name = self.tree_html.xpath("//h1[@id='productTitle']/text()")

        return prod_name[0].strip()

    def _upc(self):
        upc = None
        try:
            variants = self._variants()
        except:
            return self.product_json['upcMap'][self._product_id()][0]['upc']

        if not variants:
            upc = re.findall(r'"upc": "(.*?)",', html.tostring(self.tree_html), re.DOTALL)[0]
        if variants:
            upc = variants[0]["upc"]

        return upc.zfill(12)

    def _features(self):
        rows = self.tree_html.xpath("//div[@id='prdDesc']//ul[contains(@class,'bullets')]/li")
        line_txts = []
        for row in rows:
            txt = "".join([r for r in row.xpath(".//text()") if len(self._clean_text(r)) > 0]).strip()
            if len(txt) > 0:
                line_txts.append(txt)
        if len(line_txts) < 1:
            return None
        return line_txts

    def _description(self):
        description = self.tree_html.xpath("//div[@id='longDescription']")[0].text_content().strip()

        if description:
            return description

    def _description_helper(self):
        description = ""
        rows = self.tree_html.xpath("//div[@id='prdDesc']//div[@itemprop='description']/text()")
        rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
        if len(rows) > 0:
            description += "\n".join(rows)
        if len(description) < 1:
            description = ""
            rows = self.tree_html.xpath("//div[@id='productDetails']//text()")
            rows = [self._clean_text(r) for r in rows if len(self._clean_text(r)) > 0]
            if len(rows) > 0:
                description += "\n".join(rows)
            if len(description) < 1:
                return None
            if description.startswith("Product Details"):
                description = description.replace("Product Details\n", "")
        return description

    def _long_description(self):
        return html.tostring(self.tree_html.xpath("//ul[@id='bullets']")[0])

    def _variants(self):
        return self.mv._variants()

    def _swatches(self):
        return self.mv._swatches()

    def _no_longer_available(self):
        if 'Not Available' in self.tree_html.xpath('//title//text()')[0]:
            return 1

        currently_unavailable = self.tree_html.xpath("//span[contains(text(),'This product is currently unavailable')]")
        if currently_unavailable:
            return 1

        return 0

    ##########################################
    # CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if not self.product_json:
            return self.tree_html.xpath('//div[@class="productImageSection"]/img/@src')

        image_url = self.product_json['imageUrl']

        try:
            if self._no_image(image_url):
                return None
        except Exception, e:
            print "WARNING: ", e.message

        if self.is_bundle:
            image_url_frags = []

            for _images in re.findall('MACYS.pdp.memberAdditionalImages\[\d+\] = "([^"]*)"', self.page_raw_text):
                image_url_frags += _images.split(',')

            for _images in re.findall('MACYS.pdp.additionalImages\[\d+\] = ({[^}]*})', self.page_raw_text):
                for frag_string in json.loads(_images).itervalues():
                    image_url_frags += frag_string.split(',')

        else:
            main_image = self.product_json['images']['imageSource']
            additional_images = self.product_json['images']['additionalImages']

            image_url_frags = [main_image] + additional_images
            
            main_color = None

            for i in self.product_json['images']['colorwayPrimaryImages'].items():
                if i[1] == main_image:
                    main_color = i[0]

            colorway_additional_images = self.product_json['images']['colorwayAdditionalImages']

            if main_color in colorway_additional_images:
                image_url_frags += colorway_additional_images[main_color].split(',')
            elif colorway_additional_images and not additional_images:
                additional_images = sorted([i.split(',') for i in colorway_additional_images.values()], key=len)
                additional_images = [i for i in additional_images if len(i) == len(additional_images[-1])]
                image_url_frags += additional_images[0]

        image_urls_tmp = map(
            lambda f: "http://slimages.macysassets.com/is/image/MCY/products/%s?wid=860&hei=1053" % f,
            image_url_frags
        )
        image_urls = []
        # Remove duplicates
        for image_url in image_urls_tmp:
            if image_url not in image_urls:
                image_urls.append(image_url)
        return image_urls

    def _video_count(self):
        if self.product_json.get('videoID'):
            return 1

        return 0

    def _bundle(self):
        return self.is_bundle

    def _size_chart(self):
        if self.product_json.get('sizesList') or \
                self.product_json.get('sizeChart', {}).get('sizeChartCanvasId'):
            return 1
        return 0

    ##########################################
    # CONTAINER : SELLERS
    ##########################################

    def _price(self):
        if self._site_online_out_of_stock():
            return "out of stock - no price given"

        price_range = self.tree_html.xpath('//span[contains(@class, "fullrange")]/text()')
        if price_range:
            return price_range[0].replace('\n', ' ').strip()

        if self.product_json.get('salePrice'):
            return '$' + self.product_json['salePrice']
        else:
            return '$' + self.product_json['regularPrice']

    def _in_stores(self):
        script = " ".join(self.tree_html.xpath("//script//text()"))
        available = re.findall(r"MACYS\.pdp\.productAvailable = \"(.*?)\"", script, re.DOTALL)
        if len(available) > 0:
            if available[0] == "true":
                return 1
        return 0

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self._no_longer_available():
            return 1

        rows = self.tree_html.xpath("//ul[@class='similarItems']//li//text()")
        if "This product is currently unavailable" in rows:
            return 1
        return 0

    ##########################################
    # CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        if self.is_bundle:
            categories = self.tree_html.xpath('//meta[@itemprop="breadcrumb"]/@content')[0].split('-')
        elif self.product_json:
            categories = self.product_json['breadCrumbCategory'].split('-')
        else:
            categories = self.tree_html.xpath('//div[@id="breadCrumbsDiv"]//a[@class="bcElement"]/text()')

        if categories:
            return [self._clean_text(c) for c in categories]

    def _brand(self):
        brand = self.tree_html.xpath('//a[contains(@class, "brandNameLink")]/text()')

        if not brand:
            brand = self._product_name().split(u'\xae')

        if brand:
            return brand[0]

        return guess_brand_from_first_words(self._product_name())

    ##########################################
    # HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("&nbsp;", " ", text).strip()

    ##########################################
    # RETURN TYPES
    ##########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "features": _features,
        "description": _description,
        "upc": _upc,
        "long_description": _long_description,
        "variants": _variants,
        "swatches": _swatches,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "size_chart": _size_chart,
        "bundle": _bundle,

        # CONTAINER : SELLERS
        "price": _price,
        "in_stores": _in_stores,
        "marketplace": _marketplace,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
    }
