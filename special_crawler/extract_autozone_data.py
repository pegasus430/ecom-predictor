#!/usr/bin/python

import re
import json
from lxml import html
from urllib import quote

from extract_data import Scraper
from product_ranking.guess_brand import guess_brand_from_first_words


class AutozoneScraper(Scraper):

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.autozone.com/.*"

    BASE_URL_REVIEWSREQ = 'https://pluck.autozone.com/ver1.0/sys/jsonp?' \
                          'widget_path=pluck/reviews/rollup&' \
                          'plckArticleUrl={article_url}&' \
                          'plckDiscoverySection={discovery}&' \
                          'plckReviewShowAttributes=true&' \
                          'clientUrl={product_url}&' \
                          'plckReviewOnKey={product_id}&' \
                          'plckReviewOnKeyType=article&' \
                          'plckArticleTitle={article_title}'

    def check_url_format(self):
        m = re.match(r"^https?://www\.autozone\.com\/.*", self.product_page_url)
        return bool(m)

    @staticmethod
    def _take_all(values):
        _values = [x.strip() for x in values or [] if x.strip()]
        if _values:
            return _values

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self.tree_html.xpath("//div[@id='product-data']//div[@id='SkuId']//text()")[0].strip()
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        return self.tree_html.xpath("//h1[@property='name']//text()")[0].strip()

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _description(self):
        description = self.tree_html.xpath("//div[@id='features']//p/text()")[0].strip()
        return description

    def _video_count(self):
        return len(self.tree_html.xpath('//div[@class="videoButton video"]//div'))

    def _features(self):
        features = self.tree_html.xpath("//div[@id='features']//li/text()")
        return self._take_all(features)

    def _specs(self):
        specs = {}

        for tr in self.tree_html.xpath("//table[@id='prodspecs']//tr"):
            key, value = tr.xpath('./td')
            key = key.text_content().strip()[:-1]
            value = value.text_content().strip()
            specs[key] = value

        if specs:
            return specs

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_urls = self.tree_html.xpath("//div[@class='productThumbsblock']/ul/li//img/@src")
        image_urls = [u.strip()[:-2] + '4' for u in image_urls]
        main_image = self.tree_html.xpath('//img[@id="mainimage"]/@src')
        if not image_urls and main_image:
            return main_image
        if image_urls:
            return image_urls

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _reviews(self, *args, **kwargs):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        discovery = self._find_between(
            self.page_raw_text, 'plckDiscoverySection:', ',').strip(" '}")
        article_title = self._find_between(
            self.page_raw_text, 'plckArticleTitle:', ',').strip(" '}")
        article_url = self._find_between(
            self.page_raw_text, 'plckArticleUrl:', ',').strip(" '}")

        review_url = self.BASE_URL_REVIEWSREQ.format(
            product_id=self._product_id(),
            product_url=quote(self.product_page_url),
            article_title=article_title,
            article_url=quote(article_url),
            discovery=discovery,
        )

        contents = self._request(review_url).content

        review_html = re.search('(<div id="pluck_reviews_rollup.+?\'\))', contents)
        review_html = html.fromstring(review_html.group(1))

        if review_html.xpath('//*[@itemprop="ratingValue"]/text()')[0].strip() == '0':
            return

        review_counts = review_html.xpath("//div[contains(@class,'pluck-dialog-middle')]//"
                         "span[contains(@class,'pluck-review-full-attributes-name-post')]/text()")

        self.reviews = [[5 - i, int(count)] for i, count in enumerate(review_counts)]
        return self.reviews

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price(self):
        price = self.tree_html.xpath('//td[contains(@class,"price")]')
        if price:
            return re.sub('\s+', '', price[0].text_content())

    def _site_online(self):
        if self.tree_html.xpath('//*[@class="button-bar-msg-not-available"]'):
            return 0
        return 1

    def _site_online_out_of_stock(self):
        return 1 - self._site_online()

    def _in_stores(self):
        if self.tree_html.xpath('//*[@class="button-bar-msg-in-stock"]'):
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
        categories = self.tree_html.xpath("//ul[contains(@class,'breadcrumb')]//li/a//text()")
        if categories:
            return [c.strip() for c in categories[1:] if c.strip()]

    def _brand(self):
        brand = re.search('"productBrand":"(.*?)",', html.tostring(self.tree_html))
        if brand:
            return brand.group(1)
        return guess_brand_from_first_words(self._product_name())

    ##########################################
    # RETURN TYPES
    ##########################################
    DATA_TYPES = {
        # CONTAINER: NONE
        "product_id": _product_id,

        # CONTAINER: PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "description": _description,
        "title_seo": _title_seo,
        "features": _features,
        "specs": _specs,
        "video_count": _video_count,

        # CONTAINER: PAGE Attributes
        "image_urls": _image_urls,

        # CONTAINER: reviews
        "reviews": _reviews,

        # CONTAINER:sellers
        "price": _price,
        "in_stores": _in_stores,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "site_online": _site_online,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "marketplace": _marketplace,

        # CONTAINER: classification
        "categories": _categories,
        "brand": _brand
    }
