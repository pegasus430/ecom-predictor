import urllib
import re
from scrapy import Request
import urlparse

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.utils import is_empty
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import (BaseProductsSpider, cond_set_value, cond_set,
                                     FLOATING_POINT_RGEX, FormatterWithDefaults)


class SupplyworksProductsSpider(BaseProductsSpider):
    name = 'supplyworks_products'
    allowed_domains = ['www.supplyworks.com']

    SEARCH_URL = "https://www.supplyworks.com/Search?keywords={search_term}&filterByCustomizedProductOffering=False&page={page_num}"

    def __init__(self, *args, **kwargs):
        self.current_page = 1
        formatter = FormatterWithDefaults(page_num=self.current_page)
        super(SupplyworksProductsSpider, self).__init__(
            formatter,
            site_name=self.allowed_domains[0],
            *args, **kwargs
        )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en-US"

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        cond_set_value(product, 'is_out_of_stock', False)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._parse_department(response)
        cond_set_value(product, 'department', department)

        return product

    def _parse_title(self, response):
        title = response.xpath("//h1[contains(@class, 'margin-top-half-em')]/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = re.search('brandName = (.*?);', response.body)
        if brand:
            brand = brand.group(1).replace("\'", "")
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        return brand

    def _parse_image_url(self, response):
        image_url = response.xpath("//img[contains(@class, 'pure-img')]/@src").extract()
        return image_url[0].replace('Thumbnail', 'Detail') if image_url else None

    def _parse_description(self, response):
        description = response.xpath("//div[contains(@class, 'thin-gray-heading-line')]").extract()
        return self._clean_text(is_empty(description)) if description else None

    def _parse_sku(self, response):
        sku = response.xpath("//span[@class='num-crumb']/text()").extract()
        if sku:
            sku = sku[0].split('#')[-1].strip()
        return sku if sku else None

    def _parse_upc(self, response):
        upc = response.xpath("//span[@class='num-crumb']/text()").extract()
        if upc:
            upc = upc[-1].split(' ')[-1]
        return upc if upc else None

    def _parse_categories(self, response):
        categories = response.xpath("//div[contains(@class, 'breadcrumbs')]//a/text()").extract()
        return categories[1:] if categories else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _scrape_total_matches(self, response):
        return None

    def _scrape_product_links(self, response):
        items = response.xpath("//a[@id='search-sku-title']/@href").extract()
        search_term = response.meta['search_term']

        for item in items:
            prod_item = SiteProductItem()
            req = Request(
                url=urlparse.urljoin(response.url, item),
                meta={
                    'product': prod_item,
                    'search_term': search_term,
                    'remaining': self.quantity,
                },
                dont_filter=True,
                callback=self._parse_single_product
            )
            yield req, prod_item

    def _scrape_next_results_page_link(self, response):
        items = response.xpath("//a[@id='search-sku-title']/@href").extract()
        if not items:
            return
        self.current_page += 1
        st = response.meta.get('search_term')

        next_page_link = self.SEARCH_URL.format(search_term=urllib.quote_plus(st.encode('utf-8')), page_num=self.current_page)
        if next_page_link:
            return next_page_link

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()