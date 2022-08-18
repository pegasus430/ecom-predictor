#!/usr/bin/python

import re
import json
import traceback
from lxml import html

from extract_data import Scraper
from spiders_shared_code.adorama_variants import AdoramaVariants


class AdoramaScraper(Scraper):

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.adorama.com/<product-code>.html"

    SPECS_URL = "https://www.adorama.com/Als.Mvc/nspc/SpecsTab?sku={}"

    OPTIONS_URL = "https://www.adorama.com/api/catalog/GetProductData?svfor=7day&cacheVersion=416" \
                  "&productVersion=20161123083530&lcuVersion=45203&sku={sku_list}" \
                  "&pageType=productPage&isEmailPrice=false&EmailPrice=F&directData=true"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.variants = None
        self.variants_checked = False
        self.av = AdoramaVariants()

    def check_url_format(self):
        m = re.match(r"^https?://www\.adorama\.com/[a-zA-Z0-9%\-\%\_]+.*\.html.*", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        if self.tree_html.xpath('//div[@class="not-found"]'):
            return True
        self._variants_init()
        return False

    def _get_api_key(self):
        api_key = re.search(r'\"reflektionApiKey\":\"(.*?)\",', self.page_raw_text)
        if api_key:
            return api_key.group(1)

    def _variants_init(self):
        api_key = self._get_api_key()
        sku_list = self.tree_html.xpath('//div[contains(@class, "product-options")]//a/@data-track-data')
        if not sku_list:
            sku_list = self.tree_html.xpath('//li[@data-value="productOption"]/@data-track-data')
        if sku_list:
            sku_list = self._sku() + ',' + ','.join([x.split(',')[-1].strip() for x in sku_list])
            headers = {
                'x-api-key': api_key,
            }
            response = self._request(self.OPTIONS_URL.format(sku_list=sku_list), headers=headers)
            if response.status_code == 200:
                data = response.json()
                self.av.setupCH(self.tree_html, data)


    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath('//i[@itemprop="productID"]/@content')
        if product_id:
            return product_id[0]

    def _site_id(self):
        return self._product_id()

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//h1[@itemprop="name"]/span/text()')
        if product_name:
            return self._clean_text(''.join(product_name))

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _sku(self):
        return self._product_id()

    def _specs(self):
        specs = {}
        specs_url = self.SPECS_URL.format(self._product_id())
        raw_specs = self._request(specs_url)
        raw_specs = html.fromstring(raw_specs.content)
        raw_specs = raw_specs.xpath('//div[@id="specs"]')[0]
        labels = raw_specs.xpath('dl/dt/text()')
        for i in range(len(labels)):
            value = raw_specs.xpath('dl/dd[' + str(i + 1) + ']/text()')
            value = "\n".join(value)
            specs.update({labels[i]: value})
        return specs

    def _description(self):
        description = self.tree_html.xpath('//div[@class="description-wrap"]/p//text()')
        return ''.join([desc.strip() for desc in description])

    def _no_longer_available(self):
        return int(bool(self.tree_html.xpath('//div[contains(@class, "item-not-avilable")]')))

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = []

        main_image = self.tree_html.xpath('//div[@class="image-swiper"]//img/@src')
        if main_image:
            image_urls.append(main_image[0])

        sub_images = self.tree_html.xpath('//div[@class="image-swiper"]//img/@data-src')
        if sub_images:
            for image in sub_images:
                image_urls.append(image)

        if not image_urls:
            image_urls = self.tree_html.xpath(
                '//div[@class="large-img"]//img[contains(@class, "productImage")]/@data-src'
            )

        return image_urls if image_urls else None

    def _video_urls(self):
        video_ids = self.tree_html.xpath('//span[@class="thumb-video-container"]'
                                         '//img[contains(@class, "thumb-video")]/@data-media-id')
        if video_ids:
            return ['https://www.youtube.com/embed/{}'.format(i) for i in video_ids]

    def _variants(self):
        if not self.variants_checked:
            self.variants_checked = True
            self.variants = self.av._variants()

        return self.variants

    def _average_review(self):
        average_review = self.tree_html.xpath('//span[@class="pr-rating pr-rounded average"]/text()')
        if average_review:
            return float(average_review[0])

    def _review_count(self):
        review_count = self.tree_html.xpath('//span[@itemprop="ratingCount"]/text()')
        if not review_count:
            return 0
        else:
            review_count = review_count[0]
            return int(review_count)

    def _reviews(self):
        reviews = []
        values = self.tree_html.xpath('//span[@class="pr-histogram-count"]/text()')
        if values:
            values = [re.findall(r'[\d]+', value)[0] for value in values]
            values = [int(value) for value in values]
            return list(zip(range(1, 6)[::-1], values))
        return reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//strong[@itemprop="price"]/text()')
        if price:
            return price[0]
        price = self.tree_html.xpath('//input[@id="FinalPrice"]/@value')
        return price[0] if price else None

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        btn_cart = self.tree_html.xpath('//form[@class="viewPriceBreakdown"]//button[contains(@class, "add-to-cart")]')
        if not btn_cart:
            return 1
        if btn_cart and btn_cart[0].xpath('./@disabled'):
            return 1

        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath('//nav[@class="breadcrumbs"]/div/a/span/text()')
        if categories:
            return categories[1:]

    def _brand(self):
        brand = self.tree_html.xpath('//span[@itemprop="brand"]/text()')
        if brand:
            return brand[0]

    ##########################################
    ################ RETURN TYPES
    ##########################################

    DATA_TYPES = {
        "product_id": _product_id,
        "site_id": _site_id,

        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "sku": _sku,
        "description": _description,
        "specs": _specs,
        "variants": _variants,

        "image_urls": _image_urls,
        "video_urls": _video_urls,

        "review_count": _review_count,
        "average_review": _average_review,
        "reviews": _reviews,

        "price": _price,
        "in_stores": _in_stores,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "no_longer_available": _no_longer_available,

        "categories": _categories,
        "brand": _brand,
    }
