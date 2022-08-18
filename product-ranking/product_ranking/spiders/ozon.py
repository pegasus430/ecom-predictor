from __future__ import division, absolute_import, unicode_literals
from future_builtins import map

import string
import urlparse
import re
import json

from scrapy.log import ERROR, DEBUG, WARNING
from scrapy.http import Request

from product_ranking.items import SiteProductItem, RelatedProduct, \
                                    Price, BuyerReviews
from product_ranking.spiders import (BaseProductsSpider, cond_set,
                                     FormatterWithDefaults)


def clear_text(l):
    """
    useful for  clearing sel.xpath('.//text()').explode() expressions
    """
    return " ".join(
        [it for it in map(string.strip, l) if it])

is_empty = lambda x, y=None: x[0] if x else y


class OzonProductsSpider(BaseProductsSpider):
    name = 'ozon_products'
    allowed_domains = ["ozon.ru"]
    start_urls = []

    SEARCH_URL = ("http://www.ozon.ru/?context=search&text={search_term}"
                  "&sort={search_sort}")

    RELATED_PRODS_URL = "http://www.ozon.ru/json/shelves.asmx/getitemsitems"

    SEARCH_SORT = {
        'default': '',
        'price': 'price',
        'year': 'year',
        'rate': 'rate',
        'new': 'new',
        'best_sellers': 'bests'
    }

    def __init__(self, search_sort='default', *args, **kwargs):

        super(OzonProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                search_sort=self.SEARCH_SORT[search_sort]
            ),
            *args, **kwargs)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']
        reqs = []

        # Set product title
        cond_set(product, 'title', response.xpath(
            '//h1[@itemprop="name"]/text()'
        ).extract(), string.strip)

        # Set image url
        # TODO: refactor this odd piece of code too
        cond_set(product, 'image_url', response.xpath(
            '//div[@id="PageContent"]'
            '//img[@class="eBigGallery_ImageView"]/@src'
        ).extract())
        cond_set(product, 'image_url', response.xpath(
            '//div[@id="PageContent"]'
            '//*[@itemprop="image"]/@src'
        ).extract())
        if product.get('image_url'):
            product['image_url'] = urlparse.urljoin(
                response.url,
                product.get('image_url'))

        # Set price
        price_main = response.xpath(
            '//div[contains(@class, "bSaleBlock")]/'
            './/span[@class="eOzonPrice_main"]/text()'
        )
        price_submain = response.xpath(
            '//div[contains(@class, "bSaleBlock")]/'
            './/span[@class="eOzonPrice_submain"]/text()'
        )

        if price_submain:
            price_submain = is_empty(
                price_submain.extract()
            )
        else:
            price_submain = '00'

        if price_main:
            price_main = is_empty(
                price_main.extract()
            ).replace('\xa0', '')
            price = '{0}.{1}'.format(
                price_main.strip(),
                price_submain.strip()
            )
            product['price'] = Price(price=price,
                                     priceCurrency='RUB')
        else:
            product['price'] = None

        # Set if out of stock
        is_out_of_stock = is_empty(
            response.xpath(
                '//div[@id="PageContent"]'
                '//div[@class="bSaleColumn"]'
                '//span[@class="eSale_Info mInStock"]/text()'
            ).extract(), ''
        )

        if is_out_of_stock.strip() != u'\u041d\u0430 \u0441\u043a\u043b\u0430\u0434\u0435.':
            product['is_out_of_stock'] = True
        else:
            product['is_out_of_stock'] = False

        # Set description and brand
        desc = response.xpath('//div[@itemprop="description"] |'
                              '//div[@id="detail_description"]')

        if desc:
            product['description'] = is_empty(
                desc.extract()
            ).strip()

        regex = "\/(\d+)"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        # TODO: refactor brand
        # Set brand
        brand = is_empty(
            response.xpath(
                '//a[contains(@href, "/brand/")]/text()'
            ).extract(), ''
        ).strip()

        if brand:
            product['brand'] = brand
        else:
            brand = is_empty(
                response.xpath(
                    '//a[@class="eItemBrand_logo"]/img/@alt |'
                    '//div[contains(@class, "bDetailLogoBlock")]/./'
                    '/a[contains(@href, "/brand/")]/text()'
                ).extract(), ''
            ).strip()
            product['brand'] = brand

        if not product.get('brand', None):
            # <a class="eBreadCrumbs_link " href="/catalog/1168060/?brand=26303248">Lenovo</a>
            _brand = response.xpath(
                '//a[contains(@class, "eBreadCrumbs")][contains(@href, "brand")]/text()'
            ).extract()
            if _brand:
                product['brand'] = _brand[0]

        # Set locale
        product['locale'] = 'ru-RU'

        # Set category
        category_sel = response.xpath('//div[contains(@class, "bBreadCrumbs")]/'
                                      'a[contains(@class, "eBreadCrumbs_link")]/text()')
        if category_sel:
            category = category_sel[0].extract()
            product['category'] = category.strip()

        # Set recommended products
        rel_prod_sel = response.xpath('//ul[@class="eUniversalShelf_Tabs"]'
                                      '/li[contains(@class, "eUniversalShelf_Tab")]'
                                      '/@onclick')

        if rel_prod_sel:
            rel_prod_ids = is_empty(rel_prod_sel.extract())

            rel_prod_ids = is_empty(
                re.findall(
                    r'return\s+(.+)',
                    rel_prod_ids
                )
            )

            if rel_prod_ids:
                rel_prod_ids = rel_prod_ids.replace('\'', '"').replace(' ', '').replace('Ids', 'itemsIds')
                data = json.loads(rel_prod_ids)

                reqs.append(
                    Request(
                        url=self.RELATED_PRODS_URL,
                        method='POST',
                        callback=self.parse_recommended_prods,
                        body=json.dumps(data),
                        headers={'Content-Type': 'application/json'},
                    )
                )

        # Set also bought products
        also_bought = is_empty(
            re.findall(
                r"dataLayer.push\({\"ecommerce\":(.+)}\);",
                response.body_as_unicode()
            )
        )

        if also_bought:
            try:
                prod_ids = []
                data = json.loads(also_bought)

                ids = data['impressions']
                for item in ids:
                    prod_ids.append(item['id'])

                form_data = {
                    "Type": "Items",
                    "itemsIds": prod_ids
                }

                reqs.append(
                    Request(
                        url=self.RELATED_PRODS_URL,
                        method='POST',
                        callback=self.parse_also_bought_prods,
                        body=json.dumps(form_data),
                        headers={'Content-Type': 'application/json'},
                    )
                )
            except (KeyError, ValueError):
                self.log("Impossible to get also bought products info in %r" % response.url, WARNING)

        # Set matketplaces
        marketplace_sel = response.css('#js_merchant_name ::text')

        mktplaces = []
        marketplace = {}

        if marketplace_sel:
            marketplace_name = is_empty(
                marketplace_sel.extract()
            ).strip()
            marketplace['name'] = marketplace_name
            marketplace['seller_type'] = 'seller'
        else:
            marketplace['name'] = self.allowed_domains[0]
            marketplace['seller_type'] = 'site'

        marketplace['price'] = product.get('price', None)
        mktplaces.append(marketplace)
        product['marketplace'] = mktplaces

        # parse buyer reviews
        br_link = None
        try:
            br_link = response.xpath(
                '//a[contains(@href, "/reviews/")]/@href').extract()[0]
        except IndexError:
            product['buyer_reviews'] = BuyerReviews(
                num_of_reviews=0,
                average_rating=0.0,
                rating_by_star={1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            )
            self.log("No buyer reviews found for URL %s" % response.url, WARNING)
        if br_link is not None and isinstance(br_link, basestring):
            if br_link.startswith('/'):
                br_link = urlparse.urljoin(response.url, br_link)
            reqs.append(
                Request(br_link, callback=self.parse_buyer_reviews,
                        meta=response.meta)
            )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        product = meta['product']
        reqs = meta.get('reqs')
        buyer_reviews = dict(num_of_reviews=0, average_rating=0.0,
                             rating_by_star={1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
        for comment_block in response.xpath('//div[contains(@id, "comment_")]'):
            star = comment_block.xpath(
                './/div[contains(@class, "stars")]/@class').extract()
            if not star:
                continue
            star = star[0]
            if 'stars1' in star:
                buyer_reviews['rating_by_star'][1] += 1
                buyer_reviews['num_of_reviews'] += 1
            if 'stars2' in star:
                buyer_reviews['rating_by_star'][2] += 1
                buyer_reviews['num_of_reviews'] += 1
            if 'stars3' in star:
                buyer_reviews['rating_by_star'][3] += 1
                buyer_reviews['num_of_reviews'] += 1
            if 'stars4' in star:
                buyer_reviews['rating_by_star'][4] += 1
                buyer_reviews['num_of_reviews'] += 1
            if 'stars5' in star:
                buyer_reviews['rating_by_star'][5] += 1
                buyer_reviews['num_of_reviews'] += 1
        _avg_list = []
        for key, value in buyer_reviews['rating_by_star'].items():
            for _i in xrange(value):
                _avg_list.append(key)
        if _avg_list:
            buyer_reviews['average_rating'] = round(
                float(sum(_avg_list)) / len(_avg_list),
                1
            )
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews)

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()

        if reqs:
            new_meta["reqs"] = reqs

        return req.replace(meta=new_meta)

    def parse_recommended_prods(self, response):
        meta = response.meta.copy()
        product = meta['product']
        related_products = product.get('related_products', {})
        reqs = meta.get('reqs')
        data = self._handle_related_product(response, 'recommended')
        if data:
            related_products['recommended'] = data
            product['related_products'] = related_products

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def parse_also_bought_prods(self, response):
        meta = response.meta.copy()
        product = meta['product']
        related_products = product.get('related_products', {})
        reqs = meta.get('reqs')
        data = self._handle_related_product(response, 'also_bought')

        if data:
            related_products['also_bought'] = data
            product['related_products'] = related_products

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _handle_related_product(self, response, rel_product_type):
        related_products = []

        try:
            data = json.loads(response.body_as_unicode())
            items = data['d']['Items']

            if items:
                for item in items:
                    title = item['Name']
                    href = '{www}{domain}{url}'.format(
                        www='http://www.',
                        domain=self.allowed_domains[0],
                        url=item['Href']
                    )

                    related_products.append(RelatedProduct(
                        title=title,
                        url=href
                    ))

                return related_products
        except (KeyError, ValueError):
            self.log("Impossible to get {0} products info in {1}".format(
                rel_product_type, response.url
            ), WARNING)
            return None

    def _scrape_total_matches(self, response):
        total = None

        totals = response.xpath('//*[@class="bAlsoSearch"]/span[1]/text()') \
                         .re('\u041d\u0430\u0448\u043b\u0438 ([\d\s]+)')

        if totals:
            total = int(''.join(totals[0].split()))

        elif not response.xpath("//div[@calss='bEmptSearch']"):
            self.log(
                "Failed to find 'total matches' for %s" % response.url,
                WARNING
            )

        return total

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//div[@itemprop="itemListElement"]/a[@itemprop="url"]/@href'
        ).extract()

        if not links:
            self.log("Found no product links.", DEBUG)

        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next = response.css('.SearchPager .Active') \
                       .xpath('following-sibling::a[1]/@href') \
                       .extract()

        if not next:
            link = None
        else:
            link = urlparse.urljoin(response.url, next[0])
        return link
