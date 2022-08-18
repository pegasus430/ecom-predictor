from __future__ import division, absolute_import, unicode_literals

import re

from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price, BuyerReviews,\
    RelatedProduct, LimitedStock
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    FormatterWithDefaults, cond_set_value, dump_url_to_file
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.validation import BaseValidator
from product_ranking.validators.maplin_validator import MaplinValidatorSettings

is_empty = lambda x, y="": x[0] if x else y

# scrapy crawl maplin_products -a searchterms_str="Earth" [-a order=default]
class MaplinProductsSpider(BaseValidator, BaseProductsSpider):
    name = "maplin_products"
    allowed_domains = ["www.maplin.co.uk"]
    start_urls = []

    settings = MaplinValidatorSettings

    SEARCH_URL = "http://www.maplin.co.uk/search?text={search_term}&x=0&y=0"\
                 "&sort={search_sort}"

    product_link = "http://www.maplin.co.uk"
    product_link_next_page = "http://www.maplin.co.uk/search"

    SORT_MODES = {
        'default': '',
        'best_seller': '',  # default
        'price_asc': '=MaplinProduct.price|0',
        'price_desc': '=MaplinProduct.price|1',
        'name_asc': '=MaplinProduct.name|0',
        'name_desc': '=MaplinProduct.name|1'
    }

    RECOMM_URL = "http://www.maplin.co.uk/thefilter/"\
                 "showCrossSellAndUpSellProducts?productCode={prod_id}"

    def __init__(self, order='default', *args, **kwargs):
        if order not in self.SORT_MODES.keys():
            self.log("'%s' not in SORT_MODES. Used default for this session"
                     % order, WARNING)
            order = 'default'
        search_sort = self.SORT_MODES[order]
        super(MaplinProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                search_sort=search_sort,
            ), *args, **kwargs
        )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        reviewed = response.meta.get('reviewed')
        prod = response.meta['product']

        # if there was no any request for item review try to send it
        if not reviewed:
            revs_a = response.xpath(
                '//a[@class="read_reviews_action"]'
            )
            if revs_a:
                avg = revs_a.xpath(
                    './/span[@itemprop="ratingValue"]/text()'
                ).extract()
                total = revs_a.xpath(
                    './/span[@itemprop="ratingCount"]/text()'
                ).extract()
                rev_url = response.url + '/reviewhtml/all'
                meta = response.meta.copy()
                meta['avg'] = avg
                meta['total'] = total
                meta['initial_response'] = response
                return Request(rev_url, callback=self.populate_reviews,
                               meta=meta)
            else:
                cond_set_value(prod, 'buyer_reviews', ZERO_REVIEWS_VALUE)
        title = response.xpath(
            '//div[@class="product-summary"]/h1/text()'
        ).extract()
        cond_set(prod, 'title', title)

        brand = [is_empty(
                        re.findall(r'"manufacturer":\s"(.*)",', response.body),
                        None)]
        if not brand:
            if prod.get("title"):
                brand = is_empty([guess_brand_from_first_words(prod['title'])], None)
        if brand:
            cond_set(prod, 'brand', brand)

        if not prod.get('brand', None):
            dump_url_to_file(response.url)
        price = response.xpath(
            '//p[@class="new-price"]/meta[@itemprop="price"]/@content'
        ).extract()
        priceCurrency = response.xpath(
            '//p[@class="new-price"]/meta[@itemprop="priceCurrency"]/@content'
        ).extract()
        if price and priceCurrency:
            if re.match("\d+(.\d+){0,1}", price[0]):
                prod["price"] = Price(priceCurrency=priceCurrency[0],
                                      price=price[0])
            else:
                prod["price"] = Price(priceCurrency="GBP", price=0.00)
        else:
            prod["price"] = Price(priceCurrency="GBP", price=0.00)

        des = response.xpath('//div[@class="productDescription"]').extract()
        cond_set(prod, 'description', des)

        img_url = response.xpath(
            '//div[@class="product-images"]/img/@src'
        ).extract()
        cond_set(prod, 'image_url', img_url)

        cond_set(prod, 'locale', ['en-US'])

        if not prod.get("reseller_id"):
            reseller_id = response.xpath('.//*[@itemprop="sku"]/text()').extract()
            cond_set(prod, 'reseller_id', reseller_id)

        prod['url'] = response.url

        available = response.xpath(
            '//form[contains(@id,"addToCartForm")]/input[@type="submit"]/@value'
        ).extract()

        if available and 'Email when back in stock' in available[0]:
            cond_set(prod, 'is_out_of_stock', [True])

        if available and 'Last few in store' in available[0]:
            lim = LimitedStock(is_limited=True,
                               items_left=[1])
            cond_set(prod, 'limited_stock', [lim])

        prod_id = re.findall(r'"id":\s"(.*)",', response.body)
        if prod_id:
            recomm_url = self.RECOMM_URL.format(prod_id=prod_id[0])
            return Request(recomm_url, callback=self.populate_recommendations,
                           meta=response.meta.copy())

        return prod

    def populate_recommendations(self, response):
        items = response.xpath('//li/div/h4')
        related = []
        for item in items:
            name = item.xpath('.//a/text()').extract()
            link = item.xpath('.//a/@href').extract()
            if name and link:
                name = name[0]
                final_link = "http://www.maplin.co.uk/" + link[0]
                related.append(RelatedProduct(title=name, url=final_link))
        product = response.meta['product']
        product['related_products'] = related
        return product

    def populate_reviews(self, response):
        product = response.meta['product']
        avg = response.meta['avg']
        avg = float(avg[0])
        total = response.meta['total']
        total = int(total[0])
        all_revs = response.xpath(
            '//meta[@itemprop="ratingValue"]/@content'
        ).extract()
        stars = {}
        for number in range(1, 6):
            pattern = '%s.0' % number
            quantity = all_revs.count(pattern)
            stars[number] = quantity

        if total:
            product['buyer_reviews'] = BuyerReviews(total, avg, stars)
        else:
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE

        initial_response = response.meta['initial_response']
        initial_response.meta['reviewed'] = True
        return self.parse_product(initial_response)

    def _scrape_total_matches(self, response):
        if "Sorry, we couldn't find any results for your search" \
                in response.body_as_unicode():
            return 0
        total_matches = None
        if 'No products found matching the search criteria'\
                in response.body_as_unicode():
            total_matches = 0
        total = response.xpath(
            '//div[@class="list-summary clearfix"]/p/text()'
            ).extract()
        if total:
            total = re.findall("(\d+(,\d+){0,5})", total[0])
        total_matches = int(''.join(total[0][0].split(",")))

        return total_matches

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//div[@class="tileinfo"]/h3/a/@href').extract()

        for link in links:
            yield self.product_link + link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        link = response.xpath(
            '//ul[@class="pagination"]/li[last()]/a/@href'
        )
        if link:
            return self.product_link_next_page + link.extract()[0].strip()
        return None

    def _parse_single_product(self, response):
        return self.parse_product(response)
