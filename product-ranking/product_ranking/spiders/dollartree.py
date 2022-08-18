import re
import string
import json
import urllib
from lxml import html
import traceback

from scrapy.http import Request
from scrapy.conf import settings

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults


class DollartreeProductsSpider(BaseProductsSpider):
    name = 'dollartree_products'
    allowed_domains = ['dollartree.com']
    handle_httpstatus_list = [404]

    SEARCH_URL = 'https://www.dollartree.com/search/go?p=Q&lbc=dollartree&ts=ajax&w={search_term}&method=and&isort=score&view=grid&srt={current_page}'

    REVIEWS_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                  "passkey=ca4585394e115511e6b1d60ea0ad7a5351&" \
                  "apiversion=5.5&" \
                  "displaycode=16649-en_us&" \
                  "resource.q0=products&" \
                  "filter.q0=id%3Aeq%3A{sku}&" \
                  "stats.q0=reviews"

    HEADER = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.82 Safari/537.36'
    }

    def __init__(self, *args, **kwargs):
        self.total_matches = None
        super(DollartreeProductsSpider, self).__init__(site_name=self.allowed_domains[0],
                                                       *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['USE_PROXIES'] = True

    def start_requests(self):
        if not self.searchterms:
            for request in super(DollartreeProductsSpider, self).start_requests():
                yield request

        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                    current_page=0,
                ),
                headers=self.HEADER,
                meta={'search_term': st, 'remaining': self.quantity},
            )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        if response.status in self.handle_httpstatus_list:
            cond_set_value(product, 'no_longer_available', True)

            return product
        else:
            # Parse title
            title = self._parse_title(response)
            cond_set_value(product, 'title', title, conv=string.strip)

            # Parse brand
            brand = self._parse_brand(response)
            cond_set_value(product, 'brand', brand, conv=string.strip)

            # Parse department
            department = self._parse_department(response)
            cond_set_value(product, 'department', department, conv=string.strip)

            # Parse description
            description = self._parse_description(response)
            cond_set_value(product, 'description', description)

            # Parse price
            price = self._parse_price(response)
            cond_set_value(product, 'price', price)

            # Parse sku
            sku = self._parse_sku(response)
            cond_set_value(product, 'sku', sku, conv=string.strip)

            # Parse image url
            image_url = self._parse_image_url(response)
            cond_set_value(product, 'image_url', image_url)

            # Parse stock status
            out_of_stock = self._parse_is_out_of_stock(response)
            cond_set_value(product, 'is_out_of_stock', out_of_stock)

            if sku:
                return Request(
                    url=self.REVIEWS_URL.format(sku=str(sku).strip()),
                    callback=self.parse_buyer_reviews,
                    meta={
                        'product': product,
                        'product_id': sku,
                    },
                    dont_filter=True
                )

            return product

    def parse_buyer_reviews(self, response):
        product = response.meta['product']

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        try:
            json_data = json.loads(response.body_as_unicode())
            product_reviews = json_data["BatchedResults"].get("q0").get("Results")[0].get('ReviewStatistics', {})
            if product_reviews:
                rating_by_stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

                for rating_distribution in product_reviews.get('RatingDistribution', []):
                    rating_by_stars[str(rating_distribution['RatingValue'])] = rating_distribution['Count']

                average_rating = product_reviews.get('AverageOverallRating', 0)
                buyer_reviews = {'num_of_reviews': product_reviews.get('TotalReviewCount', 0),
                                 'average_rating': round(float(average_rating), 1) if average_rating else None,
                                 'rating_by_star': rating_by_stars
                                 }
                product['buyer_reviews'] = buyer_reviews

        except Exception as e:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE
        finally:
            return product

    def _scrape_total_matches(self, response):
        if self.total_matches:
            return self.total_matches
        total = response.xpath('//span[@class="sli_count_selected"]').extract()
        total = re.search('(\d+)', total[0], re.DOTALL)
        try:
            self.total_matches = int(total.group(1))
            return self.total_matches
        except:
            self.log('Found no product next link: {}'.format(traceback.format_exc()))

    def _scrape_product_links(self, response):
        selector = html.fromstring('<div>' + response.body + '</div>')
        links = selector.xpath('//a[@data-tb-sid="st_image-wrapper"]/@href')
        for link in links:
            item = SiteProductItem()
            yield link, item

    def _scrape_next_results_page_link(self, response):
        st = response.meta['search_term']
        current_page = response.meta.get('current_page')

        if not current_page:
            current_page = 0
        if current_page * 15 > self.total_matches:
            return
        next_page = current_page + 1
        url = self.SEARCH_URL.format(current_page=next_page * 15, search_term=st)
        return Request(
            url,
            meta={
                'search_term': st,
                'remaining': self.quantity,
                'current_page': next_page}, )

    def _parse_brand(self, response):
        brand = None
        details = response.xpath('//*[@id="productDetails"]/div').extract()
        if details:
            re_brand_result = re.search(u'(?<=Brand</strong>:\u00A0)(.*)(?=<br>)', details[0])
            if re_brand_result:
                brand = re_brand_result.group()
        return brand

    def _parse_title(self, response):
        title = response.xpath(
            '//input[@id="productName"]/@value'
        ).extract()
        return title[0].strip() if title else None

    @staticmethod
    def _parse_department(response):
        departments = response.xpath(
            '//div[@id="breadcrumb"]'
            '/ul[@class="horiz"]'
            '/li/a/text()'
        ).extract()
        if departments:
            return departments[-1]

    def _parse_description(self, response):
        description_list = response.xpath(
            '//div[@class="productDesc"]'
            '/text()'
        ).extract()

        description = ''
        for desc in description_list:
            description += self._clean_text(desc)
        return description if description else None

    def _parse_price(self, response):
        price = response.xpath(
            '//span[@class="unitCaseNum"]'
            '/text()'
        ).extract()
        if not price:
            return None
        try:
            price = re.search('(.*) Per', price[0])
            return Price(price=float(price.group(1).replace('$', '')), priceCurrency='USD')
        except:
            self.log("Error while parsing price: {}".format(traceback.format_exc()))

    def _parse_sku(self, response):
        sku = response.xpath('//div[@class="skuContainer"]'
                             '/p/strong/text()').extract()
        try:
            sku = re.search('(\d+)', sku[0], re.DOTALL)
            return sku.group(1)
        except:
            self.log("Error while parsing sku: {}".format(traceback.format_exc()))

    @staticmethod
    def _parse_image_url(response):
        img_url = response.xpath(
            '//img[@class="img_xlarge"]'
            '/@src'
        ).extract()
        return img_url[0] if img_url else None

    def _parse_is_out_of_stock(self, response):
        return not bool(response.xpath('//div[@class="deliveryOptionsContainer"]'))

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()
