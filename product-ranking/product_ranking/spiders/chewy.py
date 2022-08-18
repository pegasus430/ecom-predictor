import re
import string
import urlparse
import traceback

from scrapy import Request
from scrapy.log import WARNING, INFO

from product_ranking.utils import is_empty
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import cond_set_value, FLOATING_POINT_RGEX
from product_ranking.spiders.contrib.product_spider import ProductsSpider
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi


class ChewyProductsSpider(ProductsSpider):
    name = 'chewy_products'
    allowed_domains = ['chewy.com']

    SEARCH_URL = "https://www.chewy.com/s?query={search_term}"

    BUYER_REVIEWS_URL = ("http://chewy.ugc.bazaarvoice.com/0090-en_us"
                         "/{product_id}/reviews.djs?format=embeddedhtml")

    HEADER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/59.0.3071.86 Safari/537.36"}

    def __init__(self, *args, **kwargs):
        super(ChewyProductsSpider, self).__init__(*args, **kwargs)
        self.br = BuyerReviewsBazaarApi(called_class=self)

    def start_requests(self):
        for request in super(ChewyProductsSpider, self).start_requests():
            request = request.replace(headers=self.HEADER)
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        reqs = []
        product = response.meta['product']

        if self._parse_no_longer_available(response):
            product['no_longer_available'] = True
            return product
        else:
            product['no_longer_available'] = False

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

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
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Shipping included
        shipping_included = self._parse_shipping_included(response)
        cond_set_value(product, 'shipping_included', shipping_included)

        product_id = response.xpath(
            '//script[contains(text(),"show_reviews")]').re(
            'productId: "(\d+)"')

        if product_id:
            # Parse buyer reviews
            reqs.append(
                Request(
                    url=self.BUYER_REVIEWS_URL.format(
                        product_id=product_id[0]),
                    dont_filter=True,
                    callback=self.br.parse_buyer_reviews,
                    meta={'product': product},
                )
            )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1/text()').extract()
        return title[0].strip() if title else None

    @staticmethod
    def _parse_price(response):
        price = response.xpath('//li[@class="our-price"]'
                               '//span[@class="ga-eec__price"]/text()').re(FLOATING_POINT_RGEX)
        if price:
            return Price(price=price[0], priceCurrency='USD')

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath(
            '//a[@class="MagicZoomPlus"]/@href').extract()
        return 'http:' + image_url[0] if image_url else None

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath(
            '//*[@id="brand"]//a/text()').extract()
        if not brand:
            brand = response.xpath('//div[@class="ga-eec__brand"]/text()').extract()
        return brand[0].strip() if brand else None

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//*[@itemprop="sku"]/@content').extract()
        return sku[0] if sku else None

    @staticmethod
    def _parse_variants(response):
        variants_data = response.xpath(
            '//script[contains(text(),"itemData")]').extract()
        if not variants_data:
            return None

        variants_data = variants_data[0].replace('\n', '')

        skus = re.findall('\'(\d+)\' : {', variants_data)
        prices = re.findall('price: \'\$([\d\.]+)', variants_data)
        urls = re.findall('canonicalURL: \'(.*?)\'', variants_data)
        imgs_raw = re.findall('images: \[(.*?)\]', variants_data)
        imgs = []
        for img in imgs_raw:
            imgs.append(["http:" + x.replace('\'', '').strip() for x in img.split(',') if x.strip()])

        variants = []
        for item in zip(skus, prices, urls, imgs):
            vr = {}
            cond_set_value(vr, 'price', item[1])
            cond_set_value(vr, 'url', urlparse.urljoin(response.url, item[2]))
            cond_set_value(vr, 'image_urls', item[3])
            vr['selected'] = True if item[0] in response.url else False

            if vr:
                variants.append(vr)

        return variants if variants and len(variants) > 1 else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        status = response.xpath(
            '//*[@id="availability"]/span[text()="In stock"]')

        return not bool(status)

    @staticmethod
    def _parse_shipping_included(response):
        shipping_text = ''.join(
            response.xpath('//span[@class="free-shipping"]//text()').extract())

        return shipping_text == ' & FREE Shipping'

    @staticmethod
    def _parse_description(response):
        description = response.xpath('//section[contains(@class,"descriptions__content")]').extract()

        return description[0] if description else None

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        if reqs:
            req.meta["reqs"] = reqs

        return req

    @staticmethod
    def _parse_no_longer_available(response):
        message = response.xpath(
            '//div[@class="error" and '
            'contains(., "The product you are trying to view is not currently available.")]')
        return bool(message)

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = re.findall('dp\/(\d+)', response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        return reseller_id

    def _scrape_total_matches(self, response):
        try:
            total_matches = is_empty(
                response.xpath(
                    '//p[@class="results-count"]/text()'
                ).re('of (\d+)'), '0')

            return int(total_matches)
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))

    def _scrape_results_per_page(self, response):
        items = response.xpath(
            '//*[contains(@class, "product")]/a/@href').extract()

        return len(items) if items else 0

    def _scrape_product_links(self, response):
        item_urls = response.xpath(
            '//*[contains(@class, "product")]/a/@href').extract()
        if item_urls:
            for item_url in item_urls:
                yield item_url, SiteProductItem()
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        url = is_empty(
            response.xpath(
                '//a[contains(@class, "cw-btn--next")]/@href').extract()
        )

        if url:
            next_page_link = urlparse.urljoin(response.url, url)
            return next_page_link
        else:
            self.log("Found no 'next page' links", WARNING)
            return None
