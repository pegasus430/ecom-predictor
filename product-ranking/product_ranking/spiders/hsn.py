from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
import urlparse

from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.hsn_variants import HsnVariants


class HsnProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'hsn_products'
    allowed_domains = ["www.hsn.com"]

    SEARCH_URL = "https://www.hsn.com/search?query={search_term}"

    def start_requests(self):
        for req in super(HsnProductsSpider, self).start_requests():
            if self.searchterms:
                req = req.replace(callback=self._check_redirect)
            yield req

    def _check_redirect(self, response):
        if response.xpath('//meta[@property="og:type" and @content="product"]'):
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = response.url
            prod['search_term'] = response.meta['search_term']
            response.meta.update({'product': prod})
            return self.parse_product(response)
        else:
            return self.parse(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        reseller_id, sku = self._parse_ids(response)
        cond_set_value(product, 'reseller_id', reseller_id)
        cond_set_value(product, 'sku', sku)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        self._parse_price(response)

        product['locale'] = "en-US"

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        product['category'] = category

        buyer_reviews = self.parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        variants = self._parse_variants(response)
        product['variants'] = variants

        return product

    def _parse_title(self, response):
        title = response.xpath("//span[@id='product-name']/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//span[@itemprop='brand']/text()").extract()

        if brand:
            brand = brand[0]
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _parse_ids(self, response):
        try:
            datalayer = re.search(r'(?<=var dataLayer = \[).+?(?=\];)', response.body, re.DOTALL).group(0)
            datalayer = json.loads(datalayer)
            reseller_id = datalayer.get('product_id')[0]
            sku = datalayer.get('product_sku')[0]
            return reseller_id, sku
        except:
            self.log("Failed ids parsing {}".format(traceback.format_exc()))
            return None, None

    def _parse_categories(self, response):
        categories = response.xpath("//nav[@id='breadcrumb']//span[@itemprop='name']/text()").extract()
        return categories[2:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_image_url(self, response):
        image = response.xpath("//div[@class='main']//a/@href").extract()
        return image[0] if image else None

    def _parse_currency(self, response):
        price_currency = response.xpath("//span[@itemprop='priceCurrency']/@content").extract()
        return price_currency[0] if price_currency else 'USD'

    def _parse_price(self, response):
        product = response.meta['product']
        price_currency = self._parse_currency(response)
        price = response.xpath("//span[@itemprop='price']/text()").extract()
        if price:
            price = re.findall(FLOATING_POINT_RGEX, price[0])
            cond_set_value(product, 'price',
                           Price(price=price[0].replace(',', ''),
                                 priceCurrency=price_currency))

    def _parse_out_of_stock(self, response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    def _parse_variants(self, response):
        self.hv = HsnVariants()
        self.hv.setupSC(response)
        return self.hv._variants()

    def parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        buyer_reviews_info = {}

        # Count of Review
        num_of_reviews = response.xpath(
            "//dd[contains(@class, 'rating')]//a[@class='count']/text()").re('\d+')
        num_of_reviews = num_of_reviews[0] if num_of_reviews else 0

        # Average Rating
        average_rating = response.xpath(
            "//div[@class='rating']//span[@class='value']/text()").re('\d*\.?\d+')
        average_rating = average_rating[0] if average_rating else 0

        # Get count of Mark
        rating_counts = response.xpath(
            "//dl[contains(@class, 'rating-distribution')]//span[contains(@class, 'count')]/text()").extract()

        if rating_counts:
            rating_counts = list(reversed(rating_counts))

        if len(rating_counts) == 5:
            rating_by_star = {'1': rating_counts[0], '2': rating_counts[1],
                              '3': rating_counts[2], '4': rating_counts[3], '5': rating_counts[4]}
        else:
            rating_by_star = {}

        if rating_by_star:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(average_rating),
                'rating_by_star': rating_by_star
            }

        if buyer_reviews_info:
            return BuyerReviews(**buyer_reviews_info)
        else:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    def _scrape_total_matches(self, response):
        total_match = response.xpath(
            "//*[@data-total-products]/@data-total-products").extract()

        return int(total_match[0]) if total_match else 0

    def _scrape_product_links(self, response):
        self.product_links = response.xpath("//ul/li[contains(@class, 'product-item')]"
                                            "/div[@class='info']//a[@itemprop='url']/@href").extract()

        for item_url in self.product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if not self.product_links:
            return
        next_page_link = response.xpath("//li[@class='next']"
                                        "//a[not(contains(@class, 'disabled'))]/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
