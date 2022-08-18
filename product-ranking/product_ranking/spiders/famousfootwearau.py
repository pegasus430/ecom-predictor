from __future__ import division, absolute_import, unicode_literals

import urlparse

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider
from product_ranking.spiders import cond_set, cond_set_value
from scrapy.log import DEBUG
import re


class FamousfootwearauProductsSpider(BaseProductsSpider):
    name = 'famousfootwearau_products'
    allowed_domains = ["famousfootwear.com.au"]
    start_urls = []

    SEARCH_URL = "http://www.famousfootwear.com.au/Search.aspx?q={search_term}"

    DEFAULT_CURRENCY = u'AUD'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)
        product = response.meta['product']
        cond_set(product,
                 'brand',
                 response.xpath("//div[@class='prod_minfo']"
                                "/div[@class='prod_brand']"
                                "/text()").extract())

        cond_set(product, 'title', response.xpath(
            "//meta[@property='og:title']/@content").extract())
        cond_set(product, 'title', response.xpath(
            "//div[@id='brand']/following::h1/text()").extract())

        price_values = response.xpath("//div[@class='prod_minfo']"
                                      "/div[@class='prod_price']"
                                      "/span/span[@class='sale']"
                                      "/text()").re('[\d.]+')
        if not price_values:
            price_values = response.xpath("//div[@class='prod_minfo']"
                                          "/div[@class='prod_price']"
                                          "/text()").re('[\d.]+')
        if price_values:
            price = u''.join(price_values)

            cond_set_value(product,
                           'price',
                           Price(
                               priceCurrency=self.DEFAULT_CURRENCY,
                               price=price))

        cond_set(
            product, 'image_url', response.xpath("(//div[@id='prod_slider']"
                                                 "/div/div"
                                                 "/a[@class='MagicZoom']"
                                                 "/@href)[1]").extract(),
            conv=full_url)

        cond_set(product, 'description', response.xpath(
            "//meta[@name='description']/@content").extract())
        cond_set(product, 'upc', response.xpath(
            "//input[@id='hidId']/@value").extract())
        cond_set_value(product, 'locale', "en-US")

        reseller_id_regex = "\/([A-Z\.]{3,})"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        rels = response.xpath("//ul[@class='like_list row']/li/a")
        related = []
        for r in rels:
            href = r.xpath("@href").extract()
            if href:
                href = href[0]
                name = r.xpath("img/@alt").extract()
                if name:
                    name = name[0]
                    related.append(RelatedProduct(name, full_url(href)))
        if related:
            product['related_products'] = {'recommended': related}
        return product

    def _scrape_total_matches(self, response):
        total = response.xpath(
            "//div[@id='panResults']/p/b/text()").extract()
        if len(total) > 1:
            try:
                return int(total[1])
            except ValueError:
                return 0
        else:
            return 0

    def _scrape_product_links(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)
        links = response.xpath("//div[@class='productGrid']"
                               "//li/a[@class='modal_link']"
                               "/@href").extract()
        if not links:
            self.log("Found no product links.", DEBUG)
            return
        for link in links:
            yield full_url(link), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)
        next_page_links = response.xpath(
            "//div[@class='pagination']/ul/li"
            "/a[contains(text(),'Next')]/@href").extract()
        if next_page_links:
            return full_url(next_page_links[0])
