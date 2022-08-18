# -*- coding: utf-8 -*-#

import json
import string
import requests

from scrapy.http import Request
from scrapy.log import INFO

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.guess_brand import guess_brand_from_first_words

is_empty = lambda x, y=None: x[0] if x else y


class MicrosoftStoreProductSpider(BaseProductsSpider):

    name = 'microsoftstore_products'
    allowed_domains = ["www.microsoftstore.com"]

    SEARCH_URL = "http://www.microsoftstore.com/store?keywords={search_term}" \
                 "&SiteID=msusa&Locale=en_US" \
                 "&Action=DisplayProductSearchResultsPage&" \
                 "result=&sortby=score%20descending&filters="

    PAGINATE_URL = 'http://www.microsoftstore.com/store/msusa/en_US/filterSearch/' \
                   'categoryID.{category_id}/startIndex.{start_index}/size.{size}/sort.score%' \
                   '20descending?keywords={search_term}&' \
                   'Env=BASE&callingPage=productSearchResultPage'

    # Simplified bazaarapi url, returns both full review stats and filtered stats
    # https://developer.bazaarvoice.com/docs/read/conversations/reviews/display/5_4
    REVIEWS_URL = 'http://api.bazaarvoice.com/data/reviews.json?apiversion=5.5&passkey=291coa9o5ghbv573x7ercim80&' \
                  'Filter=ProductId:eq:{product_id}&Include=Products&Stats=Reviews&filter=contentlocale:eq:en_US&' \
                  'filteredstats=reviews'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        self.start_index = 0

        super(MicrosoftStoreProductSpider, self).__init__(*args, **kwargs)

    def parse_product(self, response):
        reqs = []
        meta = response.meta
        product = meta['product']

        product_id = is_empty(response.xpath(
            '//script[contains(text(), "productId")]/text()').re(
            r"productId: '(\d+)'"))
        meta['product_id'] = product_id

        cond_set_value(product, "reseller_id", product_id)

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self.parse_title(response)
        cond_set_value(product, 'title', title)

        # Parse brand
        brand = self.parse_brand(title)
        cond_set_value(product, 'brand', brand)

        # Parse price
        price = self.parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self.parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self.parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse sku
        sku = self.parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse variants
        variants = self.parse_variant(response)
        cond_set_value(product, 'variants', variants)

        # Parse buyer reviews
        reqs.append(
            Request(
                url=self.REVIEWS_URL.format(product_id=product_id),
                dont_filter=True,
                callback=self.parse_buyer_reviews,
                meta=meta
            )
        )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def parse_sku(self, response):
        sku = is_empty(response.xpath('//script[contains(text(), "sku")]').re(r"sku : \[(.*)\]"))
        return sku

    def parse_buyer_reviews(self, response):
        meta = response.meta
        product = meta['product']
        product_id = meta['product_id']
        data = response.body

        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        if data:
            data = json.loads(data)

            if data:
                try:
                    # Need to use FilteredReviewStatistics as on website.
                    # shows only reviews that match current locale
                    js = data['Includes']['Products'][product_id]['FilteredReviewStatistics']
                    total = js['TotalReviewCount']
                    average = js['AverageOverallRating']
                    stars = js['RatingDistribution']

                    for star in stars:
                       rating_by_star[str(star['RatingValue'])] = star['Count']

                    if total and average and stars:
                        buyer_reviews = {
                            'num_of_reviews': int(total),
                            'average_rating': round(average, 1),
                            'rating_by_star': rating_by_star
                        }

                    product['buyer_reviews'] = BuyerReviews(**buyer_reviews)

                except:
                    product['buyer_reviews'] = ZERO_REVIEWS_VALUE



        return product


    def parse_title(self, response):
        title = is_empty(response.xpath(
            '//h1[@itemprop="name"]/text()').extract())
        if title:
            return title

    def parse_brand(self, title):
        brand = guess_brand_from_first_words(title)
        # brand = is_empty(response.xpath(
        #     '//div[@class="shell-header-brand"]/a/@title').extract())
        return brand

    def parse_price(self, response):
        price = is_empty(response.xpath(
            '//p[@class="current-price"]/span/text()').re(r'([\d\.\,]+)'))

        currency = is_empty(response.xpath(
            '//meta[@itemprop="priceCurrency"]/@content').extract())
        if not price:
            price = is_empty(response.xpath(
                '//span[@itemprop="price"]/text()').re(r'([\d\.\,]+)'))
        if not price:
            price = is_empty(response.xpath(
                                   '//span[@itemprop="price"]/text()').re(r'Starting from .([\d\.\,]+)'))

        if price and currency:
            price = Price(price=price, priceCurrency=currency)
        else:
            price = Price(price=0.00, priceCurrency="USD")
        return price

    def parse_image_url(self, response):
        image_url = is_empty(response.xpath(
            '//div[@class="image-container"]/@data-src').extract())
        if not image_url:
            image_url = is_empty(response.xpath(
                './/*[@class="product-hero base-hero"]/li[1]/img/@src').extract())
        if not image_url:
            image_url = is_empty(response.xpath(
                './/*[@data-class="poster"]/@data-src').extract())
        if image_url:
            return image_url

    def parse_description(self,response):
        description = is_empty(response.xpath(
            '//div[@class="short-desc"]').extract())

        return description

    def parse_variant(self, response):
        variants = []
        price_blocks = response.xpath(
            '//div[contains(@class, "price-block")]'
            '//p[contains(@class,"current-price")]')
        prices = []
        for p_block in price_blocks:
            price = p_block.xpath('.//text()').extract()
            price = [x for x in price if len(x.strip()) > 0]
            price = "".join(price)
            prices.append(price)

        titles = response.xpath(
            '//div[contains(@class,"variation-container")]//li//a/@title'
        ).extract()
        if len(titles) < 1:
            titles = response.xpath('//div[contains(@class,"variation-container")]'
                                    '//li//a/@data-variation-title').extract()

        urls = response.xpath(
            '//div[contains(@class,"btnSubmitSpinContainer")]//'
            'a[contains(@class,"buyBtn_AddtoCart")]/@href').extract()

        selected = response.xpath(
            '//div[contains(@class,"variation-container")]//li').extract()
        data_pids = response.xpath(
            '//div[contains(@class,"variation-container")]//li/@data-pid'
        ).extract()
        if len(selected) > 0 and len(data_pids) == 0:
            data_pids = response.xpath(
                '//div[contains(@class,"variation-container")]//li/a/@var-pid'
            ).extract()

        idx = 0
        for price in prices:
            variant = {}
            if idx >= len(titles) or idx >= len(urls):
                break
            variant["price"] = price
            variant["title"] = titles[idx]
            variant["url"] = urls[idx]
            if "class='active'" in selected[idx] \
                    or 'class="active"' in selected[idx] \
                    or 'class="selected"' in selected[idx] \
                    or "class='selected'" in selected[idx]:
                variant["selected"] = True
            else:
                variant["selected"] = False

            if "https://www.microsoftstore.com/store/msusa/en_US/pdp/Lenovo-Yoga-900-Signature-Edition-2-in-1-PC/productID.334955000" == response._url:
                pass

            in_stock_url = "https://www.microsoftstore.com/store?Action=DisplayPage&" \
                           "Locale=en_US&SiteID=msusa&id=ProductInventoryStatusXmlPage&" \
                           "productID=%s" % data_pids[idx]
            r = requests.get(in_stock_url)
            if "PRODUCT_INVENTORY_OUT_OF_STOCK" in r.text:
                variant["in_stock"] = False
            else:
                variant["in_stock"] = True

            variants.append(variant)
            idx += 1

        return variants

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        total_matches = is_empty(
            response.xpath(
                '//span[@class="product-count"]/text()').re(r'\d+'))
        if total_matches:
            total_matches = total_matches.replace(',', '')
            return int(total_matches)
        else:
            return 0

    def _scrape_results_per_page(self, response):
        """
        Number of results on page
        """
        links = response.xpath(
            '//div[@class="product-row"]/a/@href'
        ).extract()

        per_page = len(links)
        return per_page

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        links = response.xpath(
            '//div[@class="product-row"]/a/@href'
        ).extract()

        if links:
            for link in links:
                yield 'http://www.microsoftstore.com/' + link, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        total = self._scrape_total_matches(response)
        size = self._scrape_results_per_page(response)
        self.start_index += size
        if self.start_index != total:
            category_id = is_empty(
                response.xpath(
                    "//div[@id='productListContainer']/@category-id").extract())
            return Request(
                self.PAGINATE_URL.format(
                    search_term=response.meta['search_term'],
                    size=size,
                    start_index=self.start_index,
                    category_id=category_id),
                    meta=response.meta
                )
