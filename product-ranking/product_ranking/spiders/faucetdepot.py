from __future__ import division, absolute_import, unicode_literals

import re
import traceback
import urlparse
from lxml import html
from scrapy.conf import settings

from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value,\
    FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words


class FaucetdepotProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'faucetdepot_products'
    allowed_domains = ["www.faucetdepot.com", "faucetdepot.ecomm-nav.com"]

    SEARCH_URL = "https://faucetdepot.ecomm-nav.com/search.js?" \
                 "initial_url=https://www.faucetdepot.com/faucetdepot/search.asp" \
                 "?SearchString={search_term}" \
                 "&keywords={search_term}&search_return=all" \
                 "&page={page}&callback=jQuery"

    def __init__(self, *args, **kwargs):
        # All this is to set the site_name since we have several
        # allowed_domains.
        super(FaucetdepotProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page=1),
            site_name=self.allowed_domains[0],
            *args, **kwargs)
        self.current_page = 1
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)' \
                          'Chrome/66.0.3359.139 Safari/537.36'
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['COOKIES_ENABLED'] = False
        settings.overrides['REFERER_ENABLED'] = False
        settings.overrides['DOWNLOAD_DELAY'] = 2

    def start_requests(self):
        for request in super(FaucetdepotProductsSpider, self).start_requests():
            request = request.replace(dont_filter=True)
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        brand = self._parse_brand(response)
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        if price:
            product['price'] = price

        if product.get('price'):
            product['price'] = Price(
                price=product['price'].replace(',', '').replace(
                    '$', '').strip(),
                priceCurrency='USD'
            )

        product['locale'] = "en-US"

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        product['category'] = category

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        buyer_reviews = self.parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath("//div[@id='ProductTitle']//span[@itemprop='name']/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//span[@itemprop='brand']/text()").extract()

        if brand:
            brand = brand[0]
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath("//div[@id='Breadcrumbs']//a/text()").extract()
        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    @staticmethod
    def _parse_image_url(response):
        main_image = None
        carousel_image = response.xpath("//div[@id='carousel-wrapper']//span//img/@src").extract()
        prod_image = response.xpath("//div[@id='ProdImage']//img/@src").extract()

        if carousel_image:
            main_image = carousel_image[0]
        elif prod_image:
            main_image = prod_image[0]

        return urlparse.urljoin(response.url, main_image)

    @staticmethod
    def _parse_price(response):
        price = response.xpath("//span[@itemprop='price']/text()").extract()
        return price[0] if price else None

    @staticmethod
    def _parse_model(response):
        model = response.xpath("//span[@itemprop='mpn']/text()").extract()
        return model[0] if model else None

    @staticmethod
    def _parse_upc(response):
        upc = response.xpath("//div[@id='UPCData']/text()").extract()
        return upc[0] if upc else None

    @staticmethod
    def _parse_out_of_stock(response):
        oos = response.xpath('.//*[contains(@class, "GreenBold") and contains(text(), "Out of Stock")]')
        return bool(oos)

    def parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        buyer_reviews_info = {}

        num_of_reviews = response.xpath(
            "//span[@itemprop='reviewCount']/text()").extract()

        # Count of Review
        if num_of_reviews:
            num_of_reviews = num_of_reviews[0]
        else:
            num_of_reviews = 0

        avarage_rating = response.xpath(
            "//span[@itemprop='ratingValue']/text()").extract()
        avarage_rating = avarage_rating[0] if avarage_rating else 0

        rating_value_list = []

        rating_value_data = response.xpath("//table[@id='Table_3']").extract()
        for rating_value in rating_value_data:
            rating_star = len(html.fromstring(rating_value).xpath(".//td//img/@src"))
            rating_value_list.append(rating_star)

        if rating_value_list:
            for rating_values in rating_value_list:
                rating_by_star[str(rating_values)] += 1

        # if rating_by_star:
        if num_of_reviews:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(avarage_rating),
                'rating_by_star': rating_by_star
            }

        if buyer_reviews_info:
            return BuyerReviews(**buyer_reviews_info)
        else:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    def _scrape_total_matches(self, response):
        total_match = None
        load_data = self._find_between(response.body, '"content":', ',"title"')
        total_match_info = html.fromstring(load_data).xpath("//div[@id='SearchResults']//span/strong/text()")

        if total_match_info:
            total_match = total_match_info[0].split()[-1]
        return int(total_match) if total_match else 0

    def _scrape_product_links(self, response):
        load_data = self._find_between(response.body, '"content":', ',"title"')
        self.product_links = html.fromstring(load_data).xpath("//div[@id='ProductListDetails']//a/@href")

        for item_url in self.product_links:
            if 'https' in item_url:
                yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if not self.product_links:
            return
        self.current_page += 1
        search_term = response.meta['search_term']
        next_link = self.SEARCH_URL.format(search_term=search_term, page=self.current_page)
        return next_link

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _find_between(self, s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
