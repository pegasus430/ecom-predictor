from __future__ import division, absolute_import, unicode_literals

import re
import json
import urlparse

from lxml import html
import traceback

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.utils import is_empty


class PotterybarnProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'potterybarn_products'
    allowed_domains = ["www.potterybarn.com"]
    SEARCH_URL = "http://www.potterybarn.com/search/results.html?words={search_term}"
    product_filter = []

    def __init__(self, *args, **kwargs):
        # All this is to set the site_name since we have several
        # allowed_domains.
        super(PotterybarnProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

        self.current_page = 1

    def _parse_single_product(self, response):
        return self.parse_product(response)

    @staticmethod
    def _parse_no_longer_available(response):
        message = response.xpath(
            '//div[@class="error" and '
            'contains(., "The product you are trying to view is not currently available.")]')
        return bool(message)

    def _extract_product_json(self):

        try:
            product_json_text = re.search('({"attributes":.*?});', html.tostring(self.tree_html), re.DOTALL).group(1)
            product_json = json.loads(product_json_text)
        except:
            product_json = None

        return product_json

    def parse_product(self, response):
        product = response.meta['product']

        if self._parse_no_longer_available(response):
            product['no_longer_available'] = True
            return product
        else:
            product['no_longer_available'] = False

        cond_set(
            product,
            'title',
            response.xpath("//meta[@property='og:title']/@content").extract())

        if not product.get('brand', None):
            brand = guess_brand_from_first_words(product.get('title').strip() if product.get('title') else '')
            if brand:
                product['brand'] = brand
            else:
                product['brand'] = product.get('title').strip().split()[0]

        image_url = self._parse_images(response)
        cond_set(product, 'image_url', image_url)

        desc = self._parse_description(response)
        product['description'] = desc

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        if categories:
            cond_set_value(product, 'department', categories[-1])

        product['locale'] = "en-US"

        self._parse_related_products(response)
        self._parse_price(response)

        return product

    def _parse_images(self, response):
        image_url_list = []
        image_urls = response.xpath(
            "//div[contains(@class, 'hero-image')]/a/img/@src").extract()
        if image_urls:
            for image_url in image_urls:
                image_url = image_url.replace('c.jpg', 'l.jpg')
                image_url_list.append(image_url)

        return image_url_list

    def _parse_categories(self, response):
        categories = response.xpath(
            "//ul[@class='breadcrumb-list']"
            "//span[@itemprop='name']/text()").extract()
        return categories[1:] if categories else None

    @staticmethod
    def _parse_description(response):
        desc = response.xpath("//dd[contains(@id, 'tab0')]"
                              "//div[contains(@class, 'accordion-contents')]//ul/li/text()").extract()
        desc = [i.strip() for i in desc]
        return "".join(desc)

    def _parse_price(self, response):
        product = response.meta['product']

        price_sale = response.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[contains(@class, 'price-state price-sale')]"
            "//span[contains(@class, 'price-amount')]/text()")
        price_special = response.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[contains(@class, 'price-state price-special')]"
            "//span[contains(@class, 'price-amount')]/text()")
        price_standard = response.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[contains(@class, 'price-state price-standard')]"
            "//span[contains(@class, 'price-amount')]/text()")

        if price_sale:
            final_price = price_sale[0]
        elif price_special:
            final_price = price_special[0]
        elif price_standard:
            final_price = price_standard[0]
        else:
            final_price = None

        if final_price:
            final_price = '$' + final_price.extract()
        final_price = final_price if final_price else None
        product['price'] = final_price

        if product.get('price', None):
            if not '$' in product['price']:
                self.log('Unknown currency at' % response.url)
            else:
                product['price'] = Price(
                    price=product['price'].replace(',', '').replace(
                        '$', '').strip(),
                    priceCurrency='USD'
                )
        else:
            # search price in JS code
            match = re.search(r'selling\s*:\s*\{[^}]*min\s*:\s*(\d+)[^}]*\}', response.body)
            if match:
                product['price'] = Price('USD', match.group(1))

    def _parse_related_products(self, response):
        product = response.meta['product']
        related_pods = []
        related_title = []
        related_url = []
        title_items = response.xpath("//div[contains(@id, 'br-more-products-widget')]"
                                     "//div[contains(@class, 'br-more-widget')]"
                                     "/a[2]/text()")
        if title_items:
            for title_item in title_items:
                related_title.append(title_item.extract().strip())

        targetItems = response.xpath("//div[contains(@id, 'br-more-products-widget')]"
                                     "//div[contains(@class, 'br-more-widget')]"
                                     "/a[2]/@href")
        if targetItems:
            for targetItem in targetItems:
                related_url.append(targetItem.extract())

        if related_url and related_title:
            related_pods.append(
                RelatedProduct(
                    title=related_title,
                    url=related_url
                )
            )
        related_pods = related_pods if related_pods else None
        product['related_products'] = related_pods

    def _scrape_product_links(self, response):
        product_links = response.xpath('//div[contains(@class, "product-thumb")]'
                                       '/div[contains(@class, "product-cell")]/a/@href').extract()

        for link in product_links:
            yield link, SiteProductItem()

    def _scrape_total_matches(self, response):
        try:
            totals = is_empty(response.xpath('//li[@id="products"]/span/text()').re('(\d+)'), '0')
            return int(totals)
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))
            return 0

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(
            '//div[contains(@class,"pagination-container")]'
            '//ul[@class="pagination"]'
            '//li[contains(@class, "pagination-next")]'
            '//a/@href').extract()

        if next_page:
            return urlparse.urljoin(response.url, next_page[0])
