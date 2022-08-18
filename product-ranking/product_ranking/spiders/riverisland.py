from __future__ import division, absolute_import, unicode_literals
import re
import string
import urllib
import urlparse

from scrapy.log import ERROR, WARNING
from scrapy.http import Request

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    cond_set_value, cond_replace, FormatterWithDefaults, \
    populate_from_open_graph

is_empty = lambda x, y=None: x[0] if x else y

class RiverislandProductsSpider(BaseProductsSpider):
    name = 'riverisland_products'

    allowed_domains = ["riverisland.com"]

    start_urls = []

    SEARCH_URL = "http://www.riverisland.com/search?Ntt={search_term}"

    SORTING = None
    SORT_MODES = {
        'default': '',
        'price_low_to_high': 'p_list_price_gbp|0',
        'price_high_to_low': 'p_list_price_gbp|1',
        'latest': 'p_latest|1',
        'oldest': 'p_latest|0',
    }

    urls_list = []
    current_cat_id = 0
    total_matches = 0

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode:
            if sort_mode.lower() not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
            else:
                self.SORTING = self.SORT_MODES[sort_mode.lower()]

        super(RiverislandProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                sort_mode=self.SORTING or self.SORT_MODES['default']),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                self._parse_all_cat,
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

        if self.products_url:
            urls = self.products_url.split('||||')
            for url in urls:
                prod = SiteProductItem()
                prod['url'] = url
                prod['search_term'] = ''
                yield Request(url,
                              self._parse_single_product,
                              meta={'product': prod})

    def _parse_all_cat(self, response):
        if not self.SORTING:
            self.SORTING = ''
        self.urls_list = response.xpath(
            "//div[contains(@class,'gender-view-all-cont')]"
            "/p/a/@href").extract()
        no_results_message = "Sorry, we can't seem to find any results for"

        all_totals = response.xpath(
            "//div[contains(@class,'gender-view-all-cont')]"
            "/p[contains(@class,'gender-title')]/text()"
            ).extract()
        if all_totals:
            for t in all_totals:
                t = re.findall('\d+', t)
                if t:
                    self.total_matches += int(t[0])
        elif no_results_message in response.body_as_unicode():
            self.total_matches = 0
        else:
            self.total_matches = None

        if self.urls_list:
            for i, url in enumerate(self.urls_list):
                self.urls_list[i] += '&Ns=' + self.SORTING
            result_url = urlparse.urljoin(response.url, self.urls_list[0])
            return Request(result_url,
                meta=response.meta, dont_filter=True)
        elif no_results_message in response.body_as_unicode():
            self.log('No results found', WARNING)

    def parse_product(self, response):
        product = response.meta['product']

        populate_from_open_graph(response, product)

        cond_set(
            product,
            'title',
            response.xpath('//meta[@property="og:title"]/@content').extract(),
            conv=string.strip)

        if not product.get('brand', None):
            brand = guess_brand_from_first_words(
                product.get('title', None).strip())
            if brand:
                product['brand'] = brand

        cond_replace(
            product,
            'image_url',
            response.css(
                ".main-image-container>img::attr(src)"
            ).extract(),
            lambda url: urlparse.urljoin(response.url, url)
        )

        prod_description = response.css(
            ".product-details-container .description-copy p::text"
        )
        cond_set_value(product, 'description', "\n".join(
            x.strip() for x in prod_description.extract() if x.strip()))

        sku = response.css(
            ".product-details-container .caption-2::text").extract()
        if sku:
            sku = re.findall('\d+', sku[0])
        else:
            sku = None
        cond_set(product, 'sku', sku, string.strip)

        cond_set(product, 'reseller_id', sku, string.strip)

        price_now = response.css(
            ".product-details-container .right-side .price .sale::text"
            ).extract()
        if not price_now:
            price = response.css(
                ".product-details-container .right-side .price span::text"
                ).extract()
        else:
            price = price_now

        cond_set(
            product,
            'price', price,
            conv=string.strip,
        )
        if price:
            product['price'] = Price(
                price=product['price'].replace(u'\xa3', '').strip(),
                priceCurrency='GBP')

        related_products = self._parse_related(response)
        cond_set_value(product, 'related_products', related_products)

        cond_set_value(product, 'locale', 'en-GB')

        sample = response.xpath('//select[@id="SizeKey"]/option/text()').extract()
        variants = []

        for index, i in enumerate(sample):
            if index > 0:
                var = i.replace('Size ', '')
                variants.append(var.strip())

        variant_list = []
        for variant in variants:
            variant_item = {}
            properties = {}

            if 'out of stock' in variant:
                properties['size'] = variant.replace(' (out of stock)', '')
            else:
                properties['size'] = variant

            variant_item['price'] = price[0].replace(u'\xa3', '').strip()
            variant_item['in_sock'] = False if 'out of stock' in variant else True
            variant_item['properties'] = properties
            variant_item['selected'] = False

            variant_list.append(variant_item)

        product['variants'] = variant_list

        return product

    def _parse_related(self, response):
        """
        Parses related products
        """
        related_products = []

        # Parse wear it with products
        wear_it_with = response.css(
            '.greatwithany .items-container div ul li')

        if wear_it_with:
            for item in wear_it_with:
                title = is_empty(item.xpath('.//a/@title').extract(), '')
                url = is_empty(item.xpath('.//a/@href').extract(), '')

                if url:
                    url = urlparse.urljoin(response.url, url)
                    if title:
                        related_products.append(RelatedProduct(
                            title=title.strip(),
                            url=url))

        return related_products

    def _scrape_total_matches(self, response):
        return self.total_matches

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//ul[contains(@class,'products-listing')]/li/a/@href"
            ).extract()
        if not links:
            self.log("Found no product links.", WARNING)

        for no, link in enumerate(links):
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_links = response.xpath(
            "//div[contains(@class, 'paginator')]"
            "/a[contains(@class, 'next-icon')]/@href").extract()
        cat_id_count = len(self.urls_list)
        if next_page_links:
            return next_page_links[0]
        elif self.current_cat_id < cat_id_count - 1:
            self.current_cat_id += 1
            return self.urls_list[self.current_cat_id]
