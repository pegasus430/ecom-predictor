#!/usr/bin/python

import re
import requests
import traceback
import json
from lxml import html

from extract_data import Scraper


class BestBuyCanadaScraper(Scraper):
    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.bestbuy.ca/en-ca/<product-name>/<product-id>.aspx"

    BASE_IMAGE_URL = "https://multimedia.bbycastatic.ca/multimedia/products/1500x1500/{}/{}/{}.jpg"
    BASE_NEXT_IMAGE_URL = "https://multimedia.bbycastatic.ca/multimedia/products/1500x1500/{}/{}/{}_{}.jpg"

    VIDEO_API_URL = "https://content.googleapis.com/youtube/v3/search?" \
                    "channelId=UC4odhKK9Vyw7xL-YFP8S7xQ&part=snippet&" \
                    "q={}%20gallery%20-desc&type=video&videoEmbeddable=true&" \
                    "key=AIzaSyAS0UAMZ6nrWqHBDjfqLq0mMm5WVLlOXuE"

    STOCK_API_URL = "https://api-ssl.bestbuy.ca/availability/products?accept-language=en&" \
                    "skus={id}&accept=application%2Fvnd.bestbuy.standardproduct.v1%2Bjson&" \
                    "postalCode=M5G2C3&locations=977%7C203%7C931%7C62%7C617&maxlos=3"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.stock_data = None

    def check_url_format(self):
        m = re.match(r"^https?://www\.bestbuy\.ca/en\-ca/[a-zA-Z0-9%\-\%\_]+/.*\.aspx.*", self.product_page_url.lower())
        return bool(m)

    def not_a_product(self):
        if not self.tree_html.xpath("//meta[@property='og:type' and @content='product']"):
            return True
        self._get_stock_data()

    def _product_id(self):
        product_id = self.tree_html.xpath('//span[@itemprop="productid"]/text()')
        if product_id:
            return product_id[0]

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@itemprop="name"]/span[1]/text()')
        if product_name:
            return product_name[0]

    def _model(self):
        model = self.tree_html.xpath('//span[@itemprop="model"]/text()')
        if model:
            return model[0]

    def _upc(self):
        upc = self.tree_html.xpath('//span[@itemprop="productid"]/text()')
        return upc[0].zfill(12)[-12:] if upc else None

    def _specs(self):
        specs = {}
        curr_header = specs
        subsection = False
        rows = self.tree_html.xpath('//ul[@class="std-tablist"]/li')
        if rows:
            for row in rows:
                header = row.xpath('span/span/b/text()')
                if header:
                    header = header[0]
                    specs[header] = {}
                    curr_header = specs[header]
                    subsection = True
                else:
                    label = row.xpath('span/a/text()')
                    if not label:
                        label = row.xpath('span/span/text()')
                    label = label[0]
                    value = row.xpath('div/span/text()')[0]
                    if subsection:
                        curr_header.update({label: value})
                    else:
                        specs.update({label: value})
        return specs

    def _description(self):
        description = self.tree_html.xpath('//div[@class="tab-overview-item"][1]/text()')
        if description:
            return "".join(description).strip()

    def _long_description(self):
        long_description = self.tree_html.xpath('//div[@itemprop="description"]/ul/li/text()')
        if long_description:
            return "\n".join(long_description)

    def _image_urls(self):
        images = re.search(r'"additionalMedia":(\[.*?\]),', html.tostring(self.tree_html), re.DOTALL)
        try:
            return [
                image.get('url')
                for image in json.loads(images.group(1))
                if image.get('url')
                ]
        except Exception as e:
            print traceback.format_exc()

            if self.lh:
                self.lh.add_list_log('errors', str(e))

    def _video_urls(self):
        video_temp = 'https://www.youtube.com/embed/'
        video_list = []
        video_ids = []
        try:
            video_json = requests.get(self.VIDEO_API_URL.format(self._product_id()), timeout=5).json()
            video_json = video_json.get('items')
            for data in video_json:
                if 'gallery en' in data.get('snippet').get('description'):
                    video_ids.append(data.get('id').get('videoId'))
            for video_id in video_ids:
                video_list.append(video_temp + video_id)
        except:
            print traceback.format_exc()
        return video_list

    def _average_review(self):
        if self._review_count() > 0:
            average_review = self.tree_html.xpath(
                '//div[@class="overall-rating bold margin-bottom-one"]/span[1]/text()')
            if average_review:
                return float(average_review[0])

    def _review_count(self):
        review_count = self.tree_html.xpath('//span[@class="font-xs"]')
        if not review_count:
            return 0
        else:
            review_count = review_count[0]
        review_count = review_count.xpath('text()')[0]
        review_count = re.findall('\d+', review_count)[0]
        return int(review_count)

    def _reviews(self):
        reviews = []
        ratings = self.tree_html.xpath(
            '//div[contains(@class, "rating-detail-total-ratings")]/text()'
        )
        for idx, rating in enumerate(ratings):
            try:
                reviews.append([5 - idx, int(rating.replace(',', ''))])
            except:
                print traceback.format_exc()

        return reviews if reviews else None

    def _price(self):
        price = self.tree_html.xpath('//span[@class="amount"]/text()')
        if price:
            return price[0].strip()

    def _in_stores(self):
        in_store = self.stock_data.get('availabilities')
        if in_store:
            return 1 if 'instore' in in_store[0].get(
                'saleChannelExclusivity', '').lower() else 0

    def _site_online(self):
        in_stock = self.stock_data.get('availabilities')
        if in_stock:
            return 1 if 'online' in in_stock[0].get('saleChannelExclusivity', '').lower() else 0

    def _site_online_out_of_stock(self):
        if self._site_online():
            availability = self.stock_data.get('availabilities')
            if availability:
                return 0 if bool(availability[0].get('shipping', {}).get('quantityRemaining')) else 1

    def _in_stores_out_of_stock(self):
        if self._in_stores():
            availability = self.stock_data.get('availabilities')
            if availability:
                return 0 if availability[0].get('pickup', {}).get('purchasable') else 1

    def _categories(self):
        categories = self.tree_html.xpath("//span[@class='breadcrumb']/span/span/a/span/text()")
        if categories:
            return categories[1:]

    def _marketplace(self):
        return 1 if self._marketplace_sellers() else 0

    def _marketplace_sellers(self):
        rows = re.search('"sellerName":(.*?),', html.tostring(self.tree_html))
        if rows:
            sellers = rows.group(1).replace('\"', '')
            return [sellers] if sellers != 'null' else None

    def _marketplace_prices(self):
        if self._marketplace():
            return [self._price_amount()] * len(self._marketplace_sellers())

    def _brand(self):
        brand = self.tree_html.xpath('//span[@class="brand-logo"]/img/@alt')
        if not brand:
            brand = re.search('"brand":"(.*?)",', html.tostring(self.tree_html))
            return brand.group(1) if brand else None
        return brand[0] if brand else None

    def _get_stock_data(self):
        id = self._product_id()
        if id:
            data = self._request(self.STOCK_API_URL.format(id=id)).text
            try:
                data = json.loads(data[data.find('{'):])
                self.stock_data = data
            except Exception as e:
                self.stock_data = {}
                print traceback.format_exc()

                if self.lh:
                    self.lh.add_list_log('errors', str(e))

    DATA_TYPES = {
        "product_id": _product_id,

        "product_name": _product_name,
        "model": _model,
        "upc": _upc,
        "description": _description,
        "specs": _specs,
        "long_description": _long_description,

        "image_urls": _image_urls,
        "video_urls": _video_urls,

        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "marketplace": _marketplace,
        "marketplace_sellers": _marketplace_sellers,
        "marketplace_prices": _marketplace_prices,

        "categories": _categories,
        "brand": _brand,
    }
