import re
import string
from lxml import html

from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import cond_set_value
from product_ranking.spiders.contrib.product_spider import ProductsSpider
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from scrapy import Request
import json
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.guess_brand import guess_brand_from_first_words

class TopshopProductsSpider(ProductsSpider):
    name = 'topshop_products'

    allowed_domains = ['topshop.com']

    SEARCH_URL = "http://us.topshop.com/webapp/wcs/stores/servlet/CatalogNavigationSearchResultCmd?" \
                 "langId=-1&storeId=13052&catalogId=33060&Dy=1&Nty=1&beginIndex=1&pageNum=1&Ntt={search_term}"

    _REVIEWS_URL = 'http://topshop.ugc.bazaarvoice.com/6025-en_us/{sku}/reviews.djs?format=embeddedhtml'

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(TopshopProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def _total_matches_from_html(self, response):
        total = response.xpath(
            '(//*[@class="pager"]//*[@class="amount"]'
            '/text())[1]').re('of (\d+)')

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
        categories = response.xpath('//*[@id="nav_breadcrumb"]//li//a//span//text()').extract()
        return categories[-1] if categories else None

    def _parse_price(self, response):
        price = response.xpath(
            '//div[contains(@class,"product_details")]'
            '//div[contains(@class,"product_prices")]//span//text()'
        ).extract()
        if len(price) > 1:
            price = price[1]
            if "$" in price:
                currency = 'USD'
            else:
                currency = ''

            price = re.findall(r'[\d\.]+', price)
        if len(price) == 0:
            return None

        return Price(price=price[0], priceCurrency=currency)

    def _parse_image_url(self, response):
        image_url = response.xpath(
            '//ul[contains(@class,"product_hero__wrapper")]'
            '//a[contains(@class,"hero_image_link")]//img/@src'
        ).extract()
        return image_url[0] if image_url else None

    def _parse_variants(self, response):
        return None

    def _parse_is_out_of_stock(self, response):
        status = response.xpath(
            '//*[@itemprop="availability" '
            'and not(@href="http://schema.org/InStock")]')
        return bool(status)

    def _parse_description(self, response):
        description = response.xpath('//div[@id="productInfo"]//p//text()').extract()
        return ''.join(description).strip() if description else None

    def _parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        product = response.meta['product']
        reqs = meta.get('reqs', [])

        product['buyer_reviews'] = self.br.parse_buyer_reviews_per_page(response)

        if reqs:
            return self.send_next_request(reqs, response)
        else:
            return product

    def clear_text(self, str_result):
        return str_result.replace("\t", "").replace("\n", "").replace("\r", "").strip()

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs', [])

        content = re.search(
            'BVRRRatingSummarySourceID":"(.+?)\},', response._body
        ).group(1).replace('\\"','"')
        content = content.replace("\\/", "/")
        review_html = html.fromstring(content)

        arr = review_html.xpath(
            '//div[contains(@class,"BVRRQuickTakeSection")]'
            '//div[contains(@class,"BVRRRatingOverall")]'
            '//img[contains(@class,"BVImgOrSprite")]/@title'
        )

        if len(arr) > 0:
            average_rating = float(arr[0].strip().split(" ")[0])
        else:
            average_rating = 0.0

        arr = review_html.xpath(
            '//div[contains(@class,"BVRRReviewDisplayStyle5")]'
            '//div[contains(@class,"BVRRReviewDisplayStyle5Header")]'
            '//span[@itemprop="ratingValue"]//text()'
        )
        num_of_reviews = len(arr)

        review_list = [[5-i, arr.count(str(5-i))] for i in range(5)]

        if review_list:
            # average score
            sum = 0
            cnt = 0
            for i, review in review_list:
                sum += review*i
                cnt += review
            # average_rating = float(sum)/cnt
            # number of reviews
            num_of_reviews = 0
            for i, review in review_list:
                num_of_reviews += review
        else:
            pass

        rating_by_star = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for i, review in review_list:
            rating_by_star[i] = review
        if average_rating and num_of_reviews:
            product["buyer_reviews"] = BuyerReviews(
                num_of_reviews=int(num_of_reviews),
                average_rating=float(average_rating),
                rating_by_star=rating_by_star,
            )
        else:
            product["buyer_reviews"] = ZERO_REVIEWS_VALUE

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_last_buyer_date(self, response):
        last_review_date = response.xpath(
            '//*[contains(@class,"box-reviews")]'
            '//*[@class="date"]/text()').re('Posted on (.*)\)')
        return last_review_date[0] if last_review_date else None

    def _parse_sku(self, response):
        sku = response.xpath(
            '//div[@id="productInfo"]//li[contains(@class,"product_code")]//span//text()'
        ).extract()
        return sku[0] if sku else None

    def _parse_brand(self, response, title):
        brand = response.xpath('.//*[contains(text(), "Shop all")]/text()').re(r'Shop\sall\s+(\S+)\s?')
        brand = brand[0].strip() if brand else None
        if not brand:
            try:
                brand = guess_brand_from_first_words(title)
            except:
                brand = None
        return brand

    def parse_product(self, response):
        reqs = []
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

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
