import re
import json
import base64
import requests
import traceback
import xml.etree.ElementTree as ET

from lxml import html, etree
from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.costco_variants import CostcoVariants


class CostcoScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.costco.com/<product name>.product.<product id>.html"

    WEBCOLLAGE_POWER_PAGE = "http://content.webcollage.net/costco/smart-button?ird=true&channel-product-id={0}"

    IMAGE_CHANNEL_URL = "http://richmedia.channeladvisor.com/ViewerDelivery/productXmlService?profileid={0}&itemid={1}&viewerid=1068"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
            "passkey=bai25xto36hkl5erybga10t99" \
            "&apiversion=5.5" \
            "&displaycode=2070-en_us" \
            "&resource.q0=products" \
            "&filter.q0=id:eq:{}" \
            "&stats.q0=reviews"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.image_urls = None
        self.is_image_checked = False

        self.is_video_checked = False
        self.video_urls = None

        self.widget_pdfs = None
        self.widget_videos = None
        self.widgets_checked = False

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def not_a_product(self):
        pid = self.tree_html.xpath('//h1[text()="Product Not Found"]//text()')
        if len(pid) > 0:
            return True
        self.cv = CostcoVariants()
        self.cv.setupCH(self.tree_html)
        return False

    def _pre_scrape(self):
        self._extract_webcollage_contents()

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        return self.product_page_url.split('.')[-2]

    ##########################################
    ################ CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        pn = self.tree_html.xpath('//h1[@itemprop="name"]//text()')
        if len(pn)>0:
            return pn[0].strip()

    def _product_title(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _title_seo(self):
        return self.tree_html.xpath("//title//text()")[0].strip()

    def _features(self):
        rws = self.tree_html.xpath('//div[@id="product-tab2"]//li')
        if not rws:
            rws = self.tree_html.xpath("//ul[@class='pdp-features']//li")
        if rws:
            return [r.text_content().replace(':',',').strip() for r in rws]

    def _description(self):
        short_description = self.tree_html.xpath("//p[@class='primary-clause']/text()")
        short_description = self._clean_html(' '.join(short_description))

        return short_description if short_description else None

    def _long_description(self):
        long_description = self.tree_html.xpath('//div[contains(@itemprop, "description")]//text()')
        long_description = self._clean_html(' '.join(long_description ))

        return long_description if long_description else None

    def _apluscontent_desc(self):
        res = self._clean_text(' '.join(self.tree_html.xpath('//div[@id="wc-aplus"]//text()')))
        if res != "" : return res

    def _variants(self):
        return self.cv._variants()

    ##########################################
    ################ CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        if self.is_image_checked:
            return self.image_urls

        self.is_image_checked = True

        main_image_url = self.tree_html.xpath("//meta[@property='og:image']/@content")[0]
        main_image_url = main_image_url if re.match('https?://', main_image_url) else 'https://' + main_image_url 

        profile_id = re.search("\?profileId=(.*)&imageId", main_image_url).group(1)
        item_id = re.search("imageId=(.*)__1&recipeName", main_image_url).group(1)

        image_info = self._request(self.IMAGE_CHANNEL_URL.format(profile_id, item_id)).content
        image_info = ET.fromstring(image_info)

        image_urls = []

        # Get the first image url (variant) for each view
        for view in image_info.findall('.//view'):
            image_urls.append(view.findall('.//image[@type="initial"]')[0].get('path'))

        if not image_urls:
            image_urls = [main_image_url]

        self.image_urls = image_urls
        return self.image_urls

    def _video_urls(self):
        if self.is_video_checked:
            return self.video_urls

        self.is_video_checked = True

        video_urls = []

        video_urls.extend(self.wc_videos)

        self._check_widgets()

        if self.widget_videos:
            video_urls.extend(self.widget_videos)

        # liveclicker videos
        dim5 = re.search('LCdim5 = "(\d+)"', html.tostring(self.tree_html))

        if dim5:
            dim5 = dim5.group(1)

            liveclicker = self.load_page_from_url_with_number_of_retries('http://sv.liveclicker.net/service/api?method=liveclicker.widget.getList&account_id=69&dim5=' + dim5)

            widgets = etree.XML( re.sub('encoding="[^"]+"', '', liveclicker))
            try:
                for widget in widgets:
                    widget_id = widget.find('widget_id').text

                    liveclicker = self.load_page_from_url_with_number_of_retries('http://sv.liveclicker.net/service/getXML?widget_id=' + widget_id)
                    video_urls = html.fromstring(liveclicker).xpath("//location/text()")
            except:
                traceback.format_exc()

        if video_urls:
            self.video_urls = video_urls
            return video_urls

    def _check_widgets(self):
        if not self.widgets_checked:
            self.widgets_checked = True

            pdfs = []
            videos = []

            sellpoint = json.loads(requests.get('http://a.sellpoint.net/w/83/l/' + self._product_id() + '.json').content)
            widgets = sellpoint.get('widgets', [])

            for widget in widgets:
                sellpoint = json.loads(requests.get('http://a.sellpoint.net/w/83/w/' + widget + '.json').content)
                widgets2 = sellpoint['widgets']

                for widget2 in widgets2:
                    sellpoint = json.loads(requests.get('http://a.sellpoint.net/w/83/w/' + widget2 + '.json').content)
                    if sellpoint.get('items'):
                        for item in sellpoint['items']:
                            url = item['url'][2:]
                            if not url in pdfs:
                                pdfs.append(url)
                    if sellpoint.get('videos') and not 'callout' in sellpoint['targetSelector']:
                        for video in sellpoint['videos']:
                            mp4 = video['src']['mp4']['res' + str(video['maxresolution'])]
                            if not mp4 in videos:
                                videos.append(mp4)

            if pdfs:
                self.widget_pdfs = pdfs
            if videos:
                self.widget_videos = videos

    def _pdf_urls(self):
        pdf = self.tree_html.xpath("//a[contains(@href,'.pdf')]/@href")
        pdf_list = []

        if len(pdf) > 0:
            pdf = set(pdf)
            pdf_list = ["http://www.costco.com" + p for p in pdf if "Cancellation" not in p and 'Restricted-Zip-Codes' not in p and 'Curbside' not in p]

        self._check_widgets()

        if self.widget_pdfs:
            pdf_list.extend(self.widget_pdfs)

        pdf_list.extend(self.wc_pdfs)

        if pdf_list:
            return pdf_list

    ##########################################
    ################ CONTAINER : SELLERS
    ##########################################

    def _price(self):
        pr = re.search(r'"price"\s*:\s*"(.+?)"', html.tostring(self.tree_html))
        if pr:
            pr = base64.b64decode(pr.group(1))
        price = self._price_currency().replace("USD", "$") + pr

        return price

    def _in_stores(self):
        if 'available at your local costco warehouse' in html.tostring(self.tree_html).lower():
            return 1
        return 0

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        if self.tree_html.xpath(
                '//span[contains(@class, "out-of-stock")] | //img[contains(@class, "oos-overlay")]')\
                or 'not available for purchase on costco.com' in html.tostring(self.tree_html).lower():
            return 1

        return 0

    def _marketplace(self):
        return 0

    ##########################################
    ################ CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//ul[@id="crumbs_ul"]/li/a/text()')
        return categories[1:] if categories else None

    def _brand(self):
        brand = re.search('Collection Name:</span> (.*?) <', html.tostring(self.tree_html), re.DOTALL)
        if brand:
            return brand.group(1)
        brand = re.search('Brand:</span> (.*?) <', html.tostring(self.tree_html), re.DOTALL)
        if brand:
            return brand.group(1)

        brand = self.tree_html.xpath('//div[contains(@class, "product-info-specs")]'
                                     '//div[text()="Brand"]'
                                     '/following-sibling::div/text()')
        if brand:
            return brand[0]

        return guess_brand_from_first_words(self._product_name())

    def _upc(self):
        bn = self.tree_html.xpath('//meta[@property="og:upc"]/@content')
        if len(bn) > 0 and bn[0] != "":
            return bn[0]

    def _model(self):
        model = self.tree_html.xpath("//span[@class='model-number']//span/text()")
        return model[0].split('|')[0].strip() if model else None

    def _item_num(self):
        sku = self.tree_html.xpath("//span[@itemprop='sku']/text()")
        return sku[0] if sku else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    # clean text inside html tags - remove html entities, trim spaces
    def _clean_text(self, text):
        p = re.compile(r'<.*?>')
        text = p.sub(' ', text)
        text = text.replace("\n", " ").replace("\t"," ").replace("\r", " ")
        text = text.replace("\\", "")
       	text = re.sub("&nbsp;", " ", text).strip()
        return re.sub(r'\s+', ' ', text)

    # Get rid of all html except for <ul>, <li> and <br> tags
    def _clean_html(self, html):
        html = html.replace('\\', '')
        html = re.sub('[\n\t\r]', '', html)
        html = re.sub('<!--[^>]*-->', '', html)
        html = re.sub('</?(?!(ul|li|br))\w+[^>]*>', '', html)
        html = re.sub('&#160;', ' ', html)
        html = re.sub('\s+', ' ', html)
        return re.sub('> <', '><', html).strip()

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
        "upc": _upc,
        "model": _model,
        "item_num": _item_num,
        "features": _features,
        "description": _description,
        "long_description": _long_description,
        "variants": _variants,

        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,
        "pdf_urls": _pdf_urls,

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
