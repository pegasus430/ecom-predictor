import json
import re
import string
import traceback
import urllib
import urlparse

from scrapy import Request
from scrapy.conf import settings

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from spiders_shared_code.oldnavy_variants import OldnavyVariants


class OldnavyProductsSpider(BaseProductsSpider):

    name = 'oldnavy_products'
    allowed_domains = ["oldnavy.gap.com"]

    SEARCH_URL = "http://oldnavy.gap.com/browse/search.do?searchText={search_term}"

    PRODUCTS_URL = "http://oldnavy.gap.com/resources/productSearch/v1/{search_term}?" \
                 "&isFacetsEnabled=true&globalShippingCountryCode=&globalShippingCurrencyCode=" \
                 "&locale=en_US&pageId={page_number}"

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json?passkey=68zs04f4b1e7jqc41fgx0lkwj" \
                 "&apiversion=5.5&displaycode=3755_31_0-en_us&resource.q0=products&" \
                 "filter.q0=id:eq:{product_id}&stats.q0=reviews&filteredstats.q0=reviews" \
                 "&filter_reviews.q0=contentlocale:eq:en_CA,en_US&filter_reviewcomments.q0=contentlocale:eq:en_CA,en_US" \
                 "&resource.q1=reviews&filter.q1=isratingsonly:eq:false&filter.q1=productid:eq:{product_id}"

    PRODUCT_URL = "http://oldnavy.gap.com/browse/product.do?pid={0}"

    def __init__(self, *args, **kwargs):
        super(OldnavyProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['USE_PROXIES'] = True

        self.current_page = 0
        self.products_json = []

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        for search_term in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(search_term.encode('utf-8')),
                ),
                meta={'search_term': search_term, 'remaining': self.quantity},
                callback=self._parse_helper,
                dont_filter=True
            )

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          callback=self._parse_single_product,
                          meta={'product': prod},
                          dont_filter=True)

    def _parse_helper(self, response):
        st = response.meta['search_term']
        return Request(
            self.PRODUCTS_URL.format(
                search_term=st,
                page_number=self.current_page
            ),
            meta={'search_term': st, 'remaining': self.quantity},
            dont_filter=True
        )

    def parse_product(self, response):
        if re.search(r'https?://www\.oldnavy\.com/commonDomainFrame\.do', response.url):
            self.log('Site does not redirect directly to a product page, build url with targetURL data')
            # with sem parameter oldnavy return incomplete page
            product_path = urllib.unquote(response.url).split('targetURL=')[-1].replace('&sem=true', '')
            url = urlparse.urljoin('http://oldnavy.gap.com/', product_path)
            return Request(url, meta=response.meta, callback=self.parse_product, dont_filter=True)

        meta = response.meta.copy()
        product = meta['product']

        reqs = []
        meta['reqs'] = reqs

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        if title:
            brand = guess_brand_from_first_words(title)
            cond_set_value(product, 'brand', brand)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description, conv=string.strip)

        # Parse sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        product_json = self._get_product_json(response)
        oldnavy_variants = OldnavyVariants()
        oldnavy_variants.setupSC(response, product_json)
        variants = oldnavy_variants._variants()
        cond_set_value(product, 'variants', variants)

        try:
            product_id = re.search('pid=(\d+)', response.url).group(1)
        except Exception as e:
            product_id = None
            self.log("Error while parsing reviews: {}".format(traceback.format_exc(e)))

        if product_id:
            response.meta['marks'] = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
            response.meta['product'] = product
            response.meta['product_id'] = product_id
            meta = response.meta

            return Request(
                url=self.REVIEW_URL.format(product_id=product_id),
                dont_filter=True,
                callback=self._parse_buyer_reviews,
                meta=meta
            )

        return product

    def _parse_title(self, response):
        title = response.xpath(
            '//h1[@class="product-title"]'
            '//text()').extract()
        return title[0].strip() if title else None

    def _parse_categories(self, response):
        categories = response.xpath(
            "//section[@class='breadcrumbs']"
            "//a[@class='crumb']/text()").extract()

        return categories[1:] if categories else None

    def _parse_price(self, response):
        currency = 'USD'
        price = is_empty(response.xpath(
            "//*[contains(@class, 'product-price--highlight')]/text()").re(r'\d+.\d+'), 0.00)

        if not price:
            price = is_empty(response.xpath(
                "//*[contains(@class, 'product-price')]/text()").re(r'\d+.\d+'), 0.00)

        try:
            return Price(price=float(price), priceCurrency=currency)
        except:
            self.log('Price error {}'.format(traceback.format_exc()))

    def _parse_image_url(self, response):
        image_url = is_empty(response.xpath('//div[@class="product-photo"]'
                                            '//li[@class="product-photo--item"]'
                                            '//img/@src').extract())

        return urlparse.urljoin(response.url, image_url) if image_url else None

    def _parse_description(self, response):
        desc = None
        try:
            desc = response.xpath(
                "//div[contains(@class, 'product-information--details')]"
                "//ul[@class='sp_top_sm dash-list']").extract()[1]
        except Exception as e:
            self.log('Description error {}'.format(traceback.format_exc(e)))

        if desc:
            desc = re.sub(' +', ' ', self._clean_text(desc))

        return desc

    def _parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        meta = response.meta.copy()
        product_id = meta['product_id']
        product = response.meta['product']

        if product_id:
            try:
                json_data = json.loads(response.body, encoding='utf-8')
                product_reviews_info = json_data['BatchedResults']['q0']['Results'][0]
                product_reviews_stats = product_reviews_info.get('ReviewStatistics', None)

                if product_reviews_stats:
                    rating_by_stars = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
                    for rating in product_reviews_stats.get('RatingDistribution', []):
                        rating_value = str(rating.get('RatingValue', ''))
                        if rating_value in rating_by_stars.keys():
                            rating_by_stars[rating_value] = int(rating.get('Count', 0))

                    try:
                        average_rating = float(format(product_reviews_stats.get('AverageOverallRating', .0), '.1f'))
                    except:
                        average_rating = 0.0

                    product['buyer_reviews'] = BuyerReviews(
                        num_of_reviews=int(product_reviews_stats.get('TotalReviewCount', 0)),
                        average_rating=average_rating,
                        rating_by_star=rating_by_stars
                    )

            except Exception as e:
                self.log('Reviews error {}'.format(traceback.format_exc(e)))
        else:
            product['buyer_reviews'] = BuyerReviews(**ZERO_REVIEWS_VALUE)

        return product

    def _parse_sku(self, response):
        sku = is_empty(response.xpath("//meta[@itemprop='sku']/@content").extract())
        return sku

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        """
        Scraping number of resulted product links
        """
        if not self.products_json:
            self.products_json = self._get_products_json(response)

        try:
            total_matches = int(self.products_json.get("totalItemCount", 0))
        except Exception as e:
            self.log('Total Match error {}'.format(traceback.format_exc(e)))
            total_matches = 0

        return total_matches

    def _scrape_product_links(self, response):
        if not self.products_json:
            self.products_json = self._get_products_json(response)

        links = []
        try:
            product_links = self.products_json["productCategory"]["childProducts"]
            links = [link["businessCatalogItemId"] for link in product_links]
        except Exception as e:
            self.log('Products Links error {}'.format(traceback.format_exc(e)))

        self.products_links = links
        for link in links:
            link = self.PRODUCT_URL.format(link)
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if not self.products_links:
            return

        st = response.meta["search_term"]
        self.current_page += 1

        if not self.products_json:
            self.products_json = self._get_products_json(response)

        try:
            pages_count = int(self.products_json["productCategory"]["productCategoryPaginator"]["pageNumberTotal"])
        except:
            pages_count = 0

        if self.current_page >= pages_count:
            return

        return self.PRODUCTS_URL.format(search_term=st, page_number=self.current_page)

    def _get_product_json(self, response):
        product_info = self._find_between(response.body, 'gap.pageProductData = ', '};')
        try:
            product_json = json.loads(product_info + '}')
        except:
            product_json = None

        return product_json

    def _get_products_json(self, response):
        try:
            products_info = json.loads(response.body)
            self.products_json = products_info.get("productCategoryFacetedSearch", {})
        except Exception as e:
            self.log('Products error {}'.format(traceback.format_exc(e)))

        return self.products_json

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""
