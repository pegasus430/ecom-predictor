# -*- coding: utf-8 -*-

import json
import traceback
import urllib
import urlparse

from scrapy import Request
from scrapy.conf import settings
from scrapy.log import INFO, ERROR, WARNING

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, cond_set_value,
                                     FormatterWithDefaults)
from product_ranking.utils import is_empty
from spiders_shared_code.macys_variants import MacysVariants


class MacysProductsSpider(BaseProductsSpider):
    name = 'macys_products'
    allowed_domains = ['macys.com', 'macys.ugc.bazaarvoice.com']

    SEARCH_URL = "https://www.macys.com/shop/featured/{search_term}"

    REVIEWS_URL = "https://www.macys.com/xapi/digital/v1/product/{product_id}/reviews?limit=1"

    IMAGE_URL_TEMPLATE = 'http://slimages.macysassets.com/is/image/MCY/products/{image_url}?wid=2000&hid=2000'

    def __init__(self, *args, **kwargs):
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        super(MacysProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page=1),
            site_name=self.allowed_domains[0],
            *args, **kwargs)
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36" \
                          " (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36"
        settings.overrides['DEFAULT_REQUEST_HEADERS'] = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'x-forwarded-for': '172.0.0.1'
        }
        settings.overrides['USE_PROXIES'] = False
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2

    def start_requests(self):
        for request in super(MacysProductsSpider, self).start_requests():
            if not self.product_url:
                st = request.meta.get('search_term')
                st = st.replace(' ', '-')
                url = self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                )
                request = request.replace(url=url)
            yield request.replace(cookies={'shippingCountry': 'US'})

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta.get('product', SiteProductItem())
        is_collection = response.xpath(".//*[@id='memberItemsTab']/a[@href='#collectionItems']"
                                       "/*[contains(text(),'Choose Your Items')]")
        if is_collection:
            self.log("{} - item is collection, dropping the item".format(response.url), INFO)
            return product

        if u'>this product is currently unavailable' in response.body_as_unicode().lower():
            product['no_longer_available'] = True
            return product

        try:
            data = json.loads(is_empty(response.xpath('//script[@data-bootstrap="feature/product"]/text()')
                                       .extract()))
        except:
            self.log('JSON not found: {}'.format(traceback.format_exc()), ERROR)
            product['not_found'] = True
            return product

        product_data = data.get('product', {})

        cond_set_value(product, 'locale', 'en_US')

        cond_set_value(product, 'title', product_data.get('detail', {}).get('name'))

        image_urls = [image.get('filePath') for image in product_data.get('imagery', {}).get('images', [])
                      if image.get('filePath')]
        if image_urls:
            cond_set_value(product, 'image_url', self.IMAGE_URL_TEMPLATE.format(image_url=is_empty(image_urls)))

        description = product_data.get('detail', {}).get('description')
        cond_set_value(product, 'description', description)

        brand = product_data.get('detail', {}).get('brand', {}).get('name')
        cond_set_value(product, 'brand', brand)

        is_out_of_stock = not data.get('viewState', {}).get('availability', {}).get('available')
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        price = is_empty(is_empty(product_data.get('pricing', {}).get('price', {}).get('tieredPrice', []), {})
                         .get('values', []), {}).get('value')
        if price:
            price = Price(price=price, priceCurrency='USD')
            cond_set_value(product, 'price', price)

            special_pricing = data.get('product', {}).get('pricing', {}).get('price', {}) \
                .get('priceType', {}).get('onSale')
            cond_set_value(product, 'special_pricing', special_pricing)

        product_id = product_data.get('id')
        cond_set_value(product, 'reseller_id', product_id)

        categories = [category.get('name') for category in
                      data.get('product', {}).get('relationships', {}).get('taxonomy', {}).get('categories',
                                                                                               [])]
        cond_set_value(product, 'categories', categories)
        cond_set_value(product, 'department', categories[-1] if categories else None)

        mv = MacysVariants()
        mv.setupSC(response)
        try:
            variants = mv._variants()
        except Exception as e:
            self.log('Cant get variants: {}'.format(traceback.format_exc()), WARNING)
            product['variants'] = []
        else:
            product['variants'] = variants

        if product.get('variants', []):
            # One-variation product
            if len(product.get('variants')) == 1:
                product['upc'] = product.get('variants')[0].get('upc')

        # Reviews
        if product_id and is_empty(data.get('utagData', {}).get('product_reviews', [])):
            return Request(url=self.REVIEWS_URL.format(product_id=product_id),
                           callback=self._on_reviews_response,
                           meta={'product': product},
                           dont_filter=True)

        return product

    def _on_reviews_response(self, response):
        product = response.meta.get('product', {})
        try:
            data = json.loads(response.body)
        except ValueError:
            self.log("Reviews json data parsing error")
            return product

        reviews_data = is_empty(data.get('review', {}).get('includes', {}).get('products', {}).values(), {}) \
            .get('reviewStatistics', {})
        stars = reviews_data.get('ratingDistribution', [])
        buyer_reviews = {
            'num_of_reviews': int(reviews_data.get('totalReviewCount', 0)),
            'average_rating': round(reviews_data.get('averageOverallRating', 0), 1),
            'rating_by_star': dict(zip([unicode(star.get('ratingValue')) for star in stars],
                                       [star.get('count') for star in stars]))
        }
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews)
        return product

    def _scrape_next_results_page_link(self, response):
        next_link = response.xpath("//li[contains(@class, 'next-page')]//a/@href").extract()
        if next_link:
            next_link = urlparse.urljoin(response.url, next_link[0])
            return Request(
                url=next_link,
                dont_filter=True,
                cookies=response.request.cookies,
                meta=response.meta
            )

    def _scrape_total_matches(self, response):
        totals = is_empty(
            response.xpath(
                '//*[@id="productCount"]'
            ).re('\d+'), '0'
        )

        return int(totals)

    def _scrape_product_links(self, response):
        urls = response.xpath(
            '//span[contains(@id, "main_images_holder")]/../../a/@href'
        ).extract()
        if not urls:
            urls = response.xpath('//div[@class="productDescription"]/a[@class="productDescLink"]/@href').extract()
        for url in [urlparse.urljoin(response.url, i) for i in urls]:
            item = SiteProductItem()
            yield Request(url,
                          self.parse_product,
                          cookies=response.request.cookies,
                          meta={'product': item},
                          ), item
