# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import urlparse

from lxml import html
from scrapy.log import WARNING
from product_ranking.items import BuyerReviews, Price, SiteProductItem as BaseSiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FLOATING_POINT_RGEX
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.surlatable_variants import SurlatableVariants
from scrapy.conf import settings
from scrapy.item import Field


class SiteProductItem(BaseSiteProductItem):
    price_sugg = Field()

class SurlatableProductsSpider(BaseProductsSpider):
    name = 'surlatable_products'
    allowed_domains = ['www.surlatable.com']

    SEARCH_URL = "https://www.surlatable.com/search/search.jsp?Ntt={search_term}"

    IMAGE_URL_TEMPLATES = "https://www.surlatable.com/images/customers/c1079/{prod_id}/{prod_id}_pdp/main_variation_Default_view_1_425x425."

    def __init__(self, *args, **kwargs):
        super(SurlatableProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(SurlatableProductsSpider, self).start_requests():
            meta = request.meta.copy()
            product = SiteProductItem()
            product['url'] = self.product_url
            meta['product'] = product
            request = request.replace(meta=meta)
            yield request

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse price:
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image
        if reseller_id:
            image_url = self.IMAGE_URL_TEMPLATES.format(prod_id=reseller_id)
            cond_set_value(product, 'image_url', image_url)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        buyer_reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        buy_save_percent = self._parse_buy_save_percent(response)
        product['buy_save_percent'] = buy_save_percent

        price_sugg = self._parse_price_sugg(response)
        product['price_sugg'] = price_sugg

        # Parse promotions
        product['promotions'] = any(
            [
                product.get('buy_save_percent'),
                product.get('price_sugg')
            ]
        )

        return product

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = response.xpath("//input[@name='productID']/@value").extract()
        return reseller_id[0] if reseller_id else None

    def _parse_title(self, response):
        title = response.xpath('//h1[@id="product-title"]/text()').extract()
        return self._clean_text(title[0]) if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//span[@itemprop='brand']/text()").extract()
        if brand:
            brand = brand[0]
        elif title:
            brand = guess_brand_from_first_words(title)
        return self._clean_text(brand) if brand else None

    def _parse_sku(self, response):
        sku = response.xpath("//input[@name='skuId']/@value").extract()
        return self._clean_text(sku[-1]) if sku else None

    def _parse_categories(self, response):
        categories = []
        breadcrumbs = response.xpath("//div[@id='product-breadcrumbs']//span").extract()
        for ct in breadcrumbs:
            if '<a ' in ct:
                category = html.fromstring(ct).xpath(".//a/text()")
                if category:
                    categories.append(self._clean_text(category[0]))
            if '<label ' in ct:
                category = html.fromstring(ct).xpath(".//label/text()")
                if category:
                    categories.append(self._clean_text(category[0]))

        return categories if categories else None

    def _parse_description(self, response):
        description = ''.join(response.xpath("//div[@itemprop='description']/text()").extract())
        ul_description = response.xpath("//div[@itemprop='description']//ul").extract()
        if ul_description:
            description = ''.join([description, ul_description[0]])

        return self._clean_text(description) if description else None

    @staticmethod
    def _parse_price(response):
        price = response.xpath("//span[@itemprop='price']/text()").re(FLOATING_POINT_RGEX)
        if price:
            return Price(price=price[0], priceCurrency='USD')

    def _parse_variants(self, response):
        price_amount = self._parse_price(response)
        if price_amount:
            price_amount = float(price_amount.price)
        self.sv = SurlatableVariants()
        self.sv.setupSC(response)
        return self.sv._variants(price_amount)

    def _parse_buyer_reviews(self, response):
        zero_reviews_value = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        buyer_reviews = {}
        stars = []
        review_count = response.xpath("//div[@class='TT2left']//meta[@itemprop='reviewCount']/@content").re('\d+')
        review_count = review_count[0] if review_count else 0

        average_rating = response.xpath("//div[@class='TT2left']//meta[@itemprop='ratingValue']/@content").re(
            '\d+\.?\d*')

        for i in range(1, 6):
            rating_value = response.xpath("//div[@id='TTreviewSummaryBreakdown-" + str(i) + "']/text()").re('\d+')
            if rating_value:
                stars.append(int(rating_value[0]))
        if len(stars) == 5:
            rating_by_star = {'1': stars[0], '2': stars[1],
                              '3': stars[2], '4': stars[3], '5': stars[4]}
        else:
            rating_by_star = {}

        if rating_by_star:
            buyer_reviews = {
                'num_of_reviews': review_count,
                'average_rating': round(float(average_rating[0]), 1) if average_rating else 0,
                'rating_by_star': rating_by_star
            }

        if buyer_reviews:
            return BuyerReviews(**buyer_reviews)

        else:
            return BuyerReviews(**zero_reviews_value)

    @staticmethod
    def _parse_out_of_stock(response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    @staticmethod
    def _parse_buy_save_percent(response):
        save_percent = response.xpath('//div[@class="product-priceInfo"]//span[@id="product-priceSaving"]/span/text()').extract()
        return save_percent[0].replace('%', '') if save_percent else None

    @staticmethod
    def _parse_price_sugg(response):
        sugg_info = response.xpath(
            '//div[@class="product-priceInfo"]//span[@id="product-priceList"]/span/text()').extract()
        return sugg_info[0].replace('$', '') if sugg_info else None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        totals = response.xpath("//input[@id='omn_searchResultSize']/@value").re('\d+')
        return int(totals[0]) if totals else None

    def _scrape_results_per_page(self, response):
        item_count = response.xpath('//button[@name="items-per-page_btn"]/span/text()').extract()
        if item_count:
            item_count = item_count[0].strip()
            return item_count

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath("//dd[@class='productinfo']//a/@href").extract()

        if items:
            for item in items:
                link = urlparse.urljoin(response.url, item)
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), WARNING)

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath("//li[contains(@class, 'nextpage')]//a/@href").extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[-1])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
