from __future__ import division, absolute_import, unicode_literals

import re
import urlparse

from product_ranking.items import SiteProductItem, RelatedProduct, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set, cond_set_value
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words


class WestelmProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'westelm_products'
    allowed_domains = ["www.westelm.com"]
    start_urls = []

    SEARCH_URL = "http://www.westelm.com/search/results.html?words={search_term}"  # TODO: ordering

    handle_httpstatus_list = [404]

    use_proxies = False

    def __init__(self, *args, **kwargs):

        super(WestelmProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta.get('product', SiteProductItem())

        # Parse locate
        locale = 'en_US'
        cond_set_value(product, 'locale', locale)

        # Parse title
        title = self.parse_title(response)
        product['title'] = title

        # Parse image
        image = self.parse_image(response)
        cond_set_value(product, 'image_url', image)

        # Parse brand
        cond_set_value(product, 'brand', self.parse_brand(response))

        # Parse description
        description = self.parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse price
        price = self._parse_price(response)
        product['price'] = price

        if product.get('price', None):
            if not '$' in product['price']:
                self.log('Unknown currency at' % response.url)
            else:
                product['price'] = Price(
                    price=product['price'].replace(',', '').replace(
                        '$', '').strip(),
                    priceCurrency='USD'
                )

        # Parse price_range
        price_range = self._parse_price_range(response)
        product['price_range'] = price_range

        # Parse categories
        categories = self.parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self.parse_category(response)
        cond_set_value(product, 'category', category)

        return product

    def _parse_price(self, response):
        price = ''
        standard_price = response.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[@class='price-state price-standard']"
            "//span[@class='price-amount']"
            "/text()").extract()
        special_price = response.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[@class='price-state price-special']"
            "//span[@class='price-amount']"
            "/text()").extract()
        sale_price = response.xpath(
            "//div[contains(@class, 'pip-summary')]"
            "//span[@class='price-state price-sale']"
            "//span[@class='price-amount']"
            "/text()").extract()
        ajax_price = re.search(r'min :(.*)', response.body)
        if ajax_price:
            ajax_price = ajax_price.group(1).strip()

        if standard_price:
            price = standard_price[0]
        elif special_price:
            price = special_price[0]
        elif sale_price:
            price = sale_price[0]
        elif ajax_price:
            price = ajax_price

        if price:
            if not '$' in price:
                price = '$' + price

        return price

    def _parse_price_range(self, response):
        try:
            min_price = re.search(r'min :(.*?),', response.body, re.DOTALL).group(1).strip()
            min_price = '$' + min_price
            max_price = re.search(r'max :(.*?)}', response.body, re.DOTALL).group(1).strip()
            max_price = '$' + max_price
            price_range = min_price + '-' + max_price

        except:
            price_range = None

        return price_range

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs

        return req.replace(meta=new_meta)

    def parse_title(self, response):
        title = response.xpath("//div[contains(@class, 'pip-summary')]//h1[@itemprop='name']/text()").extract()
        if title:
            title = ''.join(title)
        return title

    def parse_image(self, response):
        image_url = response.xpath("//div[contains(@class, 'hero-image')]//a/img/@src").extract()
        if image_url:
            image_url = ''.join(image_url).replace('c.jpg', 'l.jpg')
            return image_url
        return None

    def parse_description(self, response):
        description = response.xpath(
            "//dd[@id='tab0']"
            "//div[contains(@class, 'accordion-contents')]"
            "//div[@class='accordion-tab-copy']").extract()
        if description:
            description = ''.join(description).replace('\n', '').strip()
            return description
        return None

    def parse_categories(self, response):
        categories = response.xpath(
            "//ul[@id='breadcrumb-list']"
            "//li//a//span[@itemprop='name']/text()").extract()

        return categories[1:] if categories else None

    def parse_category(self, response):
        categories = self.parse_categories(response)

        return categories[-1] if categories else None

    def parse_brand(self, response):
        brand = re.search(r'brand\s*:\s*"([^"]+)"', response.body)

        if brand:
            return brand.group(1)

        title = self.parse_title(response)

        if title:
            brand = guess_brand_from_first_words(title)

            if brand:
                return brand

        return None

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class, 'product-thumb')]"
            "//a/@href").extract()
        links = list(set(links))
        for link in links:
            yield link, SiteProductItem()

    def _scrape_total_matches(self, response):
        total_link = response.xpath("//li[contains(@id, 'products')]//span").extract()
        if total_link:
            totals = re.findall(r"\d+", ''.join(total_link))[0]
            if totals:
                return int(totals)
        return

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath("//li[contains(@class, 'next-page')]//a/@href").extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])