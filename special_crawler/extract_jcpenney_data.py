#!/usr/bin/python

import re
import ast
import json
import requests
import traceback

from lxml import html
from extract_data import Scraper

import spiders_shared_code.canonicalize_url
from spiders_shared_code.jcpenney_variants import JcpenneyVariants


def catch_json_decode_exception(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except (ValueError, IndexError):
            print(
                '[WARNING] Can not load `{}` data: {}'.format(func.__name__, traceback.format_exc())
            )
    return wrapper

class JcpenneyScraper(Scraper):

    # #########################################
    # ############## PREP
    # #########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.jcpenney.com/*/prod.jump?ppId=<prod-id> or " \
                          "http(s)://www.jcpenney.com/p/*"

    REVIEW_URLS = ["http://jcpenney.ugc.bazaarvoice.com/1573-en_us/{}/reviews.djs?format=embeddedhtml",
        "http://jcpenney.ugc.bazaarvoice.com/1573redes2/{}/reviews.djs?format=embeddedhtml",
        "http://sephora.ugc.bazaarvoice.com/8723jcp/{}/reviews.djs?format=embeddedhtml"]

    STOCK_STATUS_URL = "http://www.jcpenney.com/jsp/browse/pp/graphical/graphicalSKUOptions.jsp?fromEditBag=&" \
                       "fromEditFav=&grView=&_dyncharset=UTF-8&_dynSessConf=-{0}&sucessUrl=%2Fjsp" \
                       "%2Fbrowse%2Fpp%2Fgraphical%2FgraphicalSKUOptions.jsp%" \
                       "3FfromEditBag%3D%26fromEditFav%3D%26grView%3D&_D%3AsucessUrl=+&" \
                       "ppType=regular&_D%3AppType=+&shipToCountry=US&_D%3AshipToCountry=+&" \
                       "ppId={1}&_D%3AppId=+&selectedLotValue=1+OZ+EAU+DE+PARFUM&_D%3AselectedLotValue=+" \
                       "&_DARGS=%2Fdotcom%2Fjsp%2Fbrowse%2Fpp%2Fgraphical%2FgraphicalLotSKUSelection.jsp"

    SIZE_CHART_AND_FIT_GUIDE_URL = "http://www.jcpenney.com/jsp/browse/pp/knowledgeAssistantContainerForPP.jsp?kaId={kaid}&isFromPOSF="

    SPEC_URL = "http://www.jcpenney.com/v1/product-specifications/{}"

    MOBILE_VARIANTS_URL = "http://m.jcpenney.com/v4/products/{product_id}"
    VARIANTS_PRICE_URL = "http://m.jcpenney.com/v4/products/{product_id}/pricing/items"
    AVAILABILITY_URL = "http://m.jcpenney.com/v4/products/{product_id}/inventory"

    MOBILE_USER_AGENT = "Mozilla/5.0 (iPad; CPU OS 11_0 like Mac OS X) AppleWebKit/604.1.34 " \
                        "(KHTML, like Gecko) Version/11.0 Mobile/15A5341f Safari/604.1"
    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)" \
                 " Chrome/65.0.3325.181 Safari/537.36"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.jv = JcpenneyVariants()
        self.is_analyze_media_contents = False
        self.video_urls = None
        self.video_count = 0
        self.pdf_urls = None
        self.pdf_count = 0
        self.size_chart_url_link = None
        self.fit_guide_url_link = None
        self.product_json = {}
        self.category_json = {}
        self.spec_info = {}

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.jcpenney(url)

    def check_url_format(self):
        m = re.match('https?://www.jcpenney.com/.*/prod.jump\?ppId=.+', self.product_page_url)
        n = re.match('https?://www.jcpenney.com/p/.*', self.product_page_url)
        return bool(m or n)

    def _extract_page_tree(self):
        for _ in range(3):
            self._extract_page_tree_with_retries(use_session=True, save_session=True, max_retries=2)

            if not self.not_a_product():
                return

    def _pre_scrape(self):
        self._get_product_json()
        self._get_specs_info()
        availability_dict = self._get_availability_dict()
        prices_json = self._get_prices()
        self.jv.setupCH(
            self.tree_html,
            product_json=self.product_json,
            availability_dict=availability_dict,
            prices_json=prices_json
        )

    def not_a_product(self):
        try:
            if self.tree_html.xpath('//div[@data-automation-id="product-title"]'):
                return False
        except:
            print traceback.format_exc()
            return True

        itemtype = self.tree_html.xpath('//div[@class="pdp_details"]')

        if not itemtype:
            if self.tree_html.xpath("//div[@class='product_row bottom_border flt_wdt']"):
                self.ERROR_RESPONSE["failure_type"] = "Bundle"
                return True

        if not self._product_name():
            self.ERROR_RESPONSE["failure_type"] = "Not a product"
            return True

        self.analyze_media_contents()
        self._extract_size_chart_and_fit_guide()
        self._extract_category_json()

    # #########################################
    # ############## CONTAINER : NONE
    # #########################################

    @catch_json_decode_exception
    def _extract_category_json(self):
        breadcrumb_info = self.tree_html.xpath("//div[@id='breadcrumbResponse']/text()")
        if breadcrumb_info:
            self.category_json = json.loads(breadcrumb_info[0]).get('breadcrumbs', {})

    @catch_json_decode_exception
    def _get_product_json(self):
        # try to get product json from the page
        product_json = re.search('var productJSON=({.*?})[;<]', html.tostring(self.tree_html))
        if product_json:
            self.product_json = json.loads(product_json.group(1))
        else:
            # if it's not there, fetch it from url
            req = self._request(
                self.MOBILE_VARIANTS_URL.format(product_id=self._product_id()),
                session=self.session,
                headers={'User-Agent': self.MOBILE_USER_AGENT}
            )
            if req.status_code == 200:
                self.product_json = req.json()

    @catch_json_decode_exception
    def _get_availability_dict(self):
        # try to load availability json from the page
        availability_json_data = self.tree_html.xpath('//div[@id="inventoryResponse"]/text()')
        if availability_json_data:
            availability_json = json.loads(availability_json_data[0].strip())
        else:
            # if it's not there, fetch it from url
            req = self._request(
                self.AVAILABILITY_URL.format(product_id=self._product_id()),
                session=self.session,
                headers={'User-Agent': self.MOBILE_USER_AGENT}
            )
            if req.status_code == 200:
                availability_json = req.json()
        availability_dict = {}
        if isinstance(availability_json, dict):
            availability_json = availability_json.get('inventory', [])

        for lot in availability_json:
            availability_dict[lot.get('id')] = lot.get('atp')
        return availability_dict

    @catch_json_decode_exception
    def _get_prices(self):
        prices = {}

        req = self._request(
            self.VARIANTS_PRICE_URL.format(product_id=self._product_id()),
            session=self.session,
            headers={'User-Agent': self.MOBILE_USER_AGENT}
        )
        if req.status_code == 200:
            prices_json = req.json()

            for v in prices_json.get('data', []):
                # http://lewk.org/blog/python-dictionary-optimizations
                sku_id = str(v.get('id'))
                price = min([price.get('min') for price in v.get('amounts')])
                prices[sku_id] = price

        return prices

    @catch_json_decode_exception
    def _get_specs_info(self):
        req = self._request(
            self.SPEC_URL.format(self._site_id()),
            session=self.session,
        )
        if req.status_code == 200:
            spec_content = req.json()
            if spec_content:
                self.spec_info = spec_content[0]['attributes']

    def _product_id(self):
        prod_id = re.search('prod\.jump\?ppId=(.+?)$', self.product_page_url.split('&')[0])

        if prod_id:
            return prod_id.group(1)

        url = self.product_page_url.split('?')[0]
        return url.split('/')[-1]

    def _site_id(self):
        site_id = re.search('"webId":"(\d+)",', html.tostring(self.tree_html))
        return site_id.group(1) if site_id else None

    # #########################################
    # ############## CONTAINER : PRODUCT_INFO
    # #########################################

    def _product_name(self):
        title = self.tree_html.xpath('//h1[@itemprop="name"]/text()') or \
                self.tree_html.xpath('//h1[@class="ProductTitle-productTitle"]/text()') or \
                self.tree_html.xpath('//meta[@property="og:title"]/@content') or \
                self.tree_html.xpath('//title/text()')
        if title:
            return title[0].strip()

    def _description(self):
        if self.tree_html.xpath("//div[@id='longCopyCont']"):
            description_html_text = html.tostring(
                self.tree_html.xpath("//div[@id='longCopyCont']")[0]
            )

            if description_html_text.startswith('<div id="longCopyCont" class="pdp_brand_desc_info" itemprop="description">'):
                short_description_start_index = len('<div id="longCopyCont" class="pdp_brand_desc_info" itemprop="description">')
            else:
                short_description_start_index = 0

            if description_html_text.find('<div style="page-break-after: always;">') > 0:
                short_description_end_index = description_html_text.find('<div style="page-break-after: always;">')
            elif description_html_text.find('<ul>') > 0:
                short_description_end_index = description_html_text.find('<ul>')
            elif description_html_text.find('<p>&#9679;') > 0:
                short_description_end_index = description_html_text.find('<p>&#9679;')
            elif short_description_start_index > 0:
                short_description_end_index = description_html_text.rfind("</div>")
            else:
                short_description_end_index = len(description_html_text)

            return description_html_text[short_description_start_index:short_description_end_index].strip()
        elif self.product_json:
            return self.product_json.get('description') or self.product_json.get('lots')[0].get('description')

    def _long_description(self):
        long_description_start_index = ''
        if self.tree_html.xpath("//div[@id='longCopyCont']"):
            description_html_text = html.tostring(self.tree_html.xpath("//div[@id='longCopyCont']")[0])

            if long_description_start_index:
                long_description_end_index = description_html_text.rfind("</div>")
                return self._clean_text( description_html_text[long_description_start_index:long_description_end_index])

            if description_html_text.find('<div style="page-break-after: always;">') > 0:
                long_description_start_index = description_html_text.find('<div style="page-break-after: always;">')
                long_description_start_index = description_html_text.find('</div>', long_description_start_index) + len("</div>")

            elif description_html_text.find('<ul>') > 0:
                long_description_start_index = description_html_text.find('<ul>')

            elif description_html_text.find('<p>&#9679;') > 0:
                long_description_start_index = description_html_text.find('<p>&#9679;')

            if long_description_start_index:
                long_description_end_index = description_html_text.rfind("</div>")
                return self._clean_text(description_html_text[long_description_start_index:long_description_end_index])

    @catch_json_decode_exception
    def _specs(self):
        specs = {}
        for elem in self.spec_info:
            spec_name = elem['name']
            spec_value = elem['value']
            specs[spec_name] = spec_value
        return specs

    def _model(self):
        model = re.findall('"modelNumber":"(.*?)",', html.tostring(self.tree_html))
        if model:
            return model[0]

    def _features(self):
        features_info = re.search('<li>Features: (.*?)</li>', html.tostring(self.tree_html))
        if features_info:
            return features_info.group(1).split(', ')
        else:
            features = self.tree_html.xpath('//li[contains(@class, "specifications__list__details")]')
            if features:
                for feature in features:
                    if feature.xpath('.//div[contains(@class, "details--name")]/text()')[0] == 'FEATURES':
                        return feature.xpath('.//div[contains(@class, "details--value)"]/text()')[0].split(',')
            else:
                specs = self._specs()
                if specs and 'FEATURES' in specs:
                    return specs['FEATURES'].split('|')

    def _variants(self):
        return self.jv.variants()

    def _swatches(self):
        return self.jv.swatches()

    def _no_longer_available(self):
        return 0

    # #########################################
    # ############## CONTAINER : PAGE_ATTRIBUTES
    # #########################################

    def _image_urls(self):
        image_ids = re.search('var imageName = "(.+?)";', html.tostring(self.tree_html))
        if image_ids:
            image_ids = image_ids.group(1).split(",")
        elif self.product_json:
            image_ids = [image.get('url').split('/')[-1] for image in self.product_json.get('images')]
        image_urls = []
        base_image_url = 'http://s7d2.scene7.com/is/image/JCPenney/{}?fmt=jpg' \
              '&op_usm=.4,.8,0,0&resmode=sharp2&wid=1600&hei=1600'

        for image_id in image_ids:
            image_url = base_image_url.format(image_id)
            if not image_url in image_urls:
                image_urls.append(image_url)

        return image_urls if image_urls else None

    def analyze_media_contents(self):
        if self.is_analyze_media_contents:
            return

        self.is_analyze_media_contents = True

        page_raw_text = html.tostring(self.tree_html)

        #check pdf
        try:
            pdf_urls = re.findall(r'href="(.+\.pdf?)"', page_raw_text)

            if not pdf_urls:
                raise Exception

            for index, url in enumerate(pdf_urls):
                if not url.startswith("http://"):
                    pdf_urls[index] = "http://www.jcpenney.com" + url

            self.pdf_urls = pdf_urls
            self.pdf_count = len(self.pdf_urls)
        except:
            pass

        video_urls_list = None

        try:
            video_urls_list = re.findall('videoIds.push\((.*?)\);\n', html.tostring(self.tree_html), re.DOTALL)
            video_urls_list = [ast.literal_eval(video_url)["url"] for video_url in video_urls_list]
        except:
            video_urls_list = None

        #check media contents window existence
        if self.tree_html.xpath("//a[@class='InvodoViewerLink']"):

            media_contents_window_link = self.tree_html.xpath("//a[@class='InvodoViewerLink']/@onclick")[0]
            media_contents_window_link = re.search("window\.open\('(.+?)',", media_contents_window_link).group(1)

            contents = self.load_page_from_url_with_number_of_retries(media_contents_window_link)

            #check media contents
            if "webapps.easy2.com" in media_contents_window_link:
                try:
                    media_content_raw_text = re.search('Demo.instance.data =(.+?)};\n', contents).group(1) + "}"
                    media_content_json = json.loads(media_content_raw_text)

                    video_lists = re.findall('"Path":"(.*?)",', media_content_raw_text)

                    video_lists = [media_content_json["UrlAddOn"] + url for url in video_lists if url.strip().endswith(".flv") or url.strip().endswith(".mp4/")]
                    video_lists = list(set(video_lists))

                    if not video_lists:
                        raise Exception

                    self.video_urls = video_lists
                    self.video_count = len(self.video_urls)
                except:
                    pass
            elif "content.webcollage.net" in media_contents_window_link:
                webcollage_link = re.search("document\.location\.replace\('(.+?)'\);", contents).group(1)
                contents = self.load_page_from_url_with_number_of_retries(webcollage_link)
                webcollage_page_tree = html.fromstring(contents)

                try:
                    webcollage_media_base_url = re.search('<div data-resources-base="(.+?)"', contents).group(1)

                    videos_json = '{"videos":' + re.search('{"videos":(.*?)]}</div>', contents).group(1) + ']}'
                    videos_json = json.loads(videos_json)

                    video_lists = [webcollage_media_base_url + videos_json["videos"][0]["src"]["src"][1:]]
                    self.wc_video = 1
                    self.video_urls = video_lists
                    self.video_count = len(self.video_urls)
                except:
                    pass

                try:
                    if webcollage_page_tree.xpath("//div[@class='wc-ms-navbar']//span[text()='360 Rotation']") or webcollage_page_tree.xpath("//div[@class='wc-ms-navbar']//span[text()='360/Zoom']"):
                        self.wc_360 = 1
                except:
                    pass

                try:
                    if webcollage_page_tree.xpath("//ul[contains(@class, 'wc-rich-features')]"):
                        self.wc_emc = 1
                except:
                    pass

            elif "bcove.me" in media_contents_window_link:
                try:
                    brightcove_page_tree = html.fromstring(contents)
                    video_lists = [brightcove_page_tree.xpath("//meta[@property='og:video']/@content")[0]]
                    self.video_urls = video_lists
                    self.video_count = len(self.video_urls)
                except:
                    pass

        try:
            if video_urls_list:
                if not self.video_urls:
                    self.video_urls = video_urls_list
                    self.video_count = len(video_urls_list)
                else:
                    self.video_urls.extend(video_urls_list)
                    self.video_count = self.video_count + len(video_urls_list)
        except:
            pass

    def _video_urls(self):
        if self.product_json and self.product_json.get('videos'):
            return [video['url'] for video in self.product_json['videos']]

        return self.video_urls

    def _video_count(self):
        if self.product_json:
            video_urls = self._video_urls()
            return len(video_urls) if video_urls else 0

        return self.video_count

    def _pdf_urls(self):
        return self.pdf_urls

    # #########################################
    # ############## CONTAINER : REVIEWS
    # #########################################

    def _reviews(self):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        review_id = self._find_between(html.tostring(self.tree_html), 'reviewIdNew = "', '";').strip()
        if not review_id:
            review_id = self.product_json.get('valuation', {}).get('id')

        for review_url in self.REVIEW_URLS:
            self.is_review_checked = False
            super(JcpenneyScraper, self)._reviews(review_url.format(review_id or self._product_id()))
            if self.reviews:
                return self.reviews

    # #########################################
    # ############## CONTAINER : SELLERS
    # #########################################

    def _price(self):
        if self.tree_html.xpath("//div[@id='priceDetails']//span[@class='gallery_page_price flt_wdt comparisonPrice']"):
            price = self.tree_html.xpath("//div[@id='priceDetails']//span[@class='gallery_page_price flt_wdt comparisonPrice']")[0].text_content().strip().replace(",", "")
            price = re.search(ur'([$])([\d,]+(?:\.\d{2})?)', price).groups()
            price = price[0] + price[1]

            return price

        if self.tree_html.xpath("//span[contains(@class, 'gallery_page_price') and @itemprop='price']"):
            price = self.tree_html.xpath("//span[contains(@class, 'gallery_page_price') and @itemprop='price']")[0].text_content().strip()
            price = re.search(ur'([$])([\d,]+(?:\.\d{2})?)', price).groups()
            price = price[0] + price[1]

            return price

        if self.tree_html.xpath("//span[@itemprop='price']"):
            price = self.tree_html.xpath("//span[@itemprop='price']/a/text()")
            price = self._clean_html(' '.join(price))
            return price

        if self.tree_html.xpath('//span[@class="pp__price__value"]'):
            currency = self.tree_html.xpath('//span[@class="pp__price__currency"]/text()')[0].strip()
            price = self.tree_html.xpath('//span[@class="pp__price__value"]/text()')[0].strip()
            return currency + price

        return '${:2,.2f}'.format(min([v['price'] for v in self.jv.all_variants()]))

    def _marketplace(self):
        return 0

    def _site_online(self):
        return 1

    def _in_stores(self):
        if self.tree_html.xpath("//input[@class='bp-pp-btn-check-availability']"):
            return 1

        return 0

    def _site_online_out_of_stock(self):
        for variant in self.jv.all_variants():
            if variant.get('in_stock'):
                return 0

        product_json = self.tree_html.xpath('//script[@type="application/ld+json"]/text()')

        if product_json and 'http://schema.org/InStock' in product_json[0]:
            return 0

        return 1

    # #########################################
    # ############## CONTAINER : CLASSIFICATION
    # #########################################

    def _categories(self):
        categories = []
        for category in self.category_json:
            if len(category.get('breadCrumbLabel')) > 0:
                categories.append(category.get('breadCrumbLabel'))
        if not categories:
            categories = self.product_json['category']
            categories = [categories['parent']['name'], categories['name']]
            return [c.replace(u'\u2019', '\'') for c in categories]
        return categories[1:]

    def _brand(self):
        return self.product_json.get('brand', {}).get('name')

    def _extract_size_chart_and_fit_guide(self):
        self.size_chart_url_link = self._size_chart_and_fit_guide_helper('size_chart')
        self.fit_guide_url_link = self._size_chart_and_fit_guide_helper('fit_guide')

    def _size_chart_and_fit_guide_helper(self, get):
        kaid_info = self.tree_html.xpath("//ul[@class='sku_links_list']//a/@onclick")

        if kaid_info:
            if get == 'size_chart':
                kaid_str = kaid_info[0]
            elif get == 'fit_guide':
                kaid_str = kaid_info[1]

            kaid = kaid_str.split(",")[3].replace('\'', '')

            req = self._request(self.SIZE_CHART_AND_FIT_GUIDE_URL.format(kaid=kaid))
            if req.status_code == 200:
                info = html.fromstring(response.content)
                link = info.xpath("//div[@class='shell_content']//img/@src")[0]
                return 'http://www.jcpenney.com' + link

    def _size_chart(self):
        if self.size_chart_url_link:
            return 1
        return 0

    def _fit_guide(self):
        if self.fit_guide_url_link:
            return 1
        return 0

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub(' +', ' ', re.sub("&nbsp;|&#160;", " ", text)).strip()

    def _clean_html(self, html):
        html = html.replace('\\','')
        html = re.sub('[\n\t\r]', '', html)
        html = re.sub('<!--[^>]*-->', '', html)
        html = re.sub('</?(?!(ul|li|br))\w+[^>]*>', '', html)
        html = re.sub('&#160;', ' ', html)
        html = re.sub('\s+', ' ', html)
        return re.sub('> <', '><', html).strip()

    # #########################################
    # ############### RETURN TYPES
    # #########################################

    DATA_TYPES = {
        # CONTAINER : NONE
        "product_id": _product_id,
        "site_id": _site_id,

        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name,
        "description": _description,
        "long_description": _long_description,
        "specs": _specs,
        "features": _features,
        "model": _model,
        "variants": _variants,
        "swatches": _swatches,
        "no_longer_available": _no_longer_available,

        # CONTAINER : PAGE_ATTRIBUTES
        "size_chart": _size_chart,
        "fit_guide": _fit_guide,
        "image_urls": _image_urls,
        "video_count": _video_count,
        "video_urls": _video_urls,

        # CONTAINER : REVIEWS
        "reviews": _reviews,

        # CONTAINER : SELLERS
        "price": _price,
        "marketplace": _marketplace,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores": _in_stores,

        # CONTAINER : CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
    }
