from __future__ import division, absolute_import, unicode_literals

import re
import urlparse

from scrapy import Request
from scrapy.conf import settings
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value,\
    FormatterWithDefaults
from spiders_shared_code.bedbathandbeyond_variants import BedBathAndBeyondVariants


class BedBathAndBeyondCaProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'bedbathbeyondca_products'
    allowed_domains = ["www.bedbathandbeyond.ca"]

    SEARCH_URL = "https://www.bedbathandbeyond.ca/store/s/{search_term}?origSearchTerm={search_term}"

    REVIEW_URL = "https://bedbathbeyondca.ugc.bazaarvoice.com/0851-en_ca" \
                 "/{product_id}/reviews.djs?format=embeddedhtml"

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi()
        super(BedBathAndBeyondCaProductsSpider, self).__init__(*args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

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

        description = self._parse_description(response)
        product['description'] = description

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        cond_set_value(product, 'department', category)

        variants = self._parse_variants(response)
        product['variants'] = variants

        product_id = response.xpath("//input[contains(@name, 'productId')]/@value").extract()
        if product_id:
            return Request(
                url=self.REVIEW_URL.format(product_id=int(product_id[0])),
                callback=self.br.parse_buyer_reviews,
                meta={"product": product},
                dont_filter=True,
            )

        return product

    def _parse_title(self, response):
        product_name = response.xpath("//h1[@id='productTitle']/text()").extract()
        return product_name[0].strip() if product_name else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath(
            "//div[@itemprop='brand']"
            "//span[@itemprop='name']/text()").extract()
        if brand:
            brand = brand[0]
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        return brand

    def _parse_categories(self, response):
        categories_list = response.xpath(
            "//div[contains(@class, 'breadcrumbs')]"
            "//a[contains(@href,'category')]/text()"
        ).extract()
        categories = map(self._clean_text, categories_list)
        return categories if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_description(self, response):
        description = response.xpath("//div[@itemprop='description']/text()").extract()
        return self._clean_text(description[0]) if description else None

    def _parse_image_url(self, response):
        image = response.xpath(
            "//a[@id='mainProductImgZoom']/@data-zoomhref|"
            "//div[@id='s7ProductImageWrapper']//img/@src"
        ).extract()

        if image:
            image_url = 'https:' + image[0]
            return image_url

        return None

    def _parse_price(self, response):
        product = response.meta['product']
        reg_price = response.xpath("//span[@itemprop='price']/@content")
        low_price = response.xpath("//span[@itemprop='lowPrice']/@content")
        price = reg_price or low_price
        price = price.re('\d+\.?\d*')
        if price:
            cond_set_value(product, 'price',
                           Price(price=price[0].replace(',', ''),
                                 priceCurrency='CAD'))

    def _parse_out_of_stock(self, response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    def _parse_variants(self, response):
        self.bed_ca = BedBathAndBeyondVariants()
        self.bed_ca.setupSC(response)
        return self.bed_ca._variants()

    def _scrape_total_matches(self, response):
        total_matches = response.xpath(
            "//li[contains(@class, 'listCount')]"
            "//span/text()").extract()
        if total_matches:
            total_matches = re.search('\d+', total_matches[0])

        return int(total_matches.group()) if total_matches else 0

    def _scrape_product_links(self, response):
        self.product_links = response.xpath(
            "//div[contains(@class, 'prodGridRow')]"
            "//a[contains(@class, 'prodImg')]/@href").extract()

        for item_url in self.product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_link = response.xpath("//*[@class='listPageNumbers']/ul/li[@class='active']/following-sibling::li[1]/a/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()