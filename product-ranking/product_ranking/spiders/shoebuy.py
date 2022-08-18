from __future__ import division, absolute_import, unicode_literals

import re
import json
import urlparse
import traceback

from scrapy.http import Request
from scrapy.conf import settings

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.guess_brand import guess_brand_from_first_words
from scrapy.log import DEBUG, WARNING
from spiders_shared_code.shoebuy_variants import ShoebuyVariants


class ShoebuyProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'shoebuy_products'
    allowed_domains = ["www.shoes.com", "www.shoebuy.com"]

    SEARCH_URL = "http://www.shoebuy.com/s.jsp?Search={search_term}"

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?" \
                 "passkey=lgzh8hhvewlnvqczzsaof7uno&apiversion=5.5&" \
                 "displaycode=11477-en_us&resource.q0=products&" \
                 "filter.q0=id:eq:{product_id}" \
                 "&stats.q0=reviews&" \
                 "filteredstats.q0=reviews&" \
                 "filter_questions.q0=contentlocale:eq:en_US&" \
                 "filter_answers.q0=contentlocale:eq:en_US&" \
                 "filter_reviews.q0=contentlocale:eq:en_US&" \
                 "filter_reviewcomments.q0=contentlocale:eq:en_US"

    use_proxies = False

    def __init__(self, *args, **kwargs):
        super(ShoebuyProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)' \
                          ' Chrome/66.0.3359.170 Safari/537.36'

        self.current_page = 1

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        reseller_id = self._parse_reseller_id(response)
        product['reseller_id'] = reseller_id

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        product["model"] = None

        product["upc"] = None

        product['locale'] = "en-US"

        price = self._parse_price(response)
        product['price'] = price

        was_now = self._parse_was_now(response)
        product['was_now'] = was_now

        product_json = self._parse_product_json(response)
        if product_json:
            shoebuy_variants = ShoebuyVariants()
            shoebuy_variants.setupSC(response, product_json)
            variants = shoebuy_variants._variants()
            cond_set_value(product, 'variants', variants)

        if product.get('price', None):
            product['price'] = Price(
                price=product['price'].replace(',', '').strip(),
                priceCurrency="USD"
            )

        stylecode = response.xpath('//input[@id="stylecode"]/@value').extract()

        if stylecode:
            url = self.REVIEW_URL.format(product_id=stylecode[0])
            return Request(
                url=url,
                callback=self._parse_buyer_reviews,
                meta={'product': product},
                dont_filter=True
            )

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//div[@class="category_title"]/h1/span/text()').extract()
        return ' '.join(title) if title else None

    @staticmethod
    def _parse_reseller_id(response):
        return urlparse.urlparse(response.url).path.split('/')[-1]

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = response.xpath("//span[@itemprop='brand']/text()").extract()
        if brand:
            brand = brand[0]
        else:
            brand = guess_brand_from_first_words(title if title else '')
        return brand

    @staticmethod
    def _parse_image(response):
        image_url = response.xpath("//div[@class='large_thumb has_thumbs']/img/@src").extract()
        return urlparse.urljoin(response.url, image_url[0]) if image_url else None

    @staticmethod
    def _parse_price(response):
        price = response.xpath("//a[contains(@class, 'selected')]"
                               "/span[contains(@class,'color_price')]/text()").re(FLOATING_POINT_RGEX)

        return price[0] if price else None

    def _parse_was_now(self, response):
        current_price = self._parse_price(response)
        past_price = response.xpath('//div[@class="regular_price"]'
                                    '//div[@class="strikethrough"]').re(FLOATING_POINT_RGEX)
        if past_price and current_price:
            return ', '.join([current_price, past_price[0]])

    def _parse_buyer_reviews(self, response):
        product = response.meta['product']

        buyer_review_values = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        try:
            review_json = json.loads(response.body)
            if review_json.get("BatchedResults", {}).get("q0", {}).get("Results", {}):
                review_statistics = review_json["BatchedResults"]["q0"]["Results"][0]['ReviewStatistics']

                if review_statistics.get("RatingDistribution", None):
                    for item in review_statistics['RatingDistribution']:
                        key = str(item['RatingValue'])
                        buyer_review_values["rating_by_star"][key] = item['Count']

                if review_statistics.get("TotalReviewCount", None):
                    buyer_review_values["num_of_reviews"] = review_statistics["TotalReviewCount"]

                if review_statistics.get("AverageOverallRating", None):
                    buyer_review_values["average_rating"] = format(review_statistics["AverageOverallRating"], '.1f')
        except Exception:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()), WARNING)
        finally:
            buyer_reviews = BuyerReviews(**buyer_review_values)
            product['buyer_reviews'] = buyer_reviews
            return product

    def _parse_product_json(self, response):
        try:
            product_json_text = re.search('({"sizes":.*?})\)', response.body, re.DOTALL).group(1)
            product_json = json.loads(product_json_text)
        except:
            product_json = None

        return product_json

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()

    def _scrape_product_links(self, response):
        product_links = response.xpath('//div[contains(@class, "pt_product")]'
                                       '/div[contains(@class, "pt_info")]'
                                       '/a[@class="pt_link"]/@href').extract()
        if not product_links:
            self.log("Found no product links.", DEBUG)

        for link in product_links:
            yield link, SiteProductItem()

    def _scrape_total_matches(self, response):
        totals = response.xpath('//div[contains(@class, "paging_sorting")]'
                                '/div[contains(@class, "results")]').extract()

        if totals:
            totals = re.findall(r'</span> (.*?) results', totals[0])
            totals = int(totals[0]) if totals else 0
        else:
            totals = 0

        return totals

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath('//div[contains(@class, "paging_sorting")]'
                                   '/div[contains(@class, "paging")]'
                                   '/a[contains(@class, "next")]/@href').extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])
