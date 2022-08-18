#!/usr/bin/python

import re
import traceback
import json
from urlparse import urljoin
from extract_data import Scraper
from spiders_shared_code.crutchfield_variants import CrutchfieldVariants


class CrutchfieldScraper(Scraper):

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www(1).crutchfield.com/p_<product-id>/<product-name>.html*"

    REVIEWS_URL = "https://www.crutchfield.com/handlers/product/item/reviews.ashx?i={}"
    VIDEO_API = "https://e.invodo.com/4.0/pl/6/E/{video_id}.js"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)

        self.cv = CrutchfieldVariants()

        self.video_urls_checked = False
        self.video_urls = []

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def check_url_format(self):
        m = re.match("https?://www1?.crutchfield.com/p_\w+/.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self.tree_html.xpath("//meta[@property='og:type' and @content='product']"):
            return False
        return True

    def _product_id(self):
        product_id = re.search('p_(\w+)', self.product_page_url)
        if product_id:
            return product_id.group(1)

    def _product_name(self):
        product_name = self.tree_html.xpath('//meta[@name="title"]/@content')
        if product_name:
            return product_name[0]

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _sku(self):
        sku = self.tree_html.xpath('//span[@itemprop="sku"]/text()')
        if sku:
            return sku[0].strip()

    def _model(self):
        model = self.tree_html.xpath('////span[@itemprop="mpn"]/text()')
        if model:
            return model[0]

    def _mpn(self):
        return self._model()

    def _specs(self):
        specs = {}
        current_chapter = specs
        specs_pool = self.tree_html.xpath('//div[@class="SpecTable"]')
        if specs_pool:
            specs_pool = specs_pool[0]
            for string in specs_pool:
                if 'head' in string.xpath('@class')[0]:
                    chapter_name = string.xpath('div/text()')[0]
                    specs.update({chapter_name: {}})
                    current_chapter = specs[chapter_name]
                elif 'body' in string.xpath('@class')[0]:
                    label = string.xpath('div[1]/text()')[0]
                    value = string.xpath('div[2]/text()')[0]
                    current_chapter.update({label: value})
        return specs

    def _description(self):
        description = self.tree_html.xpath("//div[contains(@class, 'ourTakeAlt')]//p[contains(@class, 'expertTagLine')]/text()")
        if description:
            return description[0].strip()

    def _no_longer_available(self):
        return bool(self.tree_html.xpath('//strong[text()="This item is no longer available."]'))

    def _image_urls(self):
        image_urls = [
            urljoin(self.product_page_url, image_url)
            for image_url in self.tree_html.xpath('//img[contains(@class, "mainProductPhoto")]/@data-src')
            ]
        image_urls += [
            urljoin(self.product_page_url, image_url)
            for image_url in self.tree_html.xpath('//img[contains(@class, "mainProductPhoto")]/@src')
            ]
        return image_urls

    def _video_urls(self):
        if self.video_urls_checked:
            return self.video_urls
        self.video_urls_checked = True
        video_ids = self.tree_html.xpath('//a[contains(@class, "videoThumb")]/@data-video-id')
        if video_ids:
            for video_id in video_ids:
                url = self.VIDEO_API.format(video_id=video_id)
                contents = self._request(url).text
                contents = contents.replace('Invodo.Pod.config(', '').replace(');', '')
                try:
                    contents = json.loads(contents)
                    for presentation in contents.get('presentations', []):
                        if presentation.get('presentationId') == video_id:
                            for pod in presentation.get('pods', []):
                                if pod.get('podId') == video_id:
                                    for frame in pod.get('frames', []):
                                        if frame.get('type') == 'video':
                                            for video in frame.get('encodings'):
                                                if video.get('id') == frame.get('defaultEncoding'):
                                                    self.video_urls = [video.get('http')]
                                                    return self.video_urls
                except:
                    print "Error Parsing Video JSON: {}".format(traceback.format_exc())

    def _price_amount(self):
        price_amount = self.tree_html.xpath('//meta[@itemprop="price"]/@content')
        if price_amount:
            price_amount = price_amount[0]
            price_amount = price_amount.replace(',', '')
            return float(price_amount)

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        oos = self.tree_html.xpath('//div[contains(@class, "buyBoxContainer")]//span[contains(@class, "stock-out")]')
        return 1 if oos else 0

    def _temp_price_cut(self):
        price_cut = self.tree_html.xpath('//p[@class="priceWas"]')
        return 1 if price_cut else 0

    def _categories(self):
        categories = self.tree_html.xpath('//div[@itemscope and @class="crumb"]/a/span/text()')
        if categories:
            if len(categories) > 2:
                return categories[2:]
            else:
                return categories

    def _brand(self):
        brand = self.tree_html.xpath('.//*[@itemprop="brand"]/meta[@itemprop="name"]/@content')
        if brand:
            return brand[0]

    def _reviews(self):
        if not self.is_review_checked:
            self.is_review_checked = True
            r = self._request(self.REVIEWS_URL.format(self._product_id()))
            try:
                reviews_json = r.json()
                reviews_json = reviews_json.get('RatingList')
                rating_by_star = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
                for i in range(5):
                    rating_by_star[i][1] = reviews_json[i].get('Count')
                self.reviews = rating_by_star
                self.review_count = sum([x[1] for x in rating_by_star])
                if self.review_count:
                    self.average_review = round(float(sum([x[0] * x[1] for x in rating_by_star])) / self.review_count, 2)
                return self.reviews
            except:
                print traceback.format_exc()
        return self.reviews

    def _variants(self):
        self.cv.setupCH(self.tree_html)
        return self.cv._variants()

    DATA_TYPES = {
        "product_id": _product_id,

        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "sku": _sku,
        "mpn": _mpn,
        "description": _description,
        "specs": _specs,
        "no_longer_available": _no_longer_available,
        "variants": _variants,

        "image_urls": _image_urls,
        "video_urls": _video_urls,

        "price_amount": _price_amount,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "temp_price_cut": _temp_price_cut,

        "categories": _categories,
        "brand": _brand,
    }
