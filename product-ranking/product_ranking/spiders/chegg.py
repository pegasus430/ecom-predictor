
from __future__ import division, absolute_import, unicode_literals

import re
import json
import itertools
import urlparse
from scrapy.http import Request
import urllib

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, cond_set_value,\
    FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.spiders import FormatterWithDefaults, dump_url_to_file
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import guess_brand_from_first_words

is_empty = lambda x, y=None: x[0] if x else y

def is_num(s):
    try:
        int(s.strip())
        return True
    except ValueError:
        return False

class CheggProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'chegg_products'
    allowed_domains = ["www.chegg.com"]
    start_urls = []

    SEARCH_URL = "http://www.chegg.com/search/{search_term}"
    PRODUCTS_URL = "https://www.chegg.com/_ajax/federated/search?query={query}&search_data=%7B%22chgsec%22%3A%22searchsection%22%2C%22chgsubcomp%22%3A%22serp%22%2C%22state%22%3A%22NoState%22%2C%22profile%22%3A%22textbooks-srp%22%2C%22page-number%22%3A{page_number}%7D&token={token}"
    product_filter = []
    use_proxies = False

    def __init__(self, *args, **kwargs):
        # All this is to set the site_name since we have several
        # allowed_domains.
        self.br = BuyerReviewsBazaarApi()
        super(CheggProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)
        self.site_url = "http://www.chegg.com"
        self.current_page = 0

    def start_requests(self):
        for search_term in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(search_term.encode('utf-8')),
                ),
                meta={'search_term': search_term, 'remaining': self.quantity},
                callback=self._parse_helper
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          callback=self._parse_single_product,
                          meta={'product': prod})

    def _parse_helper(self, response):
        self.current_page = self.current_page + 1
        self.category_name = response.meta['search_term'].split()[0].lower()
        self.token = re.search('csrfToken = (.*?);', response.body, re.DOTALL).group(1).replace("\'", "")
        return Request(self.PRODUCTS_URL.format(query=self.category_name, page_number=self.current_page, token=self.token),
                       meta={'search_term': response.meta['search_term'], 'remaining': self.quantity})

    def _scrape_total_matches(self, response):
        return None

    def _scrape_product_links(self, response):
        product_links = []
        product_json = json.loads(response.body)
        links_info = product_json['textbooks']['responseContent']['docs']
        for links in links_info:
            product_links.append(self.site_url + links['url'])

        for item_url in product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        prod_links = self._scrape_product_links(response)
        if not prod_links:
            return None
        self.current_page = self.current_page + 1
        st = response.meta['search_term']
        return Request(
            self.url_formatter.format(
                self.PRODUCTS_URL,
                page_number=self.current_page,
                token=self.token,
                query=self.category_name
            ),
            meta={
                'search_term': st,
                'remaining': self.quantity,
                'page': self.current_page}, )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):

        product = response.meta['product']

        brand = guess_brand_from_first_words(product.get('title').strip() if product.get('title') else '')
        product['brand'] = brand

        title = self._parse_title(response)
        product['title'] = title

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        if price:
            if not '$' in  price:
                price = '$' + price
        product['price'] = price

        if product.get('price', None):
            if not '$' in product['price']:
                self.log('Unknown currency at' % response.url)
            else:
                product['price'] = Price(
                    price=product['price'].replace(',', '').replace(
                        '$', '').strip(),
                    priceCurrency='USD'
                )

        product['locale'] = "en-US"

        description = self._parse_description(response)
        product['description'] = description

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        product['category'] = category

        return product

    def _parse_title(self, response):
        item_title = ''.join(response.xpath("//span[@itemprop='name']/text()").extract())
        book_title = ''.join(response.xpath("//span[@class='book-title-name']/text()").extract())
        if item_title:
            title = item_title
        elif book_title:
            title = book_title
        return title if title else None

    def _parse_image(self, response):
        image = response.xpath("//img[@itemprop='image']/@src").extract()
        if image:
            image = 'http:' + image[0]
        return image

    def _parse_price(self, response):
        price = re.search('"price":(.*?),', response.body, re.DOTALL)
        if price:
            price = price.group(1).replace('\"', '')
        return price

    def _parse_categories(self, response):
        categories = response.xpath("//div[contains(@class, 'txt-2-small global-breadcrumb')]//a/text()").extract()

        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_description(self, response):
        description = response.xpath("//div[@itemprop='description']//span/text()").extract()
        return ''.join(description) if description else None


