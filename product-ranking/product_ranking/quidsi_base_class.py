import re
import string
import urlparse
import json
import traceback

from scrapy import Request
from scrapy.log import WARNING

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import (BaseProductsSpider, cond_set_value,
                                     FLOATING_POINT_RGEX)
from product_ranking.utils import is_empty


class QuidsiBaseProductsSpider(BaseProductsSpider):

    def start_requests(self):
        for item in super(QuidsiBaseProductsSpider, self).start_requests():
            yield item.replace(dont_filter=True)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        cond_set_value(product, 'locale', 'en-US')

        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        brand = self._parse_brand(response)
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        categories = self._parse_categories(response)
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)
        cond_set_value(product, 'reseller_id', sku)

        variants = self._parse_variants(response)

        if not variants:
            asin = self._parse_asin(response)
            cond_set_value(product, 'asin', asin)
            is_out_of_stock = self._parse_stock_status(response)
            cond_set_value(product, 'is_out_of_stock', is_out_of_stock, conv=bool)
        elif len(variants) == 1:
            vr = variants[0]
            cond_set_value(product, 'is_out_of_stock', not vr.get('in_stock'))
            cond_set_value(product, 'asin', vr.get('asin'))
            variants = None
        else:
            in_stock = any([var.get('in_stock') for var in variants])
            cond_set_value(product, 'is_out_of_stock', not in_stock)

        cond_set_value(product, 'variants', variants)

        group_id = re.search('PowerReview.groupId = (\d+);', response.body)
        if group_id and re.search('mosthelpful_default', response.body):
            prodpath = self._build_prodpath(group_id.group(1))
            url = self.REVIEWS_URL.format(prodpath=prodpath)
            meta = {'product': product}
            return Request(url, self._parse_buyer_reviews, meta=meta, dont_filter=True)

        return product

    def _build_prodpath(self, gid):
        gid = string.zfill(gid, 6)
        return gid[0:2] + "/" + gid[2:4] + "/" + gid[4:]

    def _parse_stock_status(self, response):
        is_out_of_stock = is_empty(
            response.xpath(
                '//*[@class="skuHidden"]/@isoutofstock'
            ).extract()
        )

        return not is_out_of_stock == 'N'

    def _parse_categories(self, response):
        categories = response.xpath(
            '//*[@class="positionNav "]//a/text()').extract()

        return categories

    def _parse_description(self, response):
        description = is_empty(
            response.xpath(
                '//*[contains(@class, "descriptContentBox")]'
            ).extract()
        )

        return description

    def _parse_asin(self, response):
        asin = is_empty(
            response.xpath(
                '//*[@class="skuHidden"]/@asin'
            ).extract()
        )

        return asin

    def _parse_sku(self, response):
        sku = is_empty(
            response.xpath(
                '//*[@itemprop="sku"]/@content'
            ).extract()
        )

        return sku

    def _parse_image_url(self, response):
        image_url = is_empty(
            response.xpath(
                '//a[@class="MagicZoomPlus"]/@href'
            ).extract()
        )

        if not image_url:
            image_url = is_empty(
                response.xpath(
                    '//img[@id="pdpMainImageImg"]/@src'
                ).extract()
            )

        if not image_url:
            return None

        return urlparse.urljoin(response.url, image_url)

    def _parse_title(self, response):
        title = is_empty(
            response.xpath(
                '//*[@itemprop="name"]/text()'
            ).extract()
        )

        return title

    def _parse_price(self, response):
        price = is_empty(
            response.xpath(
                '//*[@class="singlePrice"]/text()'
            ).re(FLOATING_POINT_RGEX)
        )

        if not price:
            return None

        return Price(price=price, priceCurrency='USD')

    def _parse_brand(self, response):
        brand = is_empty(
            response.xpath(
                '//div[@class="viewBox"]//a/text()'
            ).extract()
        )

        return brand

    def _parse_variants(self, response):
        try:
            items = json.loads(
                re.search(
                    'pdpOptionsJson\s*=\s*(\[.*\])',
                    response.body_as_unicode()
                ).group(1)
            )
        except:
            self.log('JSON not found or invalid JSON: {}'.format(traceback.format_exc()))
            return None

        variants = []
        properties_dict = {}
        properties = response.xpath('//*[contains(@class, "attributeOption")]')
        for prop in properties:
            prop_id = is_empty(prop.xpath('@id').extract())
            prop_attr = is_empty(
                prop.xpath(
                    './/*[contains(@class, "attributeValue")]/b/text()'
                ).extract()
            )
            if prop_id and prop_attr:
                properties_dict[prop_id] = prop_attr

        properties_names = response.xpath(
            '//span[@class="attributeTitle"]/text()').extract()

        for item in items:
            attr_values = [
                item.get('PrimaryAttributeValue'),
                item.get('SecondAttributeValue'),
                item.get('ThirdAttributeValue'),
            ]
            if not any(attr_values):
                continue

            variant = {
                'properties': dict(zip(properties_names,
                    [properties_dict.get(key) for key in attr_values]
                )),
                'in_stock': 'N' in item.get('IsOutOfStock', ''),
                'price': item.get('RetailPrice'),
                'asin': item.get('Asin'),
                'sku': item.get('Sku')
            }
            variants.append(variant)

        return variants

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        num_of_reviews = is_empty(
            response.xpath(
               '//span[@class="pr-review-num"]/text()'
            ).re('(\d+) REVIEWS'), '0'
        )
        average_rating = is_empty(
            response.xpath(
                '//span[contains(@class,"average")]/text()'
            ).extract(), '0'
        )

        stars = response.xpath("//div[@class='pr-info-graphic-amazon']/dl")
        distribution = {}
        for star in stars:
            key = is_empty(star.xpath(
                "dd[contains(text(),'star')]/text()"
            ).re(r"(\d+) star"))
            value = is_empty(star.xpath("dd/text()").re(r"\((\d+)\)"))
            try:
                key = str(key)
                value = int(value)
            except:
                distribution = {}
                break

            distribution[key] = value

        buyer_reviews = BuyerReviews(
            int(num_of_reviews),
            float(average_rating),
            distribution
        )
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        last_date = is_empty(
            response.xpath(
                '//*[@class="pr-review-author-date pr-rounded"]/text()'
            ).extract()
        )
        cond_set_value(product, 'last_buyer_review_date', last_date)

        return product

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//a[@class="product-box-link"]/@href'
        ).extract()

        if not links:
            links = response.xpath('//ul[contains(@class, "s-result-list")]/li[contains(@id, "result_")]'
                                   '//a[contains(@class, "s-access-detail-page")]/@href').extract()

        if not links:
            self.log("Found no product links.", WARNING)
        for link in links:
            yield link, SiteProductItem()

    def _scrape_total_matches(self, response):
        total_matches = is_empty(
            response.xpath(
                '//*[@class="searched-stats"]//text()'
            ).re('of ([\d,]+)'), '0'
        ).replace(',', '')
        if not total_matches:
            total_matches = is_empty(response.xpath('//*[contains(@id, "s-result-count")]'
                                                    '/text()').re('([\d,]+) result'), '0').replace(',', '')
        return int(total_matches)

    def _scrape_next_results_page_link(self, response):
        next_page = is_empty(
            response.xpath(
                '//a[@class="next"]/@href'
            ).extract()
        )
        return next_page
