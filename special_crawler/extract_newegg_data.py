#!/usr/bin/python

import re
import json
import traceback

from lxml import html
from extract_data import Scraper
from spiders_shared_code.newegg_variants import NeweggVariants

class NeweggScraper(Scraper):

    ##########################################
    ############### PREP
    ##########################################

    INVALID_URL_MESSAGE = "Expected URL format is http(s)://www.newegg.(com or ca)/Product/Product.aspx?Item=<product-id>"

    WEBCOLLAGE_POWER_PAGE = 'https://scontent.webcollage.net/newegg/power-page?ird=true&channel-product-id={}'

    REVIEW_URL = "https://www.newegg.com/Common/Ajax/ProductReview2017.aspx?action=" \
                 "Biz.Product.ProductReview.switchReviewTabCallBack&callback=Biz.Product.ProductReview.switchReview" \
                 "TabCallBack&&Item={}&review=0&SummaryType=0&Pagesize=25&PurchaseMark=false&SelectedRating=-1" \
                 "&VideoOnlyMark=false&VendorMark=false&IsFeedbackTab=true&ItemGroupId=51571483&Type=" \
                 "Seller&ItemOnlyMark=true&chkItemOnlyMark=on&Keywords=(keywords)&SortField=0&DisplaySpecificReview=1"

    def __init__(self, **kwargs):
        Scraper.__init__(self, **kwargs)
        self.nv = NeweggVariants()

        self._set_proxy()

    def check_url_format(self):
        m = re.match("https?://www.newegg.(com|ca)/product/product\.aspx\?item=[a-z0-9\-]+", self.product_page_url.lower())
        return bool(m)

    def not_a_product(self):
        if not self.tree_html.xpath('//div[@itemtype="//schema.org/Product"]'):
            return True
        self.nv.setupCH(html.tostring(self.tree_html))
        return False

    def _extract_page_tree(self):
        self._extract_page_tree_with_retries()

    def _product_id(self):
        product_id = self.tree_html.xpath('//input[@id="hiddenItemNumber"]/@value')
        return product_id[0] if product_id else None

    def _item_num(self):
        item_num = self.tree_html.xpath('//input[@id="persMainItemNumber"]/@value')
        return item_num[0] if item_num else None

    def _pre_scrape(self):
        self._extract_webcollage_contents(product_id=self._item_num())

    ##########################################
    ############### CONTAINER: PRODUCT_INFO
    ##########################################

    def _product_name(self):
        product_name = self.tree_html.xpath('//*[@itemprop="name"]/text()')
        return product_name[0].strip() if product_name else None

    def _product_title(self):
        return self._product_name()

    def _title_seo(self):
        return self._product_name()

    def _model(self):
        model = self._find_between(html.tostring(self.tree_html), "product_model:['", "'],")
        return model if model else None

    def _features(self):
        features = self.tree_html.xpath('//dl[dt/text()="Features"]/dd/text()')
        return features if features else None

    def _description(self):
        description = self.tree_html.xpath('//div[@class="grpBullet"]/ul[@class="itemColumn"]')
        return self._clean_text(html.tostring(description[0])) if description else None

    def _long_description(self):
        long_desc = self.tree_html.xpath("//div[@id='Overview_Content']")

        if long_desc:
            long_desc = self._exclude_javascript_from_description(html.tostring(long_desc[0]))
            long_desc = self._clean_text(html.fromstring(long_desc).text_content()).strip()
            return long_desc if long_desc else None

    ##########################################
    ############### CONTAINER: PAGE_ATTRIBUTES
    ##########################################

    def _image_urls(self):
        image_list = self._find_between(html.tostring(self.tree_html), 'imgGalleryConfig.Items=', '];')
        image_base_url = 'https:' + self._find_between(html.tostring(self.tree_html), 'imgGalleryConfig.BaseUrlForNonS7="', '";')
        image_json = json.loads(image_list + ']')
        if image_json[0].get('normalImageInfo'):
            if image_json[0]['normalImageInfo'].get('imageNameList'):
                image_urls = image_json[0]['normalImageInfo']['imageNameList'].split(',')
                return [image_base_url + image_url for image_url in image_urls] if image_urls else None

    def _video_urls(self):
        if self.wc_videos:
            return self.wc_videos

        if self.tree_html.xpath('//iframe[@allowfullscreen]/@src'):
            return self.tree_html.xpath('//iframe[@allowfullscreen]/@src')

    def _variants(self):
        return self.nv._variants()

    ##########################################
    ############### CONTAINER: REVIEWS
    ##########################################

    def _reviews(self):
        if not self.is_review_checked:
            self.is_review_checked = True

            item_id = re.search(r'Item=(\w+\d+(?:-\w+\d+)+)', self._canonical_link())
            if not item_id:
                item_id = re.search(r'-_-(\w+\d+(?:-\w+\d+)+)', self.product_page_url)
            if not item_id:
                item_id = re.search(r'Item=(\w+\d+)', self.product_page_url)

            if not item_id:
                return None

            review_url = self.REVIEW_URL.format(item_id.group(1))

            try:
                review_content = self._request(review_url).content
                review_html = html.fromstring(review_content.replace('\\', ''))

                review_count = review_html.xpath('//span[@itemprop="reviewCount"]/text()')

                if review_count:
                    self.review_count = int(review_count[0])

                    average_review = review_html.xpath('//span[@itemprop="ratingValue"]/@content')
                    self.average_review = float(average_review[0])

                    self.reviews = []

                    rating_groups = review_html.xpath('//div[@class="rating-view"]')
                    for rating_group in rating_groups:
                        rating = rating_group.xpath('.//div[@class="rating-view-name"]/text()')
                        if not rating:
                            continue

                        rating = re.search(r'\d+', rating[0])
                        if rating:
                            rating = int(rating.group())
                            rating_count = rating_group.xpath('.//div[@class="rating-view-chart-num"]/text()')
                            if rating_count:
                                rating_count = int(rating_count[0])
                                self.reviews.append([rating, rating_count])
            except:
                print traceback.format_exc()

        return self.reviews

    ##########################################
    ############### CONTAINER: SELLERS
    ##########################################

    def _price_amount(self):
        price_amount = self.tree_html.xpath('//meta[@itemprop="price"]/@content')
        return float(price_amount[0]) if price_amount else None

    def _site_online_out_of_stock(self):
        return 0

    def _in_stores_out_of_stock(self):
        in_stock = self._find_between(html.tostring(self.tree_html), "product_instock:['", "'],")
        return 1 if in_stock == '0' else 0

    def _in_stores(self):
        return 1

    ##########################################
    ############### CONTAINER: CLASSIFICATION
    ##########################################

    def _categories(self):
        bread_crumb = self._find_between(html.tostring(self.tree_html), "page_breadcrumb:'", "',")
        categories = bread_crumb.split(' &gt; ')
        return categories[1:-1] if categories else None

    def _brand(self):
        brand = re.search('brandName:"(.*?)"', html.tostring(self.tree_html), re.DOTALL)
        return brand.group(1) if brand else None

    def _marketplace(self):
        return 1 if self._marketplace_sellers() else 0

    def _marketplace_sellers(self):
        return self.tree_html.xpath('//p[@class="grpNote-sold-by"]/*/text()')

    ##########################################
    ################ RETURN TYPES
    #########################################

    DATA_TYPES = {
        # CONTAINER: NONE
        "product_id": _product_id,

        # CONTAINER: PRODUCT_INFO
        "product_name": _product_name,
        "product_title": _product_title,
        "title_seo": _title_seo,
        "model": _model,
        "features": _features,
        "description": _description,
        "long_description": _long_description,
        "item_num": _item_num,

        # CONTAINER: PAGE_ATTRIBUTES
        "image_urls": _image_urls,
        "video_urls": _video_urls,

        # CONTAINER: REVIEWS
        "reviews": _reviews,

        # CONTAINER: SELLERS
        "price_amount": _price_amount,
        "in_stores": _in_stores,
        "site_online_out_of_stock": _site_online_out_of_stock,
        "in_stores_out_of_stock": _in_stores_out_of_stock,
        "marketplace": _marketplace,
        "marketplace_sellers": _marketplace_sellers,

        # CONTAINER: CLASSIFICATION
        "categories": _categories,
        "brand": _brand,
        "variants": _variants
        }
