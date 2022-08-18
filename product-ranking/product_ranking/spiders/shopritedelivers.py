"""This is a shopritedelivers.com base module"""
# -*- coding: utf-8 -*-
import string
import urlparse
from collections import namedtuple
from product_ranking.spiders import (BaseProductsSpider, SiteProductItem, cond_set_value,
                                     FLOATING_POINT_RGEX)
from product_ranking.items import Price


class ShopritedeliversProductsSpider(BaseProductsSpider):
    """This is a shopritedelivers.com base class"""
    name = "shopritedelivers_products"
    allowed_domains = ["shopritedelivers.com"]
    SEARCH_URL = ("http://www.shopritedelivers.com/Search.aspx?s=Name ASC&ps=48&k={search_term}")

    def __init__(self, *args, **kwargs):
        """Initiate input variables and etc."""
        super(ShopritedeliversProductsSpider, self).__init__(*args, **kwargs)
        self.use_proxies = True

    @staticmethod
    def _scrape_total_matches(response):
        """Scrapes the total number of matches of the search term."""
        total_matches = response.xpath(
            '//span[contains(@id, "PageContent_ResultIndexMessage")]/text()'
        ).re(r'(\d+) results$')
        return int(total_matches[0]) if total_matches else None

    @staticmethod
    def _scrape_product_links(response):
        """
        Returns the products in the current results page and a SiteProductItem
        which may be partially initialized.
        """
        product_links_raw = response.xpath(
            '//*[@class="itemContainer"]//a[contains(@id, "_ProductName")]/@href'
        ).extract()
        urljoin = lambda x: urlparse.urljoin(response.url, x)
        links = [urljoin(link) for link in product_links_raw]
        for item_url in links:
            yield item_url, SiteProductItem()

    @staticmethod
    def _scrape_next_results_page_link(response):
        """
        Scrapes the URL for the next results page.
        It should return None if no next page is available.
        """
        link = response.xpath(
            '//a[@class="current"]/following-sibling::a/@href').extract()
        urljoin = lambda x: urlparse.urljoin(response.url, x)
        return urljoin(link[0]) if link else None

    @staticmethod
    def _scrape_results_per_page(response):
        """
        Scrapes the number of products at the first page
        It should return None if the value is unavailable
        """
        results_per_page = response.xpath(
            '//span[contains(@id, "PageContent_ResultIndexMessage")]/text()'
        ).re(r'(\d+) of \d+ results$')
        return int(results_per_page[0]) if results_per_page else None

    @staticmethod
    def _parse_title(response):
        """Parse title"""
        title = response.xpath('//*[@itemprop="name"]//text()').extract()
        return " ".join(title)

    @staticmethod
    def _parse_categories_full_info(categories_names, categories_links):
        """Parse categories full info"""
        category_tuple = namedtuple('category', ['name', 'url'])
        categories_tuple = zip(categories_names, categories_links)
        return [dict(category_tuple._make(category)._asdict())
                for category in categories_tuple]

    @staticmethod
    def _parse_categories_links(response):
        """Parse categories links, except first one"""
        categories_links_raw = response.xpath(
            '//*[@class="breadCrumbs categoryBreadCrumbs"]//a/@href'
        ).extract()[1:]
        urljoin = lambda x: urlparse.urljoin(response.url, x)
        categories_links = [urljoin(category_link)
                            for category_link in categories_links_raw]
        return categories_links

    @staticmethod
    def _parse_categories(response):
        """Parse categories names, except first one"""
        categories_names = response.xpath(
            '//*[@class="breadCrumbs categoryBreadCrumbs"]//a/text()'
        ).extract()[1:]
        return categories_names

    @staticmethod
    def _parse_category(categories):
        """Parse last category"""
        return categories[-1] if categories else None

    @staticmethod
    def _parse_sku(response):
        """Parse sku"""
        sku = response.xpath('//*[@itemprop="sku"]/text()').extract()
        return sku[0] if sku else None

    @staticmethod
    def _parse_price(response):
        """Parse price"""
        currency = response.xpath('*//*[@itemprop="priceCurrency"]/@content').extract()
        price = response.xpath('*//*[@itemprop="price"]/text()').re(FLOATING_POINT_RGEX)
        if currency and price:
            return Price(price=price[0], priceCurrency=currency[0])
        else:
            return Price(price=0, priceCurrency='USD')

    @staticmethod
    def _parse_image_url(response):
        """Parse image url"""
        image_url = response.xpath(
            '//*[@id="ProductImageUrl"]/@href').extract()
        return urlparse.urljoin(response.url, image_url[0]) if image_url else None

    @staticmethod
    def _parse_brand(response):
        """Parse brand"""
        brand = response.xpath('//*[@itemprop="manufacturer"]/text()').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_description(response):
        """Parse description"""
        description = response.xpath('//*[@itemprop="description"]/node()').extract()
        return "".join(description)

    def parse_product(self, response):
        """Handles parsing of a product page"""
        product = response.meta['product']
        # Set locale
        product['locale'] = 'en_US'

        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._parse_category(categories)
        cond_set_value(product, 'category', category)

        categories_links = self._parse_categories_links(response)
        categories_full_info = self._parse_categories_full_info(categories, categories_links)
        cond_set_value(product, 'categories_full_info', categories_full_info)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        cond_set_value(product, 'reseller_id', sku)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        return product

    def _parse_single_product(self, response):
        """Same to parse_product"""
        return self.parse_product(response)
