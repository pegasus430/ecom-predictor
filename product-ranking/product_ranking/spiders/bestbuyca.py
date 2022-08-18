import re
import urlparse
import traceback
import json

from scrapy import Request
from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value,\
    FormatterWithDefaults
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words


class BestbuycaProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'bestbuyca_products'
    allowed_domains = ["www.bestbuy.ca"]

    SEARCH_URL = "http://www.bestbuy.ca/en-CA/Search/SearchResults.aspx?query={search_term}"

    API_URL = "https://api-ssl.bestbuy.ca/availability/products?accept-language=en&" \
              "skus={id}&" \
              "accept=application%2Fvnd.bestbuy.standardproduct.v1%2Bjson&" \
              "postalCode=M5G2C3&locations=977%7C203%7C931%7C62%7C617&maxlos=3"

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        self._parse_price(response)

        description = self._parse_description(response)
        product['description'] = description

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        product['department'] = category

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        buyer_reviews = self.parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        id = response.url.split('/')[-1]
        id = re.search('(\d+)', id, re.DOTALL)
        if id:
            id = id.group(1)
            return Request(
                url=self.API_URL.format(id=id),
                callback=self._parse_is_out_of_stock,
                meta={
                    'product': product,
                },
                dont_filter=True
            )

        return product

    def _parse_title(self, response):
        title = response.xpath("//span[@id='ctl00_CP_ctl00_PD_lblProductTitle']/text()").extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//span[@class='brand-logo']//img/@alt").extract()

        if brand:
            brand = brand[0]
        if not brand and title:
            brand = guess_brand_from_first_words(title)

        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//span[@property='itemListElement']//span[@property='name']/text()").extract()
        return categories[1:-1] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_description(self, response):
        description = response.xpath("//div[@itemprop='description']//text()").extract()
        if not description:
            description = response.xpath("//div[@class='tab-overview-item']/text()").extract()
        return self._clean_text(''.join(description))

    def _parse_image_url(self, response):
        main_image = response.xpath("//div[@class='gallery-image-container']//img/@src").extract()
        return main_image[0] if main_image else None

    def _parse_currency(self, response):
        price_currency = response.xpath("//meta[@itemprop='priceCurrency']/@content").extract()
        return price_currency[0] if price_currency else 'CAD'

    def _parse_price(self, response):
        product = response.meta['product']
        price_currency = self._parse_currency(response)
        price = response.xpath("//span[@class='amount']/text()").extract()

        if price:
            cond_set_value(product, 'price',
                           Price(price=price[0].replace(',', '').replace('$', '').strip(), priceCurrency=price_currency))

    def _parse_model(self, response):
        model = response.xpath("//span[@itemprop='model']/text()").extract()
        return model[0] if model else None

    def _parse_sku(self, response):
        upc = response.xpath("//span[@itemprop='productid']/text()").extract()
        return upc[0] if upc else None

    def parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        buyer_reviews_info = {}

        num_of_reviews = response.xpath("//div[@itemprop='ratingCount']/text()").re('\d+')
        num_of_reviews = num_of_reviews[0] if num_of_reviews else 0

        avarage_rating = response.xpath("//div[@itemprop='ratingvalue']/text()").extract()
        if avarage_rating:
            avarage_rating = self._clean_text(avarage_rating[0])
        else:
            avarage_rating = 0

        # Get count of Mark
        rating_counts = response.xpath(
            "//ul[contains(@class, 'rating-detail')]"
            "//div[contains(@class, 'rating-detail-total-ratings')]/text()").extract()

        if rating_counts:
            rating_counts = list(reversed(rating_counts))

        if len(rating_counts) == 5:
            rating_by_star = {'1': rating_counts[0], '2': rating_counts[1],
                              '3': rating_counts[2], '4': rating_counts[3], '5': rating_counts[4]}
        else:
            rating_by_star = {}

        if rating_by_star:
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

    def _parse_reseller_id(self, response):
        return self._parse_sku(response)

    def _parse_is_out_of_stock(self, response):
        product = response.meta.get('product')
        try:
            data = json.loads(response.body[response.body.find('{'):])
            product['is_out_of_stock'] = 'OutOfStock' in data.get('availabilities')[0].get('pickup').get('status')
        except:
            self.log("Error while parsing stock status: {}".format(traceback.format_exc()))
        return product

    def _scrape_total_matches(self, response):
        total_match = response.xpath("//span[@class='display-total']/text()").extract()
        return int(total_match[0]) if total_match else 0

    def _scrape_product_links(self, response):
        self.product_links = response.xpath("//div[@class='prod-info']//a/@href").extract()

        for item_url in self.product_links:
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if not self.product_links:
            return
        next_page_link = response.xpath("//li[@class='pagi-next']//a/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
