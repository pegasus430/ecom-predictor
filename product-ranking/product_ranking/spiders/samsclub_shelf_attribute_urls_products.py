import re
import urlparse
from scrapy.http import Request
from scrapy.conf import settings

from product_ranking.items import AttributeProductItem
from product_ranking.utils import append_get_arguments
from product_ranking.spiders.samsclub_shelf_pages import SamsclubShelfPagesSpider


class SamsclubAttributePagesSpider(SamsclubShelfPagesSpider):
    name = 'samsclub_shelf_attribute_urls_products'
    allowed_domains = ["samsclub.com"]

    EXCLUDED_SECTIONS = [
        'how_to_get_it',
        'price',
        'product_rating'
    ]

    def __init__(self, *args, **kwargs):
        super(SamsclubAttributePagesSpider, self).__init__(*args, **kwargs)
        pipelines = settings.get('ITEM_PIPELINES')
        pipelines.pop('product_ranking.pipelines.AddSearchTermInTitleFields', None)
        pipelines.pop('product_ranking.pipelines.AddCrawledAt', None)
        settings.overrides['ITEM_PIPELINES'] = pipelines

    def parse(self, response):
        for filter in self._get_filters(response):
            yield Request(
                url=append_get_arguments(response.url, {'rootDimension': filter}),
                callback=self._parse_products,
            )

    def _get_filters(self, response):
        filters = re.findall(r'urlParameter&#39;:&#39;(.*?)&#39;', response.body)
        return [filter for filter in filters if not any(sec_name in filter for sec_name in self.EXCLUDED_SECTIONS)]

    def _parse_products(self, response):
        attribute_name = self._parse_attribute_name(response)
        attribute_value = self._parse_attribute_value(response)
        category_id = self._parse_category_id(response.url)
        for product in self._get_product_elements(response):
            item = AttributeProductItem()
            item.update({
                'shelf_url': self.product_url,
                'category_id': category_id,
                'product_id': self._parse_product_id(product),
                'title': self._parse_title(product),
                'url': self._parse_product_url(product),
                'attribute': attribute_name,
                'value': attribute_value,
                'character_count': len(attribute_value) if attribute_value else 0
            })
            yield item
        yield self._get_next_products_page(response)

    def _get_next_products_page(self, response):
        current_page = response.meta.get('current_page', 1)
        total_matches = response.meta.get('total_matches') or self._scrape_total_matches(response)
        if total_matches > current_page * self.prods_per_page:
            return Request(
                url=append_get_arguments(
                    response.url,
                    {'offset': current_page * self.prods_per_page, 'navigate': current_page + 1}
                ),
                callback=self._parse_products,
                meta={
                    'total_matches': total_matches,
                    'current_page': current_page + 1
                }
            )

    @staticmethod
    def _parse_attribute_name(response):
        attr_name = response.xpath(
            '//div[@class="facets-wrapper" and .//span[contains(@class, "true")]]//h2/text()'
        ).extract()
        return attr_name[0] if attr_name else None

    @staticmethod
    def _parse_attribute_value(response):
        attr_value = response.xpath('//span[contains(@class, "true")]/parent::label/@for').extract()
        return attr_value[0] if attr_value else None

    @staticmethod
    def _parse_category_id(url):
        cat_id = re.search(r'sams/(.*?)\?', url)
        return cat_id.group(1) if cat_id else None

    @staticmethod
    def _get_product_elements(response):
        return response.xpath('//div[@class="products-card"]')

    @staticmethod
    def _parse_product_id(product):
        prod_id = product.xpath('.//span[@data-product-id]/@data-product-id').extract()
        return prod_id[0] if prod_id else None

    @staticmethod
    def _parse_title(product):
        title = product.xpath('.//img/@alt').extract()
        return title[0] if title else None

    def _parse_product_url(self, product):
        url = product.xpath('.//a[@ng-click]/@href').extract()
        return urlparse.urljoin(self.product_url, url[0]) if url else None
