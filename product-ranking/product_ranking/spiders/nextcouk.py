# -*- coding: utf-8 -*-#

import json
import re
import hjson
import urlparse

from scrapy.http import Request
from scrapy.log import ERROR, INFO, WARNING

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value)
from product_ranking.utils import is_empty


def product_id_format(product_id, product_target=None):
    """
    Formats product id 123456 to 123-456-X56
    """
    result = '{0}-{1}'.format(
        product_id[:3],
        product_id[3:]
    )
    if product_target:
        result = '{0}-{1}'.format(
            result,
            product_target
        )
    return result

class NextCoUkProductSpider(BaseProductsSpider):

    name = 'nextcouk_products'
    allowed_domains = ["www.next.co.uk",
                       "next.ugc.bazaarvoice.com"]

    SEARCH_URL = "http://www.next.co.uk/search?w={search_term}&isort={search_sort}"

    NEXT_PAGE_URL = "http://www.next.co.uk/search?w=jeans&isort=score&srt={start_pos}"

    REVIEWS_URL = "http://api.bazaarvoice.com/data/products.json?apiversion=5.4&" \
                  "passkey=caQJkdpouD5IPtdhUhW1NAKfApRb7uFwzaeJ9wEkUObJE&" \
                  "Filter=Id:{product_id}&stats=reviews&callback=bvGetReviewSummaries"

    _SORT_MODES = {
        "RELEVANT": "score",
        "POPULAR": "popular",
        "ALPHABETICAL": "title",
        "LOW_HIGH": "price",
        "HIGH_LOW": "price%20rev",
        "RATING": "rating",
    }

    def __init__(self, search_sort='POPULAR', *args, **kwargs):
        self.start_pos = 0
        super(NextCoUkProductSpider, self).__init__(
            site_name=self.allowed_domains[0],
            url_formatter=FormatterWithDefaults(
                search_sort=self._SORT_MODES[search_sort]
            ),
            *args, **kwargs)

    def parse_product(self, response):
        reqs = []
        product = response.meta['product']

        product_ids = is_empty(
            re.findall(r'#(\d+)(\D\w+)', product['url']),
            None
        )

        if not product_ids:
            product_ids = response.xpath('//input[@id="idList"]/'
                                         '@value').extract()[0]
            product_ids = product_ids.split(',')
            product_id = product_ids[0]
        else:
            product_id = product_ids[0]


        product['locale'] = 'en_GB'

        regex = "\/(g[\da-z]+)"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        # Set category
        self._parse_category(response)

        # Get StyleID to choose current item
        style_id_data = re.findall(
            r'\s*(StyleID|ItemNumber)\s*:\s*"?([^\n",]+)"?',
            response.body_as_unicode()
        )

        tree = {}
        last_id = None
        for (key, val) in style_id_data:
            if key == 'StyleID':
                last_id = val
            elif key == 'ItemNumber':
                tree[val] = last_id

        try:
            style_id = tree[product_id_format(product_id)]
        except (KeyError, ValueError) as exc:
            self.log('Error parsing style_id:{0}'.format(exc), ERROR)
            return product

        variants = self._parse_variants(response, style_id)
        if len(variants) > 1:
            sku = variants[0].get('properties', {}).get('sku')
            cond_set_value(product, 'sku', sku)

            is_out_of_stock = not any([var.get('in_stock') for var in variants])
            cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

            if len(variants) == 1:
                variants = None

        cond_set_value(product, 'variants', variants)

        # Format product id to get proper section from html body
        item = response.xpath(
            '//article[@id="Style{id}"]'.format(
                id=style_id
            )
        )

        if item:
            #  Set title
            self._parse_title(response, item)

            # Set description
            self._parse_description(response, item)

            # Get price
            self._parse_price(response, item)

            # Get image url
            self._parse_image(response, item)

        else:
            self.log(
                "Failed to extract product info from {}".format(response.url), ERROR
            )

        # Get buyer reviews
        prod_info_js = self.REVIEWS_URL.format(product_id=product_id)
        reviews_request = Request(
            url=prod_info_js,
            callback=self._parse_prod_info_js,
            dont_filter=True,
            meta={'product': product}
        )
        reqs.append(reviews_request)

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_category(self, response):
        """
        Parses list of categories for product
        """
        product = response.meta['product']

        try:
            category = response.xpath(
                '//div[@class="BreadcrumbsHolder"]/./'
                '/li[@class="Breadcrumb"][not(contains(@class, "bcHome"))]'
                '/a/text()'
            ).extract()[:-1]
            cond_set_value(product, 'category', category, conv=list)
        except ValueError as exc:
            self.log(
                "Failed to get category from {}: {}".format(
                    response.url, exc
                ), WARNING
            )

    def _parse_title(self, response, item):
        product = response.meta['product']

        title = item.xpath('.//div[@class="Title"]//h1/text() |'
                           './/div[@class="Title"]//h2/text()')
        title = is_empty(
            title.extract(), ''
        )

        if title:
            product['title'] = title.strip()

    def _parse_description(self, response, item):
        product = response.meta['product']

        description = is_empty(
            item.css('.StyleContent').extract(), ''
        )

        if description:
            product['description'] = description.strip().replace('\r', '').replace('\n', '').replace('\t', '')

    def _parse_variants(self, response, style_id):
        try:
            js = re.search(r'shotData = ({.*})', response.body_as_unicode())
            js = hjson.loads(js.group(1), object_pairs_hook=dict).get('Styles')
        except:
            return None

        variants = []

        # get variants data for current product
        data = []
        for product in js:
            if str(product.get('StyleID')) == style_id:
                data = product.get('Fits', [])
                break

        for variant_data in data:
            # iterate over fits
            fit = variant_data.get('Name').strip()

            for item in variant_data.get('Items', []):
                # iterate over colors
                color = item.get('Colour')
                item_number = item.get('ItemNumber')

                for option in item.get('Options', []):
                    # iterate over sizes
                    variant = {
                        'properties': {
                            'sku': item_number,
                        },
                        'price': option.get('Price'),
                        'in_stock': option.get('StockStatus') == 'InStock',
                    }
                    size = option.get('Name')
                    if fit:
                        variant['properties']['fit'] = fit
                    if color:
                        variant['properties']['color'] = color
                    if size:
                        variant['properties']['size'] = size
                    variants.append(variant)

        return variants

    def _parse_price(self, response, item):
        product = response.meta['product']

        price_sel = item.css('.Price')

        if price_sel:
            price = is_empty(
                price_sel.extract()
            ).strip()
            price = is_empty(
                re.findall(r'(\d+)', price)
            )
            product['price'] = Price(
                priceCurrency="GBP",
                price=price
            )
        else:
            product['price'] = None

    def _parse_image(self, response, item):
        product = response.meta['product']

        image_sel = item.xpath('.//div[@class="StyleThumb"]//img/@src')

        if image_sel:
            image = is_empty(image_sel.extract())
            product['image_url'] = image.replace('Thumb', 'Zoom')

    def _parse_prod_info_js(self, response):
        meta = response.meta.copy()
        reqs = meta.get("reqs")
        product = meta['product']
        data = response.body_as_unicode()
        data = is_empty(
            re.findall(
                r'bvGetReviewSummaries\((.+)\)',
                data
            )
        )

        if data:
            data = json.loads(data)
            results = is_empty(
                data.get('Results', [])
            )

            if results:
                # Buyer reviews
                buyer_reviews = self._parse_buyer_reviews(results, response)
                product['buyer_reviews'] = BuyerReviews(**buyer_reviews)

                # Get brand
                self._parse_brand(response, results)

                # Get department
                self._parse_department(response, results)

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_brand(self, response, data):
        product = response.meta['product']

        try:
            brand = data['Brand']['Name']
            product['brand'] = brand
        except (KeyError, ValueError) as exc:
            self.log(
                "Failed to get brand from {}: {}".format(
                    response.url, exc
                ), WARNING
            )

    def _parse_department(self, response, data):
        product = response.meta['product']

        try:
            departments = is_empty(
                data['Attributes']['department']['Values']
            )
            department = departments['Value']
            product['department'] = department
        except (KeyError, ValueError) as exc:
            self.log(
                "Failed to get department from {}: {}".format(
                    response.url, exc
                ), WARNING
            )

    def _parse_buyer_reviews(self, data, response):
        buyer_review = dict(
            num_of_reviews=0,
            average_rating=0.0,
            rating_by_star={'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        )

        try:
            buyer_reviews_data = data['ReviewStatistics']
            buyer_review['num_of_reviews'] = buyer_reviews_data['TotalReviewCount']

            if buyer_review['num_of_reviews']:
                buyer_review['average_rating'] = float(
                    round(buyer_reviews_data['AverageOverallRating'], 1)
                )

                ratings = buyer_reviews_data['RatingDistribution']
                for rate in ratings:
                    star = str(rate['RatingValue'])
                    buyer_review['rating_by_star'][star] = rate['Count']
        except (KeyError, ValueError) as exc:
            self.log(
                "Failed to get buyer reviews from {}: {}".format(
                    response.url, exc
                ), WARNING
            )

        return buyer_review

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        if reqs:
            req.meta["reqs"] = reqs

        return req

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """

        total_matches = response.css("#filters .ResultCount .Count ::text")
        try:
            matches_re = re.compile('(\d+) PRODUCTS')
            total_matches = re.findall(
                matches_re,
                is_empty(
                    total_matches.extract()
                )
            )
            return int(
                is_empty(total_matches, '0')
            )
        except (KeyError, ValueError) as exc:
            total_matches = None
            self.log(
                "Failed to extract total matches from {}: {}".format(
                    response.url, exc
                ), ERROR
            )

        return total_matches

    def _scrape_results_per_page(self, response):
        """
        Number of results on page
        """

        num = len(
            response.css('[data-pagenumber="1"] article.Item')
        )
        self.items_per_page = num

        if not num:
            num = None
            self.items_per_page = 0
            self.log(
                "Failed to extract results per page from {}".format(response.url), ERROR
            )

        return num

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """

        items = response.css(
            'div.Page article.Item'
        )

        if items:
            for item in items:
                link = is_empty(
                    item.css('.Details .Title a ::attr(href)').extract()
                )
                res_item = SiteProductItem()

                link = urlparse.urljoin(response.url, link)
                yield Request(
                    link,
                    dont_filter=True,
                    meta={'product': res_item},
                    callback=self.parse_product,
                ), res_item
        else:
            self.log("Found no product links in {}".format(response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        url = self.NEXT_PAGE_URL.format(start_pos=self.start_pos)
        self.start_pos += self.items_per_page
        return url
