from __future__ import division, absolute_import, unicode_literals
import urllib

from scrapy import Request
from scrapy.log import WARNING
import re
import urlparse
from product_ranking.items import SiteProductItem, Price, RelatedProduct, \
    BuyerReviews
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults
from product_ranking.spiders import cond_set, cond_set_value
from product_ranking.settings import ZERO_REVIEWS_VALUE

class HairShop24Spider(BaseProductsSpider):
    """
    hair-shop24.net product spider.

    'upc' field is missing

    Takes 'order' argument  with following possible values:

    * 'relevance'
    * 'name'
    * 'price'
    * 'item'
    Sort items from largest to smallest
    """
    name = 'hair_shop24_products'

    allowed_domains = ["hair-shop24.net"]
    start_urls = []

    SEARCH_URL = "http://www.hair-shop24.net/catalogsearch" \
        "/result/index/?dir=&order={sort_mode}&q={search_term}"
    SORTING = None

    SORT_MODES = {
        'default': '',
        'relevance': 'relevance',
        'name': 'name',
        'price': 'price',
        'item': 'produktserie',
    }

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode:
            if sort_mode.lower() not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
            else:
                self.SORTING = self.SORT_MODES[sort_mode.lower()]

        super(HairShop24Spider, self).__init__(
            url_formatter=FormatterWithDefaults(
                sort_mode=self.SORTING or self.SORT_MODES['default']),
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def start_request(self):
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                self.create_link,
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
                yield Request(url, self._parse_single_product, 
                              meta={'product': prod})

    def create_link(self, response):
        if not self.SORTING:
            self.SORTING = ''
        url = response.url + '&Ns=' + self.SORTING
        return Request(url, meta=response.meta, dont_filter=True)

    def parse_product(self, response):
        product = response.meta['product']

        prod_name = response.xpath(
            "//div[@class='product-name']/h1/text()")
        cond_set_value(
            product,
            'title',
            "\n".join(x.strip() for x in prod_name.extract() if x.strip()))

        cond_set(
            product,
            'image_url',
            response.xpath(
                "//div[@class='MagicToolboxContainer']/a/img/@src").extract(),
            lambda url: urlparse.urljoin(response.url, url)
        )

        desc = response.xpath(
            "//div[contains(@class, 'product-description-wrapper')]"
            "/div[@class='std']//text()").extract()

        cond_set_value(product, 
                       'description', 
                       "\n".join(x.strip() for x in desc if x.strip()))

        price = response.xpath(
            "//div[@class='product-options-bottom']/div[@class='price-box']"
            "//span[@class='price']/text()").re('\d{1,},\d{2}')
        price_now = response.xpath(
            "//div[@class='price-box']/p"
            "/span[@class='price']/text()").re('\d{1,},\d{2}')
        special_price = response.xpath(
            "//div[@itemprop='offers']//p[@class='special-price']"
            "/span[@class='price']/text()").re('\d{1,},\d{2}')

        price_one = '0.0'
        if price:
            price_one = price[0].replace(',', '.')
        elif special_price:
            price_one = special_price[0].replace(',', '.')
        elif price_now:
            price_one = price_now[0].replace(',', '.')

        product['price'] = Price(price=price_one, priceCurrency='EUR')
        cond_set_value(product, 'locale', 'de_DE')

        reseller_id = response.xpath('//*[@class="product_id"]/text()').extract()
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        rel_key = response.xpath(
            "//div[@class='box-collateral box-cross-sell box-up-sell block']"
            "/h2/text()").extract()

        if rel_key:
            related = []
            related_products = {}

            related.append(RelatedProduct(
                title=response.xpath(
                    "//div[@class='box-collateral box-cross-sell box-up-sell "
                    "block']/ol/li/h3/a/@title").extract(),
                url=response.xpath(
                    "//div[@class='box-collateral box-cross-sell "
                    "box-up-sell block']/ol/li/h3/a/@href").extract()))

            related_products[rel_key[0]] = related
            product['related_products'] = related_products

        # Parse buyer reviews
        buyer_reviews = self._parse_buyer_review(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        return product

    def _parse_buyer_review(self, response):
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        stars = response.xpath('//div[@class="box-collateral box-reviews"]'
                               '/dl/dt/div/div/@style').extract()
        points = []
        for star in stars:
            point = re.findall(r'(\d+)', star)

            if point[0] == '100':
                points.append(5)
            elif point[0] == '80':
                points.append(4)
            elif point[0] == '60':
                points.append(3)
            elif point[0] == '40':
                points.append(2)
            elif point[0] == '20':
                points.append(1)
        for point in points:
            rating_by_star[str(point)] += 1
        average_rating = response.xpath('//meta[@itemprop="ratingValue"]'
                                        '/@content').extract()
        num_of_reviews = len(points)
        if stars:
            buyer_reviews = {
                    'num_of_reviews': int(num_of_reviews),
                    'average_rating': float(average_rating[0]),
                    'rating_by_star': rating_by_star
            }
        else:
            return ZERO_REVIEWS_VALUE

        return BuyerReviews(**buyer_reviews)

    def _scrape_total_matches(self, response):
        totals = response.xpath(
            "//div[@class='page-title']/h1/text()").re('\d{1,}')
        if totals:
            try:
                total_matches = int(totals[0])
            except ValueError:
                self.log(
                    "Failed to parse number of matches: %r" % totals, WARNING)
                total_matches = None
        elif "Sorry, we can't find any matches for" \
                in response.body_as_unicode():
            total_matches = 0
        else:
            total_matches = None

        return total_matches

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//div[@class="category-products"]/ul/li/a/@href').extract()
        if not links:
            self.log("Found no product links.", WARNING)

        for no, link in enumerate(links):
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_links = response.xpath(
            "//div[@class='category-products']/div[1]"
            "/div/div/ol/li[4]/a/@href").extract()
        if next_page_links:
            return next_page_links[0]
