import json
import re
import traceback
import urlparse
import math

from lxml import html
from scrapy import Request
from scrapy.conf import settings
from scrapy.log import WARNING

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (FLOATING_POINT_RGEX, BaseProductsSpider, FormatterWithDefaults,
                                     cond_set_value)
from product_ranking.utils import is_empty


class GraingerProductsSpider(BaseProductsSpider):
    name = 'grainger_products'
    allowed_domains = ['www.grainger.com']

    SEARCH_URL = "https://www.grainger.com/search?searchQuery={search_term}" \
                 "&perPage=32&requestedPage={page_num}&ts_optout=true"

    REVIEWS_URL = 'https://grainger.ugc.bazaarvoice.com/5049hbrs-en_us/{0}/reviews.djs?format=embeddedhtml'

    NEXT_PAGE_PARAM = '&perPage={results_per_page}&requestedPage={page_num}'

    agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36"
    headers = {'Content-Type': 'application/json', 'User-agent': agent}

    def __init__(self, *args, **kwargs):
        url_formatter = FormatterWithDefaults(page_num=1)
        super(GraingerProductsSpider, self).__init__(
            url_formatter=url_formatter,
            site_name=self.allowed_domains[0],
            *args, **kwargs
        )
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.CustomClientContextFactory'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en-US"

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        cond_set_value(product, 'is_out_of_stock', False)

        self._parse_price(response)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        department = self._parse_department(response)
        cond_set_value(product, 'department', department)

        if sku:
            return Request(
                url=self.REVIEWS_URL.format(sku),
                callback=self.parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    def _parse_title(self, response):
        title = response.xpath("//h1[@class='productName']/text()").extract()
        return self._clean_text(is_empty(title)) if title else None

    def _parse_brand(self, response):
        brand = response.xpath("//*[@itemprop='Brand']/text()").extract()
        return is_empty(brand)

    def _parse_currency(self, response):
        price_currency = response.xpath("//span[@itemprop='priceCurrency']/@content").extract()
        return price_currency[0] if price_currency else 'USD'

    def _parse_price(self, response):
        product = response.meta['product']
        price = response.xpath("//span[@itemprop='price']/@content").extract()
        price_currency = self._parse_currency(response)
        if price:
            price = re.findall(FLOATING_POINT_RGEX, price[0])
            cond_set_value(product, 'price',
                           Price(price=price[0].replace(',', ''),
                                 priceCurrency=price_currency))

    def _parse_image_url(self, response):
        image_url = response.xpath('//*[contains(@class, "carouselItemList")]'
                                   '//img/@data-image').extract()
        return urlparse.urljoin(response.url, image_url[0]) if image_url else None

    def _parse_sku(self, response):
        sku = response.xpath("//span[@itemprop='productID']/text()").extract()
        return is_empty(sku)

    def _parse_upc(self, response):
        upc = response.xpath("//li[@id='unspc']//span/text()").extract()
        return is_empty(upc)

    def _parse_model(self, response):
        model = response.xpath("//span[@itemprop='model']/text()").extract()
        return is_empty(model)

    def _parse_categories(self, response):
        categories = response.xpath("//section[@id='breadcrumbs']//li//a/text()").extract()
        return categories

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def parse_buyer_reviews(self, response):
        rating_counts = []
        product = response.meta.get("product")
        contents = response.body_as_unicode()

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        try:
            start_index = contents.find("webAnalyticsConfig:") + len("webAnalyticsConfig:")
            end_index = contents.find(",\nwidgetInitializers:initializers", start_index)

            review_json = contents[start_index:end_index]
            review_json = json.loads(review_json)

            review_html = html.fromstring(
                re.search('"BVRRSecondaryRatingSummarySourceID":" (.+?)"},\ninitializers={', contents).group(1))

            reviews_by_mark = review_html.xpath("//*[contains(@class, 'BVRRHistAbsLabel')]/text()")
            reviews_by_mark = reviews_by_mark[:5][::-1]

            # Average Rating, Count of Reviews
            if review_json:
                num_of_reviews = review_json["jsonData"]["attributes"]["numReviews"]
                average_rating = round(float(review_json["jsonData"]["attributes"]["avgRating"]), 1)

            if reviews_by_mark:
                rating_counts = [int(re.findall('\d+', mark)[0]) for i, mark in enumerate(reviews_by_mark)]

            if len(rating_counts) == 5:
                rating_by_star = {'1': rating_counts[0], '2': rating_counts[1],
                                  '3': rating_counts[2], '4': rating_counts[3], '5': rating_counts[4]}
            else:
                rating_by_star = {}

            if rating_by_star:
                buyer_reviews_info = {
                    'num_of_reviews': int(num_of_reviews),
                    'average_rating': float(average_rating),
                    'rating_by_star': rating_by_star
                }

            else:
                buyer_reviews_info = ZERO_REVIEWS_VALUE

        except Exception:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()), WARNING)
            buyer_reviews_info = ZERO_REVIEWS_VALUE

        product['buyer_reviews'] = BuyerReviews(**buyer_reviews_info)

        return product

    def _scrape_total_matches(self, response):
        total_matches = re.findall('"numProductsReturned":(\d+)', response.body_as_unicode())
        return int(is_empty(total_matches)) if total_matches else None

    def _scrape_product_links(self, response):
        data = None
        json_data = re.search('search_variables=(.*?),\slevel', response.body_as_unicode())
        try:
            data = json.loads(json_data.group(1))
        except:
            self.log("Error while parsing json data {}".format(traceback.format_exc()))

        if data:
            search_products_info = data.get('SEARCH_TERMS', {}).get('searchResultProducts', [])

            if search_products_info:
                for product_info in search_products_info:
                    product_id = product_info.get('ProductId', '')

                    if product_id and 'WP' not in product_id:
                        brand_name = product_info.get('BrandName', '')
                        product_name = product_info.get('ProductNm', '').split(',')[0].replace(' ', '-')

                        if brand_name and product_name:
                            link = '/product/' + brand_name + '-' + product_name + '-' + product_id
                            link = urlparse.urljoin(response.url, link)

                            res_item = SiteProductItem()
                            yield link, res_item

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page', 1)
        total_matches = response.meta.get('total_matches')
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 32
        if (total_matches and results_per_page
            and current_page < math.ceil(total_matches / float(results_per_page))):
            current_page += 1
            url = self.SEARCH_URL.format(search_term=response.meta['search_term'],
                                         page_num=current_page)
            meta['current_page'] = current_page
            return Request(url, meta=meta)

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
