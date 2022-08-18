from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback

from scrapy.http import Request
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value,\
    FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from spiders_shared_code.joann_variants import JoannVariants
from product_ranking.items import BuyerReviews
from scrapy.log import WARNING


class JoannProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'joann_products'
    allowed_domains = ["www.joann.com"]

    SEARCH_URL = "http://www.joann.com/search?q={search_term}"

    REVIEW_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=e7zwsgz8csw4fd3opkunhjl78" \
                 "&apiversion=5.5" \
                 "&displaycode=12608-en_us" \
                 "&resource.q0=products" \
                 "&&filter.q0=id:eq:{prod_id}" \
                 "&stats.q0=reviews"

    STOCK_URL = 'http://www.joann.com/on/demandware.store/Sites-JoAnn-Site/default' \
                '/ProductCont-QuantityControls?pid={sku}'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi()

        super(JoannProductsSpider, self).__init__(*args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product_img = response.xpath("//div[@class='content-asset']//p//img/@data-yo-src").extract()
        if product_img and 'error404' in product_img[0]:
            product['not_found'] = True
            return product

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        self._parse_price(response)

        product['locale'] = "en-US"

        description = self._parse_description(response)
        product['description'] = description

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._department(response)
        product['department'] = department

        reqs = []
        self.jv = JoannVariants()
        self.jv.setupSC(response)

        sku_list = response.xpath("//div[contains(@class, 'product-variant-tile')]/@data-pid").extract()
        sku_len = len(sku_list)
        response.meta['sku_len'] = sku_len
        for sku in sku_list:
            url = self.STOCK_URL.format(sku=sku)
            req = Request(url=url,
                          meta=response.meta,
                          callback=self.get_stock)
            reqs.append(req)

        product_id = self._parse_product_id(response)
        cond_set_value(product, 'reseller_id', product_id)

        if product_id:
            reqs.append(
                Request(
                    self.REVIEW_URL.format(prod_id=product_id),
                    callback=self._parse_buyer_reviews_from_filters,
                    meta={"product": product},
                    dont_filter=True
                )
            )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_title(self, response):
        title = response.xpath('//span[@itemprop="name"]/text()').extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        if title:
            brand = guess_brand_from_first_words(title)
            return brand if brand else None

    def _parse_product_id(self, response):
        product_id = response.xpath("//meta[@itemprop='productID']/@content").extract()
        return product_id[0] if product_id else None

    def _parse_categories(self, response):
        categories = response.xpath('//li[@class="breadcrumb"]//a/text()').extract()
        categories = [self._clean_text(category) for category in categories if categories]
        return categories[1:] if categories else None

    def _department(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_description(self, response):
        shot_des = ''.join(response.xpath('//div[@id="short-description-content"]/text() | '
                                          '//div[@id="short-description-content"]//p/text()').extract())
        long_desc = ''.join(response.xpath('//div[@id="short-description-content"]//ul').extract())
        return self._clean_text(''.join([shot_des, long_desc]))

    def _parse_image_url(self, response):
        image = response.xpath("//div[@class='main']//a//img/@src | "
                               "//img[@class='productthumbnail']/@data-yo-src").extract()
        if image:
            image = image[0].replace('sw=70&sh=70&', '').replace(';', '&').replace('amp', '')

        return image

    def _parse_price(self, response):
        product = response.meta['product']
        price = response.xpath('//span[contains(@class, "on-sale")]/text() | '
                               '//span[contains(@class, "standard-price")]'
                               '/text()').re(FLOATING_POINT_RGEX)
        if price:
            cond_set_value(product, 'price',
                           Price(price=price[0].replace(',', ''),
                                 priceCurrency='USD'))

    def _parse_out_of_stock(self, response):
        oos = response.xpath('//div[contains(@class, "in-stock")]/text()').extract()
        return self._clean_text(''.join(oos)).lower() == 'out of stock'

    def get_stock(self, response):
        meta = response.meta.copy()
        sku_len = meta.get('sku_len')
        product = meta.get('product')
        reqs = meta.get('reqs')
        stock_list = meta.get('stocks', [])

        in_stock = True
        stock_option = response.xpath("//input[contains(@class, 'fancy-radio-button')]").extract()[0]
        if 'disabled' in stock_option:
            in_stock = False

        stock_list.append(in_stock)

        if len(stock_list) == sku_len:
            product['variants'] = self.jv._variants(stock_list)

        response.meta['stocks'] = stock_list
        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _scrape_total_matches(self, response):
        totals = None
        total_match = response.xpath("//div[@id='pageBy']//div[contains(@class, 'results-hits')]/text()").extract()
        if total_match:
            totals = re.search('of ([\d,]+) Results', self._clean_text(total_match[0]))
        return int(totals.group(1).replace(',', '')) if totals else 0

    def _scrape_product_links(self, response):
        product_links = response.xpath("//div[@class='product-name']//h2//a/@href").extract()

        for item_url in product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_link = response.xpath("//li[contains(@class, 'next')]//a/@href").extract()
        if next_page_link:
            return next_page_link[0]

    def _parse_buyer_reviews_from_filters(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs')

        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            review_json = json.loads(response.body)
            if 'FilteredReviewStatistics' in review_json["BatchedResults"]["q0"]["Results"][0]:
                review_statistics = review_json["BatchedResults"]["q0"]["Results"][0]['FilteredReviewStatistics']
            else:
                review_statistics = review_json["BatchedResults"]["q0"]["Results"][0]['ReviewStatistics']

            if review_statistics.get("RatingDistribution"):
                for item in review_statistics['RatingDistribution']:
                    key = str(item['RatingValue'])
                    buyer_review_values["rating_by_star"][key] = item['Count']

            if review_statistics.get("TotalReviewCount"):
                buyer_review_values["num_of_reviews"] = review_statistics["TotalReviewCount"]

            if review_statistics.get("AverageOverallRating"):
                buyer_review_values["average_rating"] = format(review_statistics["AverageOverallRating"], '.1f')
        except Exception as e:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
        finally:
            buyer_reviews = BuyerReviews(**buyer_review_values)
            product['buyer_reviews'] = buyer_reviews

            if reqs:
                response.meta['product'] = product
                return self.send_next_request(reqs, response)

            return product

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        new_meta = response.meta.copy()

        if reqs:
            new_meta["reqs"] = reqs

        return req.replace(meta=new_meta)

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
