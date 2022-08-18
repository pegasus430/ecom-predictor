from __future__ import division, absolute_import, unicode_literals

import json
import traceback
from urlparse import urljoin

import re
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import Price, BuyerReviews, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults
from product_ranking.spiders import cond_set, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.utils import is_empty
from scrapy import Request
from scrapy.conf import settings

from spiders_shared_code.bestbuy_variants import BestBuyVariants


class BestBuyProductSpider(BaseProductsSpider):
    name = 'bestbuy_products'
    allowed_domains = ['bestbuy.com']
    # TODO fix this {product_url} to {product_id}
    REVIEW_URL = "http://bestbuy.ugc.bazaarvoice.com/3545w/{product_url}/reviews.djs?format=embeddedhtml"

    SEARCH_URL = "http://www.bestbuy.com/site/searchpage.jsp?_dyncharset=UTF-" \
                 "8&_dynSessConf=&id=pcat17071&type=page&sc=Global&cp={page}" \
                 "&nrp=&sp=&qp=" \
                 "&list=n&iht=y&usc=All+Categories&ks=960&st={search_term}"

    API_PRICES_URL = 'http://www.bestbuy.com/api/1.0/carousel/prices?skus={}'

    HEADERS = {
        'Host': 'www.bestbuy.com',
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/62.0.3202.94 Safari/537.36",
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/61.0.3163.100 Safari/537.36"

        super(BestBuyProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                page=1),
            *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        for request in super(BestBuyProductSpider, self).start_requests():
            request = request.replace(headers=self.HEADERS)
            yield request

    def parse_product(self, response):
        product = response.meta['product']
        rows = is_empty(response.xpath(
            "//div[contains(@class,'cart-button')]/@data-add-to-cart-message"
        ).extract(), '')
        if "Sold Out Online" in rows:
            product['is_out_of_stock'] = True
        else:
            product['is_out_of_stock'] = False
        if 'this item is no longer available' in response.body_as_unicode().lower():
            product['no_longer_available'] = True
            return product

        self._populate_from_schemaorg(response, product)

        title = is_empty(response.css(".sku-title ::text").extract())
        if not title:
            title = is_empty(response.xpath('//h1[@class="type-subhead-alt-regular"]/text()').extract())

        if title and len(re.split(r'\s+-\s+ | -', title, 1)) > 1:
            brand, _ = re.split(r'\s+-\s+', title, 1)
            cond_set_value(product, 'brand', brand)
        cond_set_value(product, 'title', title)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        reseller_id = response.css("#sku-value ::text").extract()
        cond_set(product, 'reseller_id', reseller_id)

        cond_set(product, 'model',
                 response.css("#model-value ::text").extract())

        new_meta = {}
        new_meta['product'] = product
        variants = product.get('variants', [])
        if variants:
            # Search for variants with Sku
            variants_with_skuId = {}
            for variant in variants:
                if 'skuId' in variant:
                    variants_with_skuId[variant['skuId']] = variant

            # Request prices for those skus
            api_prices_url = self.API_PRICES_URL.format(
                ','.join(variants_with_skuId.keys()))
            new_meta['variants_with_skuId'] = variants_with_skuId
            return Request(api_prices_url,
                           dont_filter=True,
                           callback=self._parse_variant_prices,
                           meta=new_meta)
        else:
            prod_id = product.get("sku")
            if prod_id:
                return Request(self.REVIEW_URL.format(product_url=prod_id),
                               dont_filter=True,
                               callback=self.parse_buyer_reviews,
                               meta=new_meta)
        return product

    def _parse_variant_prices(self, response):
        try:
            price_ajax_list = json.loads(response.body)
        except:
            price_ajax_list = []
        variants_with_skuId = response.meta['variants_with_skuId']
        product = response.meta['product']
        variants = product.get('variants')

        new_meta = {}
        new_meta['product'] = product

        for price_ajax in price_ajax_list:
            # Update price
            vr = variants_with_skuId[price_ajax['skuId']]
            index = variants.index(vr)
            vr['price'] = price_ajax.get('currentPrice', None) or price_ajax.get('regularPrice', None)
            # Replace
            variants.pop(index)
            variants.insert(index, vr)

        prod_id = product.get("reseller_id")
        if prod_id:
            return Request(self.REVIEW_URL.format(product_url=prod_id),
                           dont_filter=True,
                           callback=self.parse_buyer_reviews,
                           meta=new_meta)
        return product

    def _populate_from_schemaorg(self, response, product):
        product_tree = response.xpath("//*[@itemtype='http://schema.org/Product']")

        cond_set(product, 'reseller_id', product_tree.xpath(
            "//*[@itemtype='http://schema.org/Product']//*[@id='pdp-model-data']/@data-sku-id"
        ).extract())

        cond_set(product, 'title', product_tree.xpath(
            "descendant::*[not (@itemtype)]/meta[@itemprop='name']/@content"
        ).extract())

        image = is_empty(response.xpath(
            '//div[@id="carousel-main"]//img/@data-img-path'
        ).extract())
        if image:
            image_url = re.sub(
                r'(maxHeight)=\d+;(maxWidth)=\d+', r'\1=1000;\2=1000', image)
            cond_set_value(product, 'image_url', image_url)

        cond_set(product, 'model', product_tree.xpath(
            "descendant::*[not (@itemtype)]/*[@itemprop='model']/text()"
        ).extract())

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        brand_tree = product_tree.xpath(
            ".//*[@itemtype='http://schema.org/Brand']"
        )
        cond_set(product, 'brand', brand_tree.xpath(
            "descendant::*[not (@itemtype) and @itemprop='name']/@content"
        ).extract())

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        sku = self._sku(response)
        product['sku'] = sku

    def _sku(self, response):
        sku = response.xpath("//span[@id='sku-value']/text()").extract()
        return sku[0] if sku else None

    def _parse_categories(self, response):
        categories = response.xpath(
            "//ol[@id='breadcrumb-list']"
            "/li/a/text()")[1:].extract()
        return categories if categories else None

    def _parse_price(self, response):
        in_cart_price = response.xpath('//div[@class="priceView-restricted-price"]//a/text()').extract()
        price = None
        if in_cart_price:
            if in_cart_price[0].lower() == 'see price in cart':
                price = re.search('"currentPrice":(.*?),', response.body)
                price = price.group(1) if price else None
        else:
            price = response.xpath('//div[contains(@class, "pb-current-price")]/span/text()').re(FLOATING_POINT_RGEX)
            if not price:
                price = response.xpath('//div[contains(@class, "priceView-purchase-price")]'
                                       '/span/text()').re(FLOATING_POINT_RGEX)
            price = price[0] if price else None

        if price:
            try:
                return Price(price=float(price.replace(',', '')), priceCurrency='USD')
            except:
                self.log("Error while parsing price {}".format(traceback.format_exc()))

    def _parse_variants(self, response):
        bestbuy_variants = BestBuyVariants()
        bestbuy_variants.setupSC(response)
        return bestbuy_variants._variants()

    def parse_buyer_reviews(self, response):

        buyer_reviews_per_page = self.br.parse_buyer_reviews_per_page(response)
        product = response.meta['product']
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews_per_page)

        return product

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        total_matches = is_empty(response.xpath(
            '//span[@class="count"]/text()'
        ).re('([\d,]+)'), '0').replace(',', '')
        return int(total_matches)

    def _scrape_next_results_page_link(self, response):
        next_link = response.css('.pager-next::attr(data-page-no)')
        if not next_link:
            return None
        try:
            next_link = int(next_link.extract()[0])
            search_term = response.meta['search_term']
            return self.url_formatter.format(self.SEARCH_URL,
                                             search_term=search_term,
                                             page=next_link)
        except:
            return

    def _scrape_product_links(self, response):
        links = response.xpath('//div[@class="sku-title"]/h4/a/@href').extract()
        for link in links:
            res_item = SiteProductItem()
            yield urljoin(response.url, link), res_item

    def _scrape_results_per_page(self, response):
        return 24
