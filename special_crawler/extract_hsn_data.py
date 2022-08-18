#!/usr/bin/python

import re
import requests

from lxml import html
from extract_data import Scraper
from spiders_shared_code.hsn_variants import HsnVariants


class HsnScraper(Scraper):
    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.hsn.com/products/<product-name>/<product id>"

    def __init__(self, **kwargs):  # **kwargs are presumably (url, bot)
        Scraper.__init__(self, **kwargs)

        self.hv = HsnVariants()

    def _extract_page_tree(self):
        for i in range(3):
            try:
                with requests.Session() as s:
                    response = s.get(self.product_page_url)

                    if response.ok:
                        content = response.text
                        self.tree_html = html.fromstring(content)
                        return

                    else:
                        self.ERROR_RESPONSE['failure_type'] = response.status_code

            except Exception as e:
                print 'ERROR EXTRACTING PAGE TREE', self.product_page_url, e

        self.is_timeout = True

    def check_url_format(self):
        m = re.match(r"^https?://www.hsn.com/products/.*?$", self.product_page_url)
        return bool(m)

    def not_a_product(self):
        itemtype = self.tree_html.xpath('//meta[@property="og:type"]/@content')[0].strip()

        if itemtype != "product":
            return True

        self.hv.setupCH(self.tree_html)

    ##########################################
    ############### CONTAINER : NONE
    ##########################################

    def _product_id(self):
        product_id = self._find_between(html.tostring(self.tree_html), '"product_id":[', '],')
        return product_id

    ##########################################
    ############### CONTAINER : PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath("//span[@id='product-name']/text()")
        if not product_name:
            product_name = self.tree_html.xpath("//div[@itemprop='name']/text()")

        return product_name[0] if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        return self._product_id()

    def _description(self):
        short_description = None
        first_short_description = self.tree_html.xpath("//div[@class='disclaimer-overview-bottom clearfix']//li//span/text()")
        next_short_description = self.tree_html.xpath("//div[@class='disclaimer-overview-bottom clearfix']//div/text()")

        if first_short_description and next_short_description:
            short_description = first_short_description[0] + next_short_description[0]
        elif first_short_description and not next_short_description:
            short_description = first_short_description[0]
        elif not first_short_description and next_short_description:
            short_description = next_short_description[0]

        return short_description

    def _long_description(self):
        long_description = self.tree_html.xpath("//div[@itemprop='description']//div[@class='content copy']")
        if long_description:
            long_description = html.tostring(long_description[0])
        else:
            long_description = ''.join(self.tree_html.xpath("//div[@class='content copy']//div/text()"))
        return re.sub(' +', ' ', self._clean_text(long_description))

    ##########################################
    ############### CONTAINER : PAGE_ATTRIBUTES
    ##########################################

    def _video_urls(self):
        video_list = []
        video_domain = "https://www.youtube.com/embed/"
        video_model_id = self.tree_html.xpath("//a[contains(@class, 'youtube-player-modal')]/@data-id")

        for id in video_model_id:
            video_list.append(video_domain + id)

        return video_list

    def _video_count(self):
        video_urls = self._video_urls()

        return len(video_urls) if video_urls else 0

    def _image_urls(self):
        image_url_list = []
        image_urls_info = self.tree_html.xpath("//div[contains(@class, 'product-image-thumbnails')]//li[@class='image-container']//a//img/@src")
        if image_urls_info:
            image_urls = image_urls_info
        else:
            image_urls = self.tree_html.xpath("//div[@class='product-videos']//img/@src")
        if image_urls:
            for image_url in image_urls:
                image_url_list.append(image_url.replace('prodthum', 'prodfull'))
                image_url_list = list(set(image_url_list))

        return image_url_list

    def _variants(self):
        return self.hv._variants()

    def _swatches(self):
        image_urls = self._image_urls()
        return self.hv.swatches(image_urls)

    ##########################################
    ############### CONTAINER : REVIEWS
    ##########################################

    def _average_review(self):
        average_rating = None

        average_rating_info = self.tree_html.xpath("//div[@class='rating']//span[@class='value']/text()")
        if average_rating_info:
            average_rating = re.findall('\d*\.?\d+', average_rating_info[0])
        else:
            average_rating_info = self.tree_html.xpath("//div[@class='rating medium']//span[@class='count']/text()")
            if average_rating_info:
                average_rating = re.findall('\d*\.?\d+', average_rating_info[0])

        return average_rating[0] if average_rating else 0

    def _review_count(self):
        review_count_info = self.tree_html.xpath("//dd[contains(@class, 'rating')]//a[@class='count']/text()")
        if review_count_info:
            review_count = review_count_info
        else:
            review_count = self.tree_html.xpath("//span[@itemprop='reviewCount']/text()")
        if review_count:
            review_count = re.search('\d+', review_count[0])

        return int(review_count.group()) if review_count else 0

    def _reviews(self):
        rating_by_star = []
        rating_values = []

        # Get mark of Review
        rating_values_data = self.tree_html.xpath("//span[contains(@class, 'ratingFilter')]/text()")
        if rating_values_data:
            for rating_value in rating_values_data:
                rating_values.append(re.findall(r'(\d+)', rating_value[0])[0])
        else:
            rating_values = self.tree_html.xpath("//ol[@class='ratings-graph']//a[@class='star-review-link ']/@data-star-rating")

        # Get count of Mark
        rating_count_data = self.tree_html.xpath("//dl[contains(@class, 'rating-distribution')]//span[contains(@class, 'count')]/text()")
        if rating_count_data:
            rating_count_data = rating_count_data[::-1]
        else:
            rating_count_data = self.tree_html.xpath("//ol[@class='ratings-graph']//span[@class='count']/text()")[::-1]

        for i in range(0, 5):
            ratingFound = False
            for rating_value in rating_values:
                for index, attribute in enumerate(rating_count_data):
                    if int(rating_value) == i + 1:
                        if index == i:
                            rating_by_star.append([rating_value, int(rating_count_data[index])])
                            ratingFound = True
                            break

            if not ratingFound:
                rating_by_star.append([i + 1, 0])

        if rating_by_star:
            buyer_reviews_info = rating_by_star[::-1]

        return buyer_reviews_info

    ##########################################
    ############### CONTAINER : SELLERS
    ##########################################

    def _price_amount(self):
        price = self.tree_html.xpath("//span[@itemprop='price']/text()")
        return float(price[0]) if price else None

    def _price(self):
        price_amount = self._price_amount()

        return '$' + str(price_amount) if price_amount else None

    def _price_currency(self):
        price_currency = self.tree_html.xpath("//span[@itemprop='priceCurrency']/@content")
        return price_currency[0] if price_currency else 'USD'

    def _temp_price_cut(self):
        shipping_status = self.tree_html.xpath("//div[@class='product-shipping-handling']/text()")
        if not shipping_status:
            shipping_status = self.tree_html.xpath("//div[@class='product-shipping-label']/text()")
        return 1 if shipping_status else 0

    def _in_stores(self):
        return 1

    def _site_online(self):
        return 1

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        return 0

    ##########################################
    ############### CONTAINER : CLASSIFICATION
    ##########################################

    def _categories(self):
        categories = self.tree_html.xpath("//nav[@id='breadcrumb']//span[@itemprop='name']/text()")
        if not categories:
            categories = self.tree_html.xpath("//li[@itemprop='itemListElement']//span[@itemprop='name']/text()")
        return categories if categories else None

    def _brand(self):
        brand = self.tree_html.xpath("//span[@itemprop='brand']/text()")

        return brand[0] if brand else None

    ##########################################
    ################ HELPER FUNCTIONS
    ##########################################

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    ##########################################
    ################ RETURN TYPES
    ##########################################

    # dictionaries mapping type of info to be extracted to the method that does it
    # also used to define types of data that can be requested to the REST service

    DATA_TYPES = { \
        # CONTAINER : NONE
        "product_id": _product_id, \
 \
        # CONTAINER : PRODUCT_INFO
        "product_name": _product_name, \
        "product_title": _product_title, \
        "title_seo": _title_seo, \
        "model": _model, \
        "description": _description, \
        "long_description": _long_description, \
        "variants" : _variants, \
        "swatches" : _swatches, \
 \
        # CONTAINER : PAGE_ATTRIBUTES
        "image_urls": _image_urls, \
        "video_count": _video_count, \
        "video_urls": _video_urls, \

        # CONTAINER : REVIEWS
        "review_count": _review_count, \
        "average_review": _average_review, \
        "reviews": _reviews, \
 \
        # CONTAINER : SELLERS
        "price": _price, \
        "price_amount": _price_amount, \
        "price_currency": _price_currency, \
        "temp_price_cut": _temp_price_cut, \
        "in_stores": _in_stores, \
        "site_online": _site_online, \
        "site_online_out_of_stock": _site_online_out_of_stock, \
        "in_stores_out_of_stock": _in_stores_out_of_stock, \
 \
        # CONTAINER : CLASSIFICATION
        "categories": _categories, \
        "brand": _brand \
        }
