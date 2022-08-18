import re
import string
import json
import urlparse

from scrapy import Request
from scrapy.log import INFO, WARNING

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty


class AuchanProductsSpider(BaseProductsSpider):

    name = 'auchan_products'
    allowed_domains = ["auchan.fr"]

    SEARCH_URL = 'https://www.auchan.fr/recherche?text={search_term}'
    start_links = 'https://www.auchan.fr'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(AuchanProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def parse_product(self, response):
        reqs = []
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_GB'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        # Parse department
        department = self._parse_department(response)
        cond_set_value(product, 'department', department)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse special pricing
        special_pricing = self._parse_special_pricing(response)
        cond_set_value(product, 'special_pricing', special_pricing, conv=bool)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse stock status
        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse upc
        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse buyer reviews
        product_code = re.search(
            'bazaarvoice\.config\.productCode = "(.*)";', response.body)
        if product_code:
            review_URL = "https://api.bazaarvoice.com/data/batch.json?" \
                         "passkey=syzh21yn6lf39vjo00ndkig63&apiversion=5.5&" \
                         "displaycode=6073-fr_fr&" \
                         "resource.q0=products&" \
                         "filter.q0=id:eq:%s&" \
                         "stats.q0=reviews" % product_code.group(1)
            reqs.append(
                Request(
                    url=review_URL,
                    dont_filter=True,
                    callback=self.parse_buyer_reviews
                )
            )

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_title(self, response):
        title = is_empty(
            response.xpath(
                '//*[@itemprop="name"]/text()'
            ).extract()
        )
        return title

    def _parse_brand(self, response):
        has_brand = re.search(r'\["product_brand"\] = "(.+)";\n', response.body)
        return has_brand.group(1) if has_brand else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        if categories:
            return categories[-1]

    def _parse_categories(self, response):
        categories = response.xpath(
            '//*[@itemtype="http://schema.org/BreadcrumbList"]'
            '//*[@itemprop="itemListElement"]/*/text()'
        ).extract()
        return [category.strip() for category in categories]

    def _parse_price(self, response):
        price = is_empty(response.xpath('//meta[@itemprop="price"]/@content').extract(), 0.00)
        return Price(price=float(price), priceCurrency='EUR')

    def _parse_special_pricing(self, response):
        special_price = is_empty(response.xpath(
            '//*[contains(@class, "product-price--oldPrice")]'
        ).extract(), False)

        return special_price

    def _parse_image_url(self, response):
        image_url = is_empty(
            response.xpath(
                '//*[@itemprop="image"]/@content'
            ).extract()
        )

        return image_url

    def _parse_description(self, response):
        description = is_empty(
            response.xpath(
                '//section[@id="tabDescription"]/main'
            ).extract()
        )
        return description

    def _parse_stock_status(self, response):
        in_stock = re.search(r'\["product_instock"\] = "(.+)";\n', response.body)
        if in_stock and in_stock.group(1) == 'Y':
            return False
        return True

    def _parse_upc(self, response):
        has_upc = re.search(r'\["product_ean"\] = "(.+)";\n', response.body)
        return has_upc.group(1) if has_upc else None

    def _parse_sku(self, response):
        has_sku = re.search(r'\["product_id"\] = "(.+)";\n', response.body)
        return has_sku.group(1) if has_sku else None

    def parse_buyer_reviews(self, response):
        product = response.meta['product']
        try:
            raw_json = json.loads(response.body_as_unicode())
        except Exception as e:
            self.log('Invalid reviews: {}'.format(str(e)), WARNING)
            return product
        buyer_reviews_data = raw_json.get('BatchedResults', {}).get('q0', {})
        response = response.replace(body=json.dumps(buyer_reviews_data))
        buyer_reviews = BuyerReviews(
            **self.br.parse_buyer_reviews_products_json(response))
        product['buyer_reviews'] = buyer_reviews

        return product

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        total_matches = is_empty(
            response.xpath(
                '//*[@class="ui-breadcrumb--quantity"]/text()'
            ).re(r'\d+'), '0'
        )

        return int(total_matches)

    def _scrape_results_per_page(self, response):
        """
        Number of results on page
        """
        items = response.xpath(
            '//div[@class="product-item--wrapper"]'
        )
        return len(items)

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        items = response.xpath(
            '//div[@class="product-item--wrapper"]'
        )

        if items:
            for item in items:
                link = is_empty(
                    item.xpath('a/@href').extract()
                )
                link = urlparse.urljoin(self.start_links, link)
                res_item = SiteProductItem()
                yield link, res_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        url = is_empty(
            response.xpath(
               '//a[@class="ui-pagination--next"]/@href'
           ).extract()
        )
        if not url:
            self.log("Found no 'next page' links", WARNING)
            return None
        return urlparse.urljoin(self.start_links, url)
