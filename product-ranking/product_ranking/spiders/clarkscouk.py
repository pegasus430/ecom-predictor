# -*- coding: utf-8 -*-#

import json
import re
import urlparse
import string

from scrapy.http import Request
from scrapy.log import ERROR, INFO, WARNING

from product_ranking.items import SiteProductItem, RelatedProduct, Price, \
    BuyerReviews
from product_ranking.spiders import BaseProductsSpider, \
    cond_set_value

is_empty = lambda x, y=None: x[0] if x else y


class ClarksProductSpider(BaseProductsSpider):

    name = 'clarkscouk_products'
    allowed_domains = ["clarks.co.uk"]

    SEARCH_URL = "http://www.clarks.co.uk/s/{search_term}"

    NEXT_PAGE_URL = 'http://www.clarks.co.uk/ProductListWidget/Ajax/GetFilteredProducts?location={location}'

    items_per_page = 40
    page_num = 1

    ZERO_REVIEWS_VALUE = {
        'num_of_reviews': 0,
        'average_rating': 0.0,
        'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
    }

    def parse_product(self, response):
        reqs = []
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse related products
        related_products = self._parse_related_products(response)
        cond_set_value(product, 'related_products', related_products)

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        # Parse stock status
        out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Parse buyer reviews
        buyer_reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_title(self, response):
        title_sel = response.xpath('//h1[@itemprop="name"]'
                                   '/span[@class="name"]/text()')
        material_sel = response.xpath('//h1[@itemprop="name"]'
                                      '/span[@itemprop="color"]/text()')

        title = is_empty(title_sel.extract(), '').strip()
        material = is_empty(material_sel.extract(), '').strip()

        if title and material:
            return title + ' ' + material
        else:
            return title

    def _parse_category(self, response):
        category_sel = response.xpath('//h1[@itemprop="name"]'
                                      '/span[@class="category"]/text()')
        category = is_empty(category_sel.extract())

        return category

    def _parse_description(self, response):
        description_sel = response.xpath('//div[@id="description"]')
        description = is_empty(description_sel.extract())

        return description

    def _parse_price(self, response):
        price_sel = response.xpath(
            '//meta[@itemprop="price"]'
            '/@content')
        price = is_empty(price_sel.extract())

        price_currency_sel = response.xpath(
            '//meta[@itemprop="priceCurrency"]'
            '/@content'
        )
        price_currency = is_empty(price_currency_sel.extract())

        if price and price_currency:
            price = Price(price=price, priceCurrency=price_currency)
        else:
            price = Price(price=0.00, priceCurrency="GBP")

        return price

    def _parse_image_url(self, response):
        image_url = is_empty(
            response.xpath('//img[@id="main-image"]/@src').extract()
        )

        if image_url:
            image_url = image_url.replace('//', '')

        return image_url

    def _parse_related_products(self, response):
        related_products = {
            'also_liked': [],
            'another_color': []
        }

        # Parse also liked related products
        also_liked_products = response.xpath('//*[@id="up-sells"]/ul/li')
        for item in also_liked_products:
            title = is_empty(
                item.xpath('././/*[@class="title"]/a/text()').extract()
            )
            material = is_empty(
                item.xpath('././/*[@class="inner"]/p/text()').extract()
            )
            url = is_empty(
                item.xpath('././/*[@class="title"]/a/@href').extract()
            )

            if title and url:
                if material:
                    title = title + ' ' + material

                url = 'http://www.{domain}{link}'.format(
                    domain=self.allowed_domains[0],
                    link=url
                )
                prod = RelatedProduct(url=url, title=title)
                related_products['also_liked'].append(prod)

        # Parse color options
        another_color_products = response.xpath('//*[@id="colour-options"]/'
                                                'ul/li')
        for item in another_color_products:
            title = is_empty(
                item.xpath('./a/@title').extract()
            )
            url = is_empty(
                item.xpath('./a/@href').extract()
            )

            if title and url:
                url = 'http://www.{domain}{link}'.format(
                    domain=self.allowed_domains[0],
                    link=url
                )
                prod = RelatedProduct(url=url, title=title)
                related_products['another_color'].append(prod)

        return related_products

    def _parse_variants(self, response):
        variants = []
        vars = response.xpath('//div[@id="size-options"]/ul/li')

        for item in vars:
            size = is_empty(
                item.xpath('./input/@value').extract()
            )

            # Extract fits for sizes
            fits = is_empty(
                item.xpath('./div/@data-price').extract()
            )
            if fits:
                try:
                    fits = json.loads(fits)
                    stock = is_empty(
                        item.xpath('./div/@data-outofstock').extract()
                    )
                    if stock:
                        stock = stock.replace('#alt-fitid-', '').split(',')

                    for fit, price in fits.iteritems():
                        single_variant = {}
                        properties = {}
                        properties['size'] = size
                        properties['fit'] = fit

                        if stock and fit in stock:
                            single_variant['out_of_stock'] = True
                        else:
                            single_variant['out_of_stock'] = False

                        single_variant['price'] = price.replace(u'£', '')
                        single_variant['properties'] = properties

                        variants.append(single_variant)
                except Exception as exc:
                    self.log(
                        'Unable to parse fits for variants on {url}: {exc}'.format(
                            url=response.url, exc=exc
                        ), WARNING
                    )

        return variants

    def _parse_stock_status(self, response):
        stock_status = is_empty(
            response.xpath('//input[@id="add-to-basket-button-static"]'
                           '/@alt').extract()
        )

        if stock_status and 'Out of stock' in stock_status:
            stock_status = True
        else:
            stock_status = False

        return stock_status

    def _parse_buyer_reviews(self, response):
        num_of_reviews = is_empty(
            response.xpath('//meta[@itemprop="reviewCount"]/@content').extract()
        )

        if num_of_reviews:
            # Get average rating
            average_rating = is_empty(
                response.xpath('//meta[@itemprop="ratingValue"]/@content').extract(),
                0.0
            )

            # Count rating by star
            rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            stars = response.xpath('//*[@id="reviews"]/./'
                                   '/li/.//meta[@itemprop="ratingValue"]'
                                   '/@content').extract()

            for star in stars:
                rating_by_star[star] += 1

            buyer_reviews = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(average_rating),
                'rating_by_star': rating_by_star
            }
        else:
            buyer_reviews = self.ZERO_REVIEWS_VALUE

        return BuyerReviews(**buyer_reviews)

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        requests = super(ClarksProductSpider, self).start_requests()

        for req in requests:
            new_url = req.url.replace('+', '%20')
            req = req.replace(url=new_url)
            yield req

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        total_matches = is_empty(
            response.xpath('//div[@id="product-list-paging-top"]/./'
                           '/span[@class="page-size-container"]/text()').extract()
        )

        if total_matches:
            try:
                total_matches = re.findall(
                    r'Found (\d+) styles',
                    total_matches
                )
                return int(
                    is_empty(total_matches, '0')
                )
            except (KeyError, ValueError) as exc:
                total_matches = None
                self.log(
                    "Failed to extract total matches from {url}: {exc}".format(
                        response.url, exc
                    ), WARNING
                )
        else:
            total_matches = 0

        return total_matches

    def _scrape_results_per_page(self, response):
        """
        Number of results on page
        """
        return self.items_per_page

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """

        items = response.xpath(
            '//ul[@id="prod-list"]/li[contains(@class, "product-list-item")]'
        )

        if items:
            for item in items:
                link = is_empty(
                    item.xpath('./span[@class="product-name-header"]/'
                               'a/@href').extract()
                )
                res_item = SiteProductItem()
                yield link, res_item
        else:
            links = re.findall(
                r'<a href=\\"(\/p\/\d+)\\"',
                response.body_as_unicode().replace('\u003c', '<').replace('\u003e', '>')
            )
            if links:
                links = list(set(links))
                for link in links:
                    res_item = SiteProductItem()
                    yield link, res_item
            else:
                self.log("Found no product links.".format(response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        # if the page no products to stop the spider
        items = response.xpath(
            '//ul[@id="prod-list"]/li[contains(@class, "product-list-item")]'
        )
        if not items:
            links = re.findall(
                r'<a href=\\"(\/p\/\d+)\\"',
                response.body_as_unicode().replace('\u003c', '<').replace('\u003e', '>')
            )
            if not links:
                return

        meta = response.meta.copy()

        # We need initial link always to be a referer:
        #   for ex. http://www.clarks.co.uk/s/smart
        # But after sending the first Req, self.NEXT_PAGE_URL
        # becomes a referer. So this is to prevent:
        response_url = meta.get(
            'response_url'
        )
        if not response_url:
            response.meta['response_url'] = response.url
            response_url = response.url

        if '/c/' in response_url:
            location = 'Category'
        else:
            location = 'Search'
        parsed_url = urlparse.urlparse(response_url)
        self.page_num += 1
        query_criteria = is_empty(
            re.findall(
                r'\/s?c?\/(.+)',
                parsed_url.path
            )
        )
        data = {
            "QueryCriteria": query_criteria,
            "ImageSize": "LargeListerThumbnail",
            "ViewName": "3Columns",
            "Location": location,
            "FilteredProductQueries": [
                {
                    "Behaviour": "kvp",
                     "FhName": "fh_view_size",
                     "DisplayName": "pagesize",
                     "DataSplit": "-or-",
                     "Priority": "secondary",
                     "Items": [str(self.items_per_page)]
                },
                {
                    "Behaviour": "kvp",
                    "DataSplit": "-or-",
                    "DisplayName": "page",
                    "FhName": "fh_start_index",
                    "Items": [str(self.page_num)]
                }
            ],
            "PathName": parsed_url.path,
            "Scroll": True,
            "DeviceType": "Desktop"
        }

        return Request(
            url=self.NEXT_PAGE_URL.format(location=location),
            method='POST',
            meta=response.meta.copy(),
            body=json.dumps(data),
            headers={
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json'
            }
        )
