from __future__ import division, absolute_import, unicode_literals
import re
import string

from scrapy.log import WARNING
from scrapy.http import Request

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    cond_set_value, \
    cond_replace_value, cond_replace, FLOATING_POINT_RGEX

is_empty = lambda x, y=None: x[0] if x else y

class BolProductsSpider(BaseProductsSpider):
    name = 'bol_products'
    allowed_domains = ["bol.com"]
    start_urls = []
    SEARCH_URL = "http://www.bol.com/nl/s/algemeen/zoekresultaten/Ntt/" \
        "{search_term}/N/0/Nty/1/search/true/searchType/qck/sc/media_all/" \
        "index.html"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        cond_set(product, 'brand', response.xpath(
            "//div/span/a[@itemprop='brand']/text()").extract())

        cond_set(
            product,
            'title',
            response.xpath(
                "//div[contains(@class,'product_heading')]"
                "/h1[@itemprop='name']/text()"
            ).extract(),
            conv=string.strip)

        cond_set(
            product,
            'image_url',
            response.xpath(
                "//div[contains(@class,'product_zoom_wrapper')]"
                "/img[@itemprop='image']/@src"
            ).extract(),
            conv=string.strip,
        )

        j = response.xpath(
            "//div[contains(@class,'product_description')]/div"
            "/div[@class='content']/descendant::*[text()]/text()"
        )
        cond_set_value(product, 'description', "\n".join(
            x.strip() for x in j.extract() if x.strip()))

        cond_set(
            product,
            'upc',
            response.xpath("//meta[@itemprop='sku']/@content").extract(),
            conv=int,
        )

        reseller_id = re.findall('\/(\d+)\/', response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        cond_set(product, 'locale', response.xpath("//html/@lang").extract())

        rel = response.xpath(
            "//div[contains(@class,'tst_inview_box')]/div"
            "/div[@class='product_details_mini']/span/a")
        recommended_prods = []
        for r in rel:
            try:
                href = r.xpath('@href').extract()[0]
                title = r.xpath('@title').extract()[0]
                recommended_prods.append(RelatedProduct(title, href))
            except IndexError:
                pass
        if recommended_prods:
            product['related_products'] = {"recommended": recommended_prods}
        self._price_from_html(response, product)

        mkt_link = is_empty(response.xpath(
            "//div[contains(@class, 'alternative')]/a/@href").extract())
        meta = {"product": product}
        if mkt_link:
            mkt_link = re.sub("filter=([^\&]\w+)", "", mkt_link)
            return Request(
                url=mkt_link, 
                callback=self.parse_marketplace, 
                meta=meta
            )
        else:
            seller = response.xpath(
                '//p[@class="bottom_xs"]/strong/text()'
            ).extract()
            if not seller:
                seller = response.xpath(
                    '//div[@class="ratinglabel_text"]/a/text() |'
                    '//div[contains(@class, "seller_popup_wrapper")]/a/text()'
                ).extract()
            if seller:
                seller = seller[0].strip()
                product["marketplace"] = [{
                    "name": seller, 
                    "price": product["price"]
                }]

        return product

    def _price_from_html(self, response, product):
        css = '.product-price-bol [itemprop=price]::attr(content)'
        cond_replace(product, 'price', response.css(css).extract())
        cond_set(
            product,
            'price',
            response.xpath(
                "//span[@class='offer_price']/meta[@itemprop='price']/@content"
            ).extract())

        currency = response.css('[itemprop=priceCurrency]::attr(content)')
        currency = currency.extract()[0] if currency else 'EUR'
        price = product.get('price', '')
        price = price.replace(',', '.')
        if price and re.match(' *\d+\.?\d* *\Z', price):
            cond_replace_value(product, 'price', Price(currency, price))

    def _scrape_total_matches(self, response):
        totals = response.xpath(
            "//h1[@itemprop='name']/span[@id='sab_header_results_size']/text()"
        ).extract()
        if totals:
            total = totals[0].replace(".", "")
            try:
                total_matches = int(total)
            except ValueError:
                self.log(
                    "Failed to parse number of matches: %r" % total, WARNING)
                total_matches = None
        elif "Geen zoekresultaat" in response.body_as_unicode():
            total_matches = 0
        else:
            total_matches = None

        return total_matches

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class,'productlist_block')]"
            "/div[@class='product_details_thumb']"
            "/div/div/a[@class='product_name']/@href").extract()
        if not links:
            self.log("Found no product links.", WARNING)

        for no, link in enumerate(links):
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_links = response.xpath(
            "//div[contains(@class,'tst_searchresults_next')]/span/a/@href")
        if next_page_links:
            return next_page_links.extract()[0]

    def parse_marketplace(self, response):
        product = response.meta["product"]

        marketplaces = response.meta.get("marketplaces", [])

        for seller in response.xpath(
            "//tr[contains(@class, 'horizontal_row')]"):
            price =  is_empty(seller.xpath(
                "td/p[contains(@class, 'price')]/text() |" \
                "td/span[contains(@class, 'price')]/text()"
            ).re(FLOATING_POINT_RGEX))
            if price:
                price = price.replace(",", ".")

            name = is_empty(seller.xpath(
                "td/div/a/img/@title |" \
                "td/div[contains(@class, 'ratinglabel_text')]/a/text() |" \
                "td/img/@title"
            ).extract())

            if name and "verkoper:" in name: 
                name = is_empty(re.findall("verkoper\:\s+(.*)", name))
            if name:
                name = name.strip()

            marketplaces.append({
                "price": Price(price=price, priceCurrency="EUR"),
                "name": name
            })

        next_link = is_empty(response.xpath("//div[contains(@class, 'left_button')]/a/@href").extract())
        if next_link:
            meta = {"product": product, "marketplaces": marketplaces}
            return Request(
                url=next_link, 
                callback=self.parse_marketplace, 
                meta=meta
            )

        product["marketplace"] = marketplaces

        return product
