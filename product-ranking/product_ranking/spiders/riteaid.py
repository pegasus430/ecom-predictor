import json
import re
import string

from scrapy import Request
from scrapy.conf import settings
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import cond_set_value
from product_ranking.spiders.contrib.product_spider import ProductsSpider


class RiteAidProductsSpider(ProductsSpider):
    name = 'riteaid_products'

    allowed_domains = ['riteaid.com']

    SEARCH_URL = "https://www.riteaid.com/shop/catalogsearch/result/?q={search_term}"

    _REVIEWS_URL='http://api.bazaarvoice.com/data/reviews.json?apiversion=5.5&passkey=tezax0lg4cxakub5hhurfey5o&' \
                 'Filter=ProductId:{sku}&Include=Products&Stats=Reviews'

    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(RiteAidProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3325.181 Safari/537.36"
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _total_matches_from_html(self, response):
        total = response.xpath(
            '(//*[@class="pager"]//*[@class="amount"]'
            '/text())[1]').re('of (\d+)')

        if not total:
            total = response.xpath('(//*[@class="pager"]//*[@class="amount"]/text())[1]').re('(\d+)\sItem')

        return int(total[0]) if total else 0

    def _scrape_results_per_page(self, response):
        results_per_page = response.xpath(
            '//*[@class="limiter"]//option[@selected]/text()').re('\d+')
        return int(results_per_page[0]) if results_per_page else 0

    def _scrape_next_results_page_link(self, response):
        link = response.xpath('//a[@title="Next"]/@href').extract()
        return link[0] if link else None

    def _scrape_product_links(self, response):
        item_urls = response.xpath(
            '//*[@class="product-name"]/a/@href').extract()
        for item_url in item_urls:
            yield item_url, SiteProductItem()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _parse_title(self, response):
        title = response.xpath('//*[@itemprop="name"]/text()').extract()
        return title[0] if title else None

    def _parse_category(self, response):
        categories = response.xpath(
            '(//a[@property="v:title"]/text())[position()>1]').extract()
        return categories[-1] if categories else None

    def _parse_price(self, response):
        price = response.xpath('//*[@itemprop="price"]/text()').re('[\d\.]+')
        currency = response.xpath(
            '//*[@itemprop="priceCurrency"]/@content').re('\w{2,3}') or ['USD']

        if not price:
            return None

        return Price(price=price[0], priceCurrency=currency[0])

    def _parse_image_url(self, response):
        image_url = response.xpath('//*[@itemprop="image"]/@src').extract()
        return image_url[0] if image_url else None

    def _parse_variants(self, response):
        return None

    def _parse_is_out_of_stock(self, response):
        status = response.xpath(
            '//*[@itemprop="availability" '
            'and not(@href="http://schema.org/InStock")]')
        return bool(status)

    def _parse_buyer_reviews(self, response):
        contents = response.body_as_unicode()
        meta = response.meta.copy()
        product = response.meta['product']
        reqs = meta.get('reqs', [])
        buyer_reviews = {}
        sku = product.get('sku')
        if not product.get('buyer_reviews'):
            contents = json.loads(contents)
            incl = contents.get('Includes')
            brs = incl.get('Products').get(sku) if incl else None
            if brs:
                by_star = {}
                for d in brs['ReviewStatistics']['RatingDistribution']:
                    by_star[str(d['RatingValue'])] = d['Count']
                for sc in range(1, 6):
                    if str(sc) not in by_star:
                        by_star[str(sc)] = 0
                buyer_reviews['rating_by_star'] = by_star
                review_count = brs['ReviewStatistics']['TotalReviewCount']

                if review_count == 0:
                    product['buyer_reviews'] = ZERO_REVIEWS_VALUE
                    return product

                buyer_reviews['num_of_reviews'] = review_count
                average_review = brs['ReviewStatistics']['AverageOverallRating']
                average_review = float(format(average_review, '.2f'))
                buyer_reviews['average_rating'] = average_review

                product['buyer_reviews'] = BuyerReviews(**buyer_reviews)
            else:
                product['buyer_reviews'] = ZERO_REVIEWS_VALUE

        if not product.get('buyer_reviews'):
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_last_buyer_date(self, response):
        last_review_date = response.xpath(
            '//*[contains(@class,"box-reviews")]'
            '//*[@class="date"]/text()').re('Posted on (.*)\)')
        return last_review_date[0] if last_review_date else None

    def _parse_sku(self, response):
        sku = response.xpath('.//*[@itemprop="sku"]/@content').extract()
        return sku[0] if sku else None

    def _parse_brand(self, response, title):
        brand = response.xpath('.//*[contains(text(), "Shop all")]/text()').re(r'Shop\sall\s+(\S+)\s?')
        brand = brand[0].strip() if brand else None
        if not brand:
            brand = guess_brand_from_first_words(title)
        return brand

    def parse_product(self, response):
        reqs = []
        meta = response.meta.copy()
        product = meta['product']

        if response.status == 404:
            product['not_found'] = True
            return product

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse reseller_id
        reseller_id = self._extract_reseller_id(response.url)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        # Parse stock status
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # Parse brand
        brand = self._parse_brand(response, product.get('title'))
        cond_set_value(product, 'brand', brand)

        # Parse last buyer review date
        last_buyer_date = self._parse_last_buyer_date(response)
        cond_set_value(product, 'last_buyer_review_date', last_buyer_date)

        # Parse reviews
        reqs.append(
            Request(
                url=self._REVIEWS_URL.format(sku=product['sku']),
                dont_filter=True,
                callback=self._parse_buyer_reviews,
                meta=meta
            ))
        if reqs:
            return self.send_next_request(reqs, response)

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

    @staticmethod
    def _extract_reseller_id(url):
        reseller_id = re.search('\d{7}', url)
        return reseller_id.group(0) if reseller_id else None
