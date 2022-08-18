import re
import json
import urlparse
import traceback
from scrapy import Request
from scrapy.conf import settings

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from product_ranking.validation import BaseValidator
from spiders_shared_code.anthropologie_variants import AnthropologieVariants


class AnthropologieProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'anthropologie_products'
    allowed_domains = ["www.anthropologie.com"]
    SEARCH_URL = "https://www.anthropologie.com/search?q={search_term}"
    VARIANTS_URL = 'https://www.anthropologie.com/orchestration/features/shop?' \
                   'exclude-filter=&includePools=00443&productId={}&trim=true'

    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        retry_http_codes = settings.get('RETRY_HTTP_CODES')
        if 404 in retry_http_codes:
            retry_http_codes.remove(404)

        super(AnthropologieProductsSpider, self).__init__(
            *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en-US"
        try:
            js = json.loads(
                re.search('{"@context"(.*?)]}}', response.body).group()
            )
        except:
            self.log('JSON not found or invalid: {}'.format(traceback.format_exc()))
            product['not_found'] = True
            return product

        title = js.get('name')
        cond_set_value(product, 'title', title)

        brand = js.get('brand', {}).get('name')
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        image_url = js.get('image')
        cond_set_value(product, 'image_url', image_url)

        price = js.get('offers', {}).get('lowPrice')
        currency = js.get('offers', {}).get('priceCurrency')
        if price:
            cond_set_value(product, 'price', Price(currency, price))

        is_out_of_stock = js.get('offers', {}).get('availability')
        if is_out_of_stock  and 'InStock' in is_out_of_stock:
            out_of_stock = False
        else:
            out_of_stock = True
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        description = self._parse_description(js)
        cond_set_value(product, 'description', description)

        sku = js.get('mpn')
        cond_set_value(product, 'sku', sku)

        categories = response.xpath(
                "//ol[contains(@class, 'c-breadcrumb__ol u-clearfix')]"
                "//li[not(contains(@class, 'c-breadcrumb__li--last'))]"
                "//span[contains(@itemprop, 'name')]/text()").extract()
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        reviews = js.get('aggregateRating', {})
        if 'aggregateRating' in response.body:
            buyer_reviews = {
                'num_of_reviews': reviews.get('ratingCount', 0),
                'average_rating': round(reviews.get('ratingValue', 0), 1),
                'rating_by_star': {}
            }
            cond_set_value(product, 'buyer_reviews', BuyerReviews(**buyer_reviews))
        else:
            cond_set_value(product, 'buyer_reviews', BuyerReviews(**ZERO_REVIEWS_VALUE))

        prod_id = re.search('product_id : (.*?)]', response.body)
        if prod_id:
            prod_id = prod_id.group(1).replace('[', '').replace('"', '')
            return Request(self.VARIANTS_URL.format(prod_id),
                           callback=self.parse_variants,
                           meta={"product": product})

        return product

    def _parse_description(self, js):
        short_description = js.get('description')
        if short_description:
            if '**' in short_description:
                i = short_description.find("**")
                short_description_index = short_description[:i]
                if short_description_index:
                    if '\n' in short_description_index:
                        return short_description_index.replace('\n', '')
                    return short_description_index

            elif '\n' in short_description:
                short_description = short_description.replace('\n', '')
                return short_description

    def parse_variants(self, response):
        product = response.meta['product']
        variants_json = json.loads(response.body)

        anthropologie_variants = AnthropologieVariants()
        anthropologie_variants.setupSC(response)
        variants = anthropologie_variants._variants(variants_json)
        cond_set_value(product, 'variants', variants)

        return product

    def _scrape_total_matches(self, response):
        total_matches = is_empty(
            response.xpath(
                '//*[@data-qa-search-results-count]'
            ).re('(\d+)'), 0
        )

        return int(total_matches)

    def _scrape_product_links(self, response):
        links = response.xpath('//*[@data-qa-product-tile]/@href').extract()
        for link in links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = is_empty(
            response.xpath('//*[@data-qa-nextpage]/@href').extract()
        )
        if next_page:
            return urlparse.urljoin(response.url, next_page)
