import json
import re
import string

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import cond_set_value
from product_ranking.spiders.contrib.product_spider import ProductsSpider
from scrapy.conf import settings


class PetBaseProductsSpider(ProductsSpider):
    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        settings.overrides[
            'RETRY_HTTP_CODES'] = [500, 502, 503, 504, 400, 403, 408]
        super(PetBaseProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def _total_matches_from_html(self, response):
        return 0

    def _scrape_results_per_page(self, response):
        results_per_page = response.xpath(
            '//span[text()="Items Per Page:"]/following-sibling::div/'
            'button[1]/text()').extract()
        return int(results_per_page[0]) if results_per_page else 0

    def _scrape_next_results_page_link(self, response):
        next = response.xpath('//a[@title="Next"]/@href').extract()
        return next[0] if next else None

    def _scrape_product_links(self, response):
        item_urls = response.css(
            '.item .sli_grid_title  > a::attr("href")').extract()

        for item_url in item_urls:
            yield item_url, SiteProductItem()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _parse_title(self, response):
        title = response.xpath('//h1/text()').extract()
        return title[0].strip() if title else None

    def _parse_categories(self, response):
        categories = response.xpath(
            '//*[@id="breadcrumbs"]'
            '//*[self::a or self::strong]/text()').extract()
        return categories if categories else None

    def _parse_category(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_price(self, response):
        try:
            price = min(map((float),
                            re.findall('"finalPrice":"([\d\.]+)"', response.body)))
            return Price(price=price, priceCurrency='USD')

        except:
            import traceback
            print traceback.print_exc()
            return None

    def _parse_image_url(self, response):
        image_url = response.css(
            '.image>img::attr("src")').extract()

        return image_url[0] if image_url else None

    def _parse_brand(self, response):
        brand = response.xpath(
            '//*[@class="product-brand"]/a/text()').re('by.(.*)')

        return brand[0].strip() if brand else None

    def _parse_sku(self, response):
        sku = response.xpath(
            '//*[@id="product-sku"]/text()').extract()

        return sku[0] if sku else None

    def _parse_variants(self, response):
        variants = []
        variants_prop = {}

        variant_search = re.search('Product.Config\((.*)\)', response.body)
        if not variant_search:
            return None

        try:
            variants_json = json.loads(variant_search.group(1))
        except ValueError:
            return None

        for attr_id in response.xpath(
            '//div[not(contains(@class,"hidden"))]/div/'
                'select/@name').re('super_attribute\[(\d+)\]'):

            attribute = variants_json['attributes'][attr_id]
            attribute_name = attribute['label']

            for option in attribute['options']:
                value = option['label']
                for product in option['products']:
                    prop = variants_prop.get(product, {})
                    prop[attribute_name] = value
                    variants_prop[product] = prop

        for variant_id in variants_json['childProducts']:
            vr = {}
            variant = variants_json['childProducts'][variant_id]
            sku = variant.get('productSku')
            cond_set_value(vr, 'skuId', sku)
            final_price = variant.get('finalPrice')
            cond_set_value(vr, 'price', final_price)
            prop = variants_prop[variant_id]
            cond_set_value(vr, 'properties', prop)
            variants.append(vr)

        return variants if variants else None

    def _parse_description(self, response):
        description = response.css(
            '.short_description, .description').extract()

        return ''.join(description).strip() if description else None

    def _parse_buyer_reviews(self, response):
        avg = response.xpath(
            '//*[@class="pr-rating pr-rounded average"]/text()').extract()

        avg = (float(avg[0]) if avg else 0.0)

        num_reviews = response.xpath(
            '//*[@class="pr-snapshot-average-based-on-text"]'
            '/span/text()').extract()

        num_reviews = (int(num_reviews[0]) if num_reviews else 0)

        ratings_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        keys = response.xpath(
            '(//ul[@class="pr-ratings-histogram-content"])[1]'
            '//*[@class="pr-histogram-label"]//span/text()').re('(\d+) Stars')
        values = response.xpath(
            '(//ul[@class="pr-ratings-histogram-content"])[1]'
            '//*[@class="pr-histogram-count"]/span').re('(\d+)')

        for (key, value) in zip(keys, values):
            ratings_by_star[key] = int(value)

        return BuyerReviews(num_of_reviews=num_reviews,
                            average_rating=avg,
                            rating_by_star=ratings_by_star)

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def parse_product(self, response):
        reqs = []
        product = response.meta['product']
        response.meta['product_response'] = response
        # Set locale
        product['locale'] = 'en_US'
        product['url'] = response.url

        if response.status == 404:
            cond_set_value(product, 'not_found', True)
            cond_set_value(product, 'is_out_of_stock', True)
            return product

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        # Parse stock status
        cond_set_value(product, 'is_out_of_stock', False)

        # Sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Reseller_id
        cond_set_value(product, 'reseller_id', sku)

        # Brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        buyer_reviews = self._parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        if reqs:
            return self.send_next_request(reqs, response)

        return product