import re
import json
import urllib
from urlparse import urljoin

from scrapy import Request
from scrapy.log import WARNING

from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value, \
    FormatterWithDefaults, FLOATING_POINT_RGEX


class IcelandcoukProductsSpider(BaseProductsSpider):
    name = 'icelandcouk_products'
    allowed_domains = ["groceries.iceland.co.uk", "iceland.resultspage.com"]
    search_term = ''

    BASE_URL = "http://groceries.iceland.co.uk"

    SEARCH_URL = "https://iceland.resultspage.com/search?w={search_term}&srt=0&p=Q&cnt=40&ts=json-full" \
                 "&ua={user_agent}&isort=score&filter=storeid:0 days_from_now:1&callback=searchResponse"

    NEXT_URL = "https://iceland.resultspage.com/search?w={search_term}&srt={shift}&p=Q&cnt=40&ts=json-full" \
               "&ua={user_agent}&isort=score&filter=storeid:0 days_from_now:1&callback=searchResponse"

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)" \
                 "Chrome/58.0.3029.110 Safari/537.36"

    def __init__(self, *args, **kwargs):
        super(IcelandcoukProductsSpider, self).__init__(site_name=self.allowed_domains[0], *args, **kwargs)

    def start_requests(self):
        for st in self.searchterms:
            self.search_term = st
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                    user_agent=self.USER_AGENT
                ),
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

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        cond_set_value(product, 'department', category)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        price_per_volume = self._parse_price_per_volume(response)
        cond_set_value(product, 'price_per_volume', price_per_volume)

        price_volume_measure = self._parse_price_volume_measure(response)
        cond_set_value(product, 'volume_measure', price_volume_measure)

        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//meta[@property="og:title"]/@content').extract()
        if title:
            return title[0]

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//div[@class="brand"]/p/text()').extract()
        brand = brand[0] if brand else 'Iceland'
        return brand

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//title/text()').extract()[0]
        categories = [category.strip() for category in categories.split('|')]
        if categories:
            return categories[1:-1]

    def _category_name(self, response):
        categories = self._parse_categories(response)
        if categories:
            return categories[-1]

    def _parse_image_url(self, response):
        main_image = response.xpath('//div[@id="primary_image"]/a/@href').extract()
        if main_image:
            return urljoin(self.BASE_URL, main_image[0])

    @staticmethod
    def _parse_price(response):
        # check if there is an active offer for the product
        offer = response.xpath(
            '//p[@class="truncated-text-sm" and preceding-sibling::em[contains(text(), "OFFER")]]/text()').extract()
        if offer:
            offer = offer[0]
            if 'FOR' in offer:
                offer = offer.split('FOR')
                amount = int(offer[0])
                price = re.findall(r'[\d\.\,]+', offer[1])[0]
                price = float(price.replace(',', ''))
                price = round(price / amount, 2)
                return Price(price=price, priceCurrency='GBP')

        price = response.xpath('//span[contains(@class, "big-price")]/text()').extract()
        if price:
            price = price[0]
            price = price[1:]
            price = float(price.replace(',', ''))
            return Price(price=price, priceCurrency='GBP')

    @staticmethod
    def _parse_reseller_id(response):
        url = response.xpath('//meta[@property="og:url"]/@content').extract()
        if url:
            reseller_id = re.findall(r'(?<=\/p\/)(\d+)', url[0])
            if reseller_id:
                return reseller_id[0]

    @staticmethod
    def _parse_unit_price(response):
        unit_price = response.xpath("//div[contains(@class, 'detailPriceContainer')]//div/text()").extract()
        return unit_price[0] if unit_price else None

    def _parse_price_per_volume(self, response):
        unit_price = self._parse_unit_price(response)
        if unit_price:
            price_per_volume = re.findall(FLOATING_POINT_RGEX, unit_price.split('per')[0])
            return price_per_volume[0] if price_per_volume else None

    def _parse_price_volume_measure(self, response):
        unit_price = self._parse_unit_price(response)
        if unit_price and len(unit_price.split('per')) > 1:
            volume_measure = re.findall('[a-zA-Z]+', unit_price.split('per')[1])
            return volume_measure[0] if volume_measure else None

    @staticmethod
    def _parse_no_longer_available(response):
        no_longer_available = re.search(
            'Analytics\.addToDataLayer\("product\[0\]\.productInfo\.badge", (.*?)\);',
            response.body
        )
        return 'unavailable' in no_longer_available.group(1) if no_longer_available else False

    @staticmethod
    def _parse_is_out_of_stock(response):
        return bool(response.xpath('.//p[starts-with(@class,"out-of-stock")]'))

    def _scrape_total_matches(self, response):
        json_pattern = r'(?<=searchResponse\()(.+)(?=\))'
        json_body = re.findall(json_pattern, response.body, re.DOTALL)
        try:
            json_body = json.loads(json_body[0])
            return json_body['result_meta']['total']
        except:
            self.log('Failed to load json response', WARNING)

    def _scrape_product_links(self, response):
        json_pattern = r'(?<=searchResponse\()(.+)(?=\))'
        json_body = re.findall(json_pattern, response.body, re.DOTALL)
        try:
            json_body = json.loads(json_body[0])
        except:
            self.log('Failed to load json response', WARNING)
            return

        product_links = [urljoin(self.BASE_URL, product.get('url')) for product in json_body.get('results', [])]

        for product_url in product_links:
            yield product_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        json_pattern = r'(?<=searchResponse\()(.+)(?=\))'
        json_body = re.findall(json_pattern, response.body, re.DOTALL)
        try:
            json_body = json.loads(json_body[0])
        except:
            self.log('Failed to load json response', WARNING)
            return

        next_page = json_body.get('pages', {}).get('next')
        if next_page:
            next_page = next_page.get('start')
            return self.url_formatter.format(
                self.NEXT_URL,
                search_term=urllib.quote_plus(self.search_term.encode('utf-8')),
                user_agent=self.USER_AGENT,
                shift=next_page)
