from __future__ import division, absolute_import, unicode_literals

import re

import urlparse
from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.guess_brand import guess_brand_from_first_words


class PlusnlProductsSpider(BaseProductsSpider):
    name = 'plusnl_products'
    allowed_domains = ["www.plus.nl"]

    SEARCH_URL = "https://www.plus.nl/zoekresultaten?SearchTerm={search_term}"
    NEXT_PAGE_URL = "https://www.plus.nl/INTERSHOP/web/WFS/PLUS-website-Site/nl_NL/-/EUR/" \
                    "ViewParametricSearch-ProductPaging?PageNumber={page_num}&PageSize=12" \
                    "&SortingAttribute=&SearchTerm={search_term}&SearchParameter=%26%" \
                    "40QueryTerm%3Dappels%26ContextCategoryUUID%3DDxAKAxIVXAIAAAFJ1q9Y6j1x" \
                    "%26OnlineFlag%3D1&SelectedTabName=solrTabs1"

    current_page = 0

    def __init__(self, *args, **kwargs):
        super(PlusnlProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args, **kwargs)
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML," \
                          " like Gecko) Chrome/66.0.3359.170 Safari/537.36"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        self._parse_price(response)

        product['locale'] = "en-US"

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._parse_department(response)
        cond_set_value(product, 'department', department)

        promotions = self._parse_promotions(response)
        cond_set_value(product, 'promotions', promotions)

        price_per_volume = self._parse_price_per_volume(response)
        cond_set_value(product, 'price_per_volume', price_per_volume)

        volume_measure = self._parse_volume_measure(response)
        cond_set_value(product, 'volume_measure', volume_measure)

        reseller_id = self._parse_reseller_id(product.get("url"))
        cond_set_value(product, 'reseller_id', reseller_id)

        return product

    @staticmethod
    def _parse_reseller_id(url):
        if url:
            reseller_id = re.search(r"-(\d+)$", url)
            if reseller_id:
                return reseller_id.group(1)

    def _parse_title(self, response):
        title = response.xpath("//h1[@class='productTitle']/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//div[@id='prod-detail-ctnr']/@data-brand").extract()

        if brand:
            brand = brand[0]
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//ol[@class='ish-breadcrumbs-list']//li//a/text()").extract()
        return categories[1:] if categories else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_image_url(self, response):
        image = response.xpath("//div[contains(@class, 'kor-product-photo')]//img/@data-src").extract()
        return urlparse.urljoin(response.url, image[0]) if image else None

    def _parse_price(self, response):
        product = response.meta['product']
        price = response.xpath("//div[@id='prod-detail-ctnr']/@data-price").re('\d+\.?\d*')
        if price:
            cond_set_value(product, 'price',
                           Price(price=price[0].replace(',', ''),
                                 priceCurrency='EUR'))

    def _parse_out_of_stock(self, response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    def _parse_promotions(self, response):
        promotions = response.xpath("//div[contains(@class, 'promotion-marker')]")
        return bool(promotions)

    def _parse_price_per_volume(self, response):
        price_per_volume = response.xpath("//div[contains(@class, 'promotion-marker')]//div[@class='ppse-css']").re('\d+(?:\,.\d+)')
        return price_per_volume[0].replace(',', '.') if price_per_volume else None

    def _parse_volume_measure(self, response):
        volume_measure = response.xpath("//div[contains(@class, 'promotion-marker')]"
                                        "//div[@class='standaard-inhoud']/text()").re('\w+')
        return volume_measure[-1] if volume_measure else None

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//div[@class='total-items-found']/text()").extract()
        return int(total_match[0]) if total_match else None

    def _scrape_product_links(self, response):
        links = response.xpath("//li[contains(@class, 'ish-productList-item')]//a/@href").extract()
        for item_url in links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        st = response.meta.get('search_term')
        total_count = self._scrape_total_matches(response)
        self.current_page += 1

        if total_count and total_count < self.current_page * 12:
            return

        next_page_link = self.NEXT_PAGE_URL.format(page_num=self.current_page, search_term=st)
        return next_page_link