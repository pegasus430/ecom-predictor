# -*- coding: utf-8 -*-
import re
import json
import traceback
from lxml import html
from urlparse import urlparse

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults

from scrapy import Request
from scrapy.log import ERROR, DEBUG


class IteminfoProductsSpider(BaseProductsSpider):
    name = 'iteminfo_products'
    allowed_domains = ['iteminfo.com']

    PRODUCT_URL = 'http://iteminfo.com/GetProduct/{product_id}'
    REVIEW_URL = 'https://cdn.powerreviews.com/repos/15458/pr/pwr/content/{review_part}/contents.js'
    SEARCH_URL = 'http://www.iteminfo.com/search/k_{search_term}/ps_12/pg_{page_num}/so_ts'

    def __init__(self, *args, **kwargs):
        self.total_matches = None
        url_formatter = FormatterWithDefaults(page_num=1)
        super(IteminfoProductsSpider, self).__init__(
            url_formatter=url_formatter,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def start_requests(self):
        for request in super(IteminfoProductsSpider, self).start_requests():
            if self.product_url:
                product_id = urlparse(self.product_url).path.split('/')[-1]
                url = self.PRODUCT_URL.format(product_id=product_id)
                request = request.replace(url=url)
            else:
                st = request.meta.get('search_term')
                url = self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=st.encode('utf-8'),
                )
                request = request.replace(url=url)
            request = request.replace(dont_filter=True)
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    @staticmethod
    def _parse_url(response):
        url = response.url
        if 'Get' in url:
            url = url.replace('GetProduct', 'product')
        return url

    def parse_product(self, response):
        product = response.meta.get('product', SiteProductItem())
        try:
            product_json = json.loads(response.body)
            product_json = json.loads(product_json['Model'])
        except:
            self.log('Error parsing product_json: {}'.format(traceback.format_exc()))
            return product

        title = self._parse_title(product_json)
        cond_set_value(product, 'title', title)

        price = self._parse_price(product_json)
        cond_set_value(product, 'price', price)

        description = self._parse_description(product_json)
        cond_set_value(product, 'description', description)

        image_url = self._parse_image(product_json)
        cond_set_value(product, 'image_url', image_url)

        brand = self._parse_brand(product_json)
        cond_set_value(product, 'brand', brand)

        categories = self._parse_categories(product_json)
        cond_set_value(product, 'categories', categories)

        url = self._parse_url(response)
        product['url'] = url

        if categories:
            department = categories[-1]
            cond_set_value(product, 'department', department)

        sku = self._parse_sku(product_json)
        cond_set_value(product, 'sku', sku)

        product['locale'] = "en-US"

        product_model = product_json.get('ItemSummary').get('Sku')
        review_part = self.get_review_url_part(product_model)
        url = self.REVIEW_URL.format(review_part=review_part)
        meta = response.meta
        meta['product'] = product
        meta['product_model'] = product_model
        return Request(url, callback=self._parse_reviews, meta=meta, dont_filter=True)

    @staticmethod
    def _parse_title(product_json):
        title = product_json.get('Item').get('Title')
        return title

    @staticmethod
    def _parse_price(product_json):
        price = product_json.get('ItemExtension').get('Price')
        return Price(price=price, priceCurrency='USD') if price else None

    @staticmethod
    def _parse_image(product_json):
        base_image = product_json.get('ResourceHelper').get('ProductBaseImage')
        image_url = None
        if base_image:
            image_url = base_image.get('Url')
        return image_url

    @staticmethod
    def _parse_brand(product_json):
        content = product_json.get('Panels').get('Datasheet')
        if content:
            content = html.fromstring(content)
            brand = content.xpath('//tr[contains(td/text(), "Brand Name")]/td[@class="attr-val"]/text()')
            return brand[0] if brand else None

    @staticmethod
    def _parse_categories(product_json):
        categorieCrumbs = product_json.get('CategoryCrumbs', [])
        categories = [category.get('Name') for category in categorieCrumbs]
        return categories

    @staticmethod
    def _parse_sku(product_json):
        sku = product_json.get('SkuHelper').get('Sku_Catalog')
        return sku

    @staticmethod
    def _parse_description(product_json):
        des = product_json.get('Item').get('Description')
        return des

    def _parse_reviews(self, response):
        product = response.meta.get('product')
        content = re.findall(r'\] = (.*?)};', response.body)
        product_model = response.meta.get('product_model')
        try:
            content = json.loads(content[0] + '}')
            content = content.get('locales').get('en_US', {})
            for key, item in content.iteritems():
                if product_model in key:
                    reviews = item.get('reviews')
                    buyer_reviews = {
                        'num_of_reviews': int(reviews.get('review_count', '0')),
                        'average_rating': float(reviews.get('avg', '0.0')),
                        'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                    }
                    for star, rating in enumerate(reviews.get('review_ratings', [])):
                        buyer_reviews['rating_by_star'][str(star + 1)] = rating
                    product['buyer_reviews'] = buyer_reviews

        except:
            self.log('Error parsing reviews: {}'.format(traceback.format_exc()))
            product['reviews'] = None
        finally:
            return product

    @staticmethod
    def get_review_url_part(product_model):
        """This method was created as copy of javascript function g(c4) from
        full.js. It will generate numerical part of url for reviews.
        example: 06/54 for url
        http://www.bjs.com/pwr/content/06/54/P_159308793-en_US-meta.js

        I use the same variables names as in js, but feel free to change them
        """
        c4 = product_model
        c3 = 0
        for letter in c4:
            c7 = ord(letter)
            c7 = c7 * abs(255 - c7)
            c3 += c7

        c3 = c3 % 1023
        c3 = str(c3)

        cz = 4
        c6 = list(c3)

        c2 = 0
        while c2 < (cz - len(c3)):
            c2 += 1
            c6.insert(0, "0")

        c3 = ''.join(c6)
        c3 = c3[0: 2] + '/' + c3[2: 4]
        return c3

    def _scrape_total_matches(self, response):
        if self.total_matches:
            return self.total_matches
        total_matches = re.findall(r'"TotalCount":(\d+)', response.body)
        if total_matches:
            self.total_matches = int(total_matches[0])
            return self.total_matches

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page')

        if not current_page:
            current_page = 1
        if current_page * 12 >= self.total_matches:
            return
        current_page += 1
        st = meta['search_term']
        url = self.SEARCH_URL.format(page_num=current_page, search_term=st)
        meta['current_page'] = current_page
        return Request(
            url,
            meta=meta,)

    def _scrape_product_links(self, response):
        links = []
        try:
            contents = re.findall(r'var pageData = (.*?)};', response.body)
            contents = contents[0] + '}'
            contents = json.loads(contents)
            contents = contents.get("Products", [])
            for content in contents:
                if not content.get('Id'):
                    continue
                product_id = content.get('Id')
                link = self.PRODUCT_URL.format(product_id=product_id)
                links.append(link)

        except Exception as e:
            self.log("Exception looking for product links {}".format(e), DEBUG)
            self.log("Exception looking for product links: {}".format(traceback.format_exc()))
        finally:
            for link in links:
                yield link, SiteProductItem()
