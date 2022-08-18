from __future__ import division, absolute_import, unicode_literals

import string
import urlparse

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, cond_set_value
from scrapy.log import WARNING
import re


class KruidvatProductsSpider(BaseProductsSpider):
    name = 'kruidvat_products'
    allowed_domains = ["kruidvat.nl"]
    start_urls = []
    SEARCH_URL = "http://www.kruidvat.nl/search?text={search_term}"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        def full_url(url):
            return urlparse.urljoin(response.url, url)

        cond_set(
            product,
            'title',
            response.xpath(
                "//section[@class='product-details']"
                "/div[@id='product-title']/h1/text()").extract(),
            conv=string.strip,
        )

        cond_set(
            product,
            'image_url',
            response.xpath(
                "//section[contains(@class,'product-imgviewer')]"
                "/div/img/@src").extract(),
            conv=full_url
        )

        cond_set(
            product,
            'price',
            response.xpath(
                "//p[@class='product-price']"
                "/meta[@itemprop='price']/@content").extract()
        )
        if product.get('price', None):
            product['price'] = Price(
                price=product['price'].replace(',', '.').replace(
                    '$', '').strip(),
                priceCurrency='EUR'
            )

        upc = response.xpath(
                "//section[@class='product-details']"
                "/meta[@itemprop='productID']/@content").extract()

        if upc and isinstance(upc[0], int):
            cond_set(
                product,
                'upc',
                response.xpath(
                    "//section[@class='product-details']"
                    "/meta[@itemprop='productID']/@content").extract(),
                conv=int,
            )

        cond_set(
            product,
            'description',
            response.xpath(
                "//section[@class='product-details']/p/text()").extract()
        )

        cond_set(
            product,
            'locale',
            response.xpath("//html/@lang").extract(),
        )

        cond_set(
            product,
            'brand',
            response.xpath("//var[@itemprop='brand']/text()").extract(),
        )

        reseller_id_regex = "p/(\d+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        res = response.xpath(
            "//div[contains(@class,'component') "
            "and contains(@class,'grid-unit-beta') ][1]/*/*/div/article")
        prodlist = []
        for r in res:
            try:
                title = r.xpath(
                    "div/p[@class='product-info']/a/text()").extract()[0]
                href = r.xpath(
                    "div/p[@class='product-info']/a/@href").extract()[0]
                prodlist.append(RelatedProduct(title, full_url(href)))
            except IndexError:
                pass

        if prodlist:
            product['related_products'] = {"recommended": prodlist}

        return product

    def _scrape_total_matches(self, response):
        total = response.xpath(
            "//section[contains(@class,'search-title')]"
            "/p/span/text()").extract()
        if total:
            total = total[0].replace(".", "")
            try:
                return int(total)
            except ValueError:
                return 0
        else:
            return 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//section[contains(@class,'search-result')]"
            "/article[@class='product-cell']"
            "/div/a[@class='product-link']/@href").extract()

        if not links:
            self.log("Found no product links.", WARNING)

        for no, link in enumerate(links):
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next = response.xpath(
            "//ul[@class='pages']/li[@class='next-page']/a/@href")
        if next:
            return next.extract()[0]
