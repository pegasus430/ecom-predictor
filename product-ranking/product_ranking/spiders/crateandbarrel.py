import json
import string
import urlparse

from scrapy import Request

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (FLOATING_POINT_RGEX, BaseProductsSpider,
                                     cond_set_value)


class CrateandbarrelProductsSpider(BaseProductsSpider):

    SEARCH_URL = "http://www.crateandbarrel.com/search?query={search_term}"

    BUYER_REVIEW_URL = 'http://api.bazaarvoice.com/data/batch.json' \
                       '?passkey=ikuyof7cllxe0ctfrkp7ow23y' \
                       '&apiversion=5.5' \
                       '&displaycode=7258-en_us' \
                       '&resource.q0=products' \
                       '&filter.q0=id%3Aeq%3A{prod_id}' \
                       '&stats.q0=reviews' \
                       '&filteredstats.q0=reviews' \
                       '&filter_reviews.q0=contentlocale%3Aeq%3Aen_US' \
                       '&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen_US'

    name = "crateandbarrel_products"
    allowed_domains = ["crateandbarrel.com"]

    def __init__(self, *args, **kwargs):
        super(CrateandbarrelProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)
        self.br = BuyerReviewsBazaarApi(called_class=self)

    @staticmethod
    def _scrape_product_links(response):
        item_urls = response.xpath(
            '//a[@class="product-miniset-title"]/@href').extract()
        for item_url in item_urls:
            yield item_url, SiteProductItem()

    @staticmethod
    def _scrape_total_matches(response):
        total_matches = response.xpath('//div[@id="_productMatch"]/text()').re(r'\d+')
        return int(total_matches[0]) if total_matches else None

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        reqs = []
        product = response.meta.get('product')
        response.meta['product_response'] = response
        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse is_out_of_stock
        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        # Parse image_url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse categories_full_info
        categories_full_info = self._parse_categories_full_info(response)
        cond_set_value(product, 'categories_full_info', categories_full_info)

        # Parse categories
        categories = self._parse_categories(categories_full_info)
        cond_set_value(product, 'categories', categories)

        # Parse category
        category = self._parse_category(categories)
        cond_set_value(product, 'category', category)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description,
                       lambda x: " ".join([desc.strip() for desc in x]).strip())

        # Extract prod_id
        prod_id = self._extract_prod_id(response)

        # Parse buyer_reviews
        if prod_id:
            reqs.append(Request(self.BUYER_REVIEW_URL.format(prod_id=prod_id),
                                dont_filter=True,
                                meta=response.meta,
                                callback=self._parse_buyer_reviews))
            return self.send_next_request(reqs, response)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1[@id="productNameHeader"]/text()').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//span[@class="jsSwatchSku"]/text()').extract()
        return sku[0] if sku else None

    @staticmethod
    def _parse_price(response):
        price = response.xpath(
            '//meta[@property="og:price:amount"]/@content'
        ).re(FLOATING_POINT_RGEX)
        currency = response.xpath(
            '//meta[@property="og:price:currency"]/@content'
        ).extract()
        if currency and price:
            return Price(price=price[0], priceCurrency=currency[0])

    @staticmethod
    def _parse_is_out_of_stock(response):
        is_out_of_stock = response.xpath(
            '//meta[@property="og:availability" and @content="InStock"]'
        ).extract()
        return not bool(is_out_of_stock)

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//meta[@property="og:image"]/@content').extract()
        return image_url[0] if image_url else None

    @staticmethod
    def _parse_categories_full_info(response):
        categories_full_info = []
        list_ = response.xpath('//div[@id="SiteMapPath"]//a')
        for level in list_:
            name = level.xpath('text()').extract()
            url = level.xpath('@href').extract()
            if name and url:
                url = urlparse.urljoin(response.url, url[0])
                category = {'name': name[0], 'url': url}
                categories_full_info.append(category)
        return categories_full_info

    @staticmethod
    def _parse_categories(categories_full_info):
        return [category.get('name') for category in categories_full_info]

    @staticmethod
    def _parse_category(categories):
        return categories[-1] if categories else None

    @staticmethod
    def _parse_description(response):
        description = response.xpath(
            '//div[@class="tab hwDetails hwDetailsTab" or '
            '@class="tab hwOverview hwDetailsTab"]/div[@class="content hwDetailsP"]/node()'
        ).extract()
        return description

    @staticmethod
    def _extract_prod_id(response):
        prod_id = response.xpath(
            '//script[contains(text(), "Crate.Reviews.init")]/text()'
        ).re(r'Crate\.Reviews\.init\(\'([\w\d]+)\'')
        return prod_id[0] if prod_id else None

    @staticmethod
    def _parse_brand(buyer_reviews_data):
        return buyer_reviews_data.get(
                'Results', {})[0].get('Brand', {}).get('Name')

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        try:
            raw_json = json.loads(response.body_as_unicode())
            buyer_reviews_data = raw_json.get(
                'BatchedResults', {}).get('q0', {})

            # Parse brand
            product['brand'] = self._parse_brand(buyer_reviews_data)

            # Parse buyer_reviews
            # TODO: update BuyerReviewsBazaarApi class, because below line not so obvious
            response = response.replace(body=json.dumps(buyer_reviews_data))
            buyer_reviews = BuyerReviews(**self.br.parse_buyer_reviews_products_json(response))
            product['buyer_reviews'] = buyer_reviews

        except Exception as e:
            self.log(e)
        return product

    @staticmethod
    def send_next_request(reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)
