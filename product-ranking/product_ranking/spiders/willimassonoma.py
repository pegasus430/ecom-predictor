from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
import urlparse

from scrapy.http import Request
from scrapy.log import WARNING
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value,\
    FormatterWithDefaults
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from spiders_shared_code.williamssonoma_variants import WilliamssonomaVariants


class WilliamssonomaProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'williamssonoma_products'
    allowed_domains = ["www.williams-sonoma.com"]

    SEARCH_URL = "https://www.williams-sonoma.com/search/results.html?words={search_term}"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?passkey=35scpqb6wtdhtvrjdydkd7d6v&apiversion=5.5" \
                 "&displaycode=3177-en_us&resource.q0=products" \
                 "&filter.q0=id%3Aeq%3A{product_id}" \
                 "&stats.q0=reviews&filteredstats.q0=reviews"

    HEADERS = {
        'Accept-Language': 'en-US,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/37.0.2049.0 Safari/537.36',
        'x-forwarded-for': '127.0.0.1'
    }

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(WilliamssonomaProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        for request in super(WilliamssonomaProductsSpider, self).start_requests():
            request = request.replace(headers=self.HEADERS)
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        try:
            data = json.loads(
                response.xpath(
                    "//body/script[@type='application/ld+json'][1]/text()"
                ).extract()[0]
            )
        except:
            self.log('JSON not found or invalid JSON: {}'
                     .format(traceback.format_exc()))
            product['not_found'] = True
            return product

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        stock_status = data.get('offers', {}).get('availability')
        if stock_status:
            cond_set_value(product, 'is_out_of_stock', 'OutOfStock' in stock_status)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        self._parse_price(response, data)

        product['locale'] = "en-US"

        description = self._parse_description(response)
        product['description'] = description

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._department(response)
        product['department'] = department

        variants = self._parse_variants(response)
        product['variants'] = variants

        product_id = self._find_between(response.body, 'prodID : "', '",')
        if product_id:
            return Request(self.REVIEW_URL.format(product_id=product_id),
                           dont_filter=True,
                           meta=response.meta,
                           callback=self.br._parse_buyer_reviews_from_filters,
                           )
        return product

    def _parse_title(self, response):
        title = response.xpath("//div[@class='pip-summary']//h1/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = self._clean_text(self._find_between(response.body, "brand:", ", pipHeroImage"))

        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//ul[@class='breadcrumb-list']//span[@itemprop='name']/text()").extract()
        return categories[1:] if categories else None

    def _department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_description(self, response):
        description = response.xpath("//div[@class='accordion-tab-copy']").extract()
        return self._clean_text(''.join(description)) if description else None

    def _parse_image_url(self, response):
        image = response.xpath("//div[@class='hero-image toolbox-for-pip']//a//img/@src").extract()
        return image[0] if image else None

    def _parse_price(self, response, data):
        product = response.meta['product']
        price = data.get('offers', {}).get('price')
        min_price = data.get('offers', {}).get('lowPrice')
        currency = data.get('offers', {}).get('priceCurrency', 'USD')

        if not price and min_price:
            price = min_price
        if price:
            cond_set_value(product, 'price', Price(price=float(price), priceCurrency=currency))

    def _parse_variants(self, response):
        self.wv = WilliamssonomaVariants()
        self.wv.setupSC(response)
        return self.wv._variants()

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//li[@id='products']//span/text()").re('\d+')

        return int(total_match[0]) if total_match else 0

    def _scrape_product_links(self, response):
        links = response.xpath("//a[@class='product-name']/@href").extract()

        for item_url in links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_link = response.xpath("//a[@id='nextPage']/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _find_between(self, s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""