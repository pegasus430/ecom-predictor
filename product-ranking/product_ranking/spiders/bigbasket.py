from __future__ import division, absolute_import, unicode_literals

import re
import json
import urllib
import traceback

from scrapy import Request
from scrapy.log import INFO

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.spiders import FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.utils import is_empty


def is_num(s):
    try:
        int(s.strip())
        return True
    except ValueError:
        return False


class BigbasketProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'bigbasket_products'

    allowed_domains = ["www.bigbasket.com"]

    SEARCH_HTML_URL = "https://www.bigbasket.com/ps/?q={search_term}"

    AUTH_URL = "https://www.bigbasket.com/skip_explore/?c=1&l=0&s=0&n=%2F"

    product_filter = []

    SEARCH_URL = 'https://www.bigbasket.com/product/get-products/?slug={search_term}' \
                 '&page={page_num}&tab_type=["all"]&sorted_on=relevance&listtype=ps'

    PROD_URL = 'https://www.bigbasket.com/pd/{sku}'

    result_per_page = 20

    def __init__(self, *args, **kwargs):
        super(BigbasketProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page_num=1),
            *args, **kwargs)

    def start_requests(self):
        yield Request(
            self.AUTH_URL,
            callback=self._start_requests
        )

    def _start_requests(self, response):
        for st in self.searchterms:
            yield Request(
                self.SEARCH_HTML_URL.format(search_term=urllib.quote_plus(st.encode('utf-8'))),
                callback=self._after_start,
                meta={'search_term': st, 'remaining': self.quantity},
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def _after_start(self, response):
        meta = response.meta.copy()
        st = meta.get('search_term')

        total_matches = re.search(r'"ResultsCount": (\d+),', response.body)
        if total_matches:
            meta['total_matches'] = int(total_matches.group(1))

        yield Request(
            self.url_formatter.format(
                self.SEARCH_URL,
                search_term=urllib.quote_plus(st.encode('utf-8')),
            ),
            meta=meta
        )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        product['title'] = title

        brand = response.xpath("//div[@class='uiv2-brand-name']//a/text()").extract()
        if brand:
            product['brand'] = brand[0].strip()

        if not product.get('brand', None):
            brand = guess_brand_from_first_words(product.get('title').strip() if product.get('title') else '')
            if brand:
                product['brand'] = brand

        image_url = self._parse_image(response)
        product['image_url'] = image_url

        desc = self._parse_description(response)
        product['description'] = desc

        categories = self._parse_categories(response)
        product['categories'] = categories

        price, currency = self._parse_price(response)
        product['price'] = Price(price=float(price), priceCurrency=currency)

        model = self._parse_model(response)
        product["model"] = model

        variants = self._parse_variants(response)
        product["variants"] = variants

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        product['locale'] = "en-IN"

        return product

    def _parse_title(self, response):
        title = response.xpath(
            "//div[contains(@class, 'uiv2-product-heading-h2-section')]"
            "//h2/text()").extract()
        if not title:
            title = response.xpath('//div[@itemprop="name"]/h1/text()').extract()
        return title[0].strip() if title else None

    def _parse_description(self, response):
        description = response.xpath("//div[contains(@class, 'uiv2-tab-content')]//p/text()").extract()
        if description:
            description = self._clean_text(description[0]).replace('\'', '')
            return description

        return None

    def _parse_categories(self, response):
        categories = []
        categories_sel = response.xpath(
            "//div[@class='breadcrumb-item']"
            "//span[@itemprop='title']/text()").extract()

        for cat in categories_sel:
            categories.append(cat.strip())

        return categories[1:]

    def _parse_price(self, response):
        currency = is_empty(
            response.xpath('//span[@itemprop="priceCurrency"]'
                           '/@content').extract(),
            'INR'
        )

        product_id = response.xpath('//input[@id="id-product-id"]/@value').extract()
        price = None

        if product_id:
            price_xpath = '//input[@id="hdnmrp_{0}"]/@value'
            price = response.xpath(price_xpath.format(product_id[0])).extract()
        if not price:
            price = response.xpath(
                '//div[@class="uiv2-product-value"][@itemprop="offers"]'
                '//div[@class="uiv2-price"]/text()').extract()

        if price:
            price = is_empty(
                re.findall(
                    r'(\d+\.?\d?)',
                    price[0]
                ), 0.00
            )

        return price, currency

    def _parse_model(self, response):
        model = response.xpath(
            "//div[@itemtype='http://schema.org/Product']"
            "//input[@id='id-product-id']/@value"
        ).extract()

        if model:
            return model[0]

        return None

    def _parse_image(self, response):
        image = response.xpath("//div[@class='uiv2-product-large-img-container']//img/@data-src").extract()
        if image:
            image_url = 'https:' + image[0]
            return image_url

        return None

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    def _parse_variants(self, response):
        skus = response.xpath(
            "//div[@itemtype='http://schema.org/Product']"
            "//div[@class='uiv2-size-variants']"
            "//input[@type='radio']/@value").extract()
        images = response.xpath(
            "//div[@class='uiv2-product-large-img-container']"
            "//img/@data-src").extract()
        sizes = response.xpath(
            "//div[@itemtype='http://schema.org/Product']"
            "//div[@class='uiv2-size-variants']//label/text()").extract()

        attribute_list = []
        variant_list = []
        image_list = []
        attribute_values_list = []
        size_list_all = []

        for image in images:
            image = 'https:' + image
            image_list.append(image)
        if image_list:
            image_list = [r for r in list(set(image_list)) if len(r.strip()) > 0]
            attribute_values_list.append(image_list)
        for size in sizes:
            size = self._clean_text(size).replace(' ', '')
            size_list_all.append(size)
        if size_list_all:
            size_list_all = [r for r in size_list_all if len(r.strip()) > 0]
            attribute_values_list.append(size_list_all)

        if image_list:
            if 'image' not in attribute_list:
                attribute_list.append('image')
        if size_list_all:
            if 'size' not in attribute_list:
                attribute_list.append('size')

        for reindex, sku in enumerate(skus):
            variant_item = {}
            properties = {}
            for index, attribute in enumerate(attribute_list):
                properties[attribute] = attribute_values_list[index][reindex]
            variant_item['properties'] = properties

            variant_item['sku'] = sku
            variant_list.append(variant_item)

        if variant_list:
            return variant_list

    def _parse_out_of_stock(self, response):
        return not response.xpath("//meta[@itemprop='availability' and contains(@content, 'in_stock')]/@content")

    def _scrape_total_matches(self, response):
        total_matches = response.meta.get('total_matches', 0)
        return total_matches

    def _scrape_product_links(self, response):
        prods = None
        try:
            prods = json.loads(response.body)['tab_info']['product_map']['all']['prods']
        except:
            self.log(traceback.format_exc())

        if prods:
            for prod in prods:
                sku = prod.get('sku')
                if sku:
                    yield self.PROD_URL.format(sku=sku), SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(
                url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)

        total_matches = meta.get('total_matches') or self._scrape_total_matches(response)
        if current_page * self.result_per_page > total_matches:
            return

        st = meta.get('st')
        current_page += 1
        meta['current_page'] = current_page

        next_req = Request(
            self.SEARCH_URL.format(search_term=st, page_num=current_page),
            meta=meta
        )

        return next_req
