from __future__ import division, absolute_import, unicode_literals

import re
import itertools
import traceback
import json
from urlparse import urlparse

from scrapy import Request, FormRequest
from scrapy.conf import settings
from scrapy.log import WARNING

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults, FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator


class BedBathAndBeyondProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'bedbathandbeyond_products'
    allowed_domains = ["www.bedbathandbeyond.com"]

    SEARCH_URL = "https://www.bedbathandbeyond.com/api/apollo/collections/bedbath/query-profiles/v1/select?wt=json" \
                 "&q={search_term}&rows={prods_per_page}&noFacet=true&start={start_num}&view=grid3&site=BedBathUS"

    REVIEW_URL = 'https://api.bazaarvoice.com/data/batch.json' \
                 '?passkey=caUoXj5OdcJR5OWpNSYAitJAZzbSnaDvoH6iGXB69ls8M' \
                 '&apiversion=5.5&displaycode=2009-en_us' \
                 '&resource.q0=products' \
                 '&filter.q0=id%3Aeq%3A{product_id}' \
                 '&stats.q0=reviews&filteredstats.q0=reviews' \
                 '&filter_reviews.q0=contentlocale%3Aeq%3Afr%2Cen_US' \
                 '&filter_reviewcomments.q0=contentlocale%3Aeq%3Afr%2Cen_US'

    PROD_URL = "https://www.bedbathandbeyond.com/store{}"

    prods_per_page = 48

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = True

        self.br = BuyerReviewsBazaarApi()
        super(BedBathAndBeyondProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(prods_per_page=48, start_num=0),
            *args, **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2

        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3325.181 Safari/537.36"

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        self.current_page = 1
        self.HOME_URL = 'https://www.bedbathandbeyond.com/'
        self.SHIP_URL = '?_DARGS=/store/_includes/modals/intlCountryCurrecyModal.jsp.1'

    def start_requests(self):
        yield Request(
            url=self.HOME_URL,
            callback=self._open_dialog,
            headers={
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'accept-encoding': 'gzip, deflate, br',
                'accept-language': 'en-US,en;q=0.9',
                'upgrade-insecure-requests': '1',
                'user-agent': self.user_agent
            }
        )

    def _open_dialog(self, response):
        return Request(
            url='https://www.bedbathandbeyond.com/store/_includes/modals/intlCountryCurrecyModal.jsp'
                '?bbbModalDialog=true',
            callback=self._change_ship,
            headers={
                'x-requested-with': 'XMLHttpRequest',
                'pragma': 'no-cache',
                'accept': 'text/html, */*; q=0.01',
                'accept-encoding': 'gzip, deflate, br',
                'accept-language': 'en-US,en;q=0.9',
                'bbb-ajax-request': 'true'
            }
        )

    def _change_ship(self, response):
        return FormRequest.from_response(
            response,
            callback=self._start_request,
            formname='intlShippingReset',
            formdata={
                '/com/bbb/internationalshipping/formhandler/InternationalShipFormHandler.updateUserContext': 'Ship to usa'
            },
            dont_filter=True
        )

    def _start_request(self, response):
        for req in super(BedBathAndBeyondProductsSpider, self).start_requests():
            yield req

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        if self._parse_no_longer_available(response):
            product['no_longer_available'] = True
        else:
            product['no_longer_available'] = False

        title = self._parse_title(response)
        product['title'] = title

        brand = self._parse_brand(response)
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        product['image_url'] = image_url

        categories = self._parse_categories(response)
        product['categories'] = categories

        price = self._parse_price(response)
        product['price'] = price

        was_now = self._parse_was_now(response)
        cond_set_value(product, 'was_now', was_now)

        cond_set_value(product, 'promotions', bool(was_now))

        variants = self._parse_variants(response)
        product["variants"] = variants

        product['locale'] = "en-US"

        reseller_id = self._parse_reseller_id(response.url)
        cond_set_value(product, 'reseller_id', reseller_id)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        product_id = response.xpath("//input[contains(@name, 'productId')]/@value").re(r'\d+')
        if product_id:
            return Request(
                url=self.REVIEW_URL.format(product_id=product_id[0]),
                callback=self._parse_buyer_reviews,
                meta={"product": product},
                dont_filter=True,
            )

        return product

    @staticmethod
    def _parse_no_longer_available(response):
        available = response.xpath('//span[@class="error" and contains(., "No Longer Available")]')
        return bool(available)

    def _parse_title(self, response):
        product_name = response.xpath("//h1[@id='productTitle']/text()").extract()

        return product_name[0].strip() if product_name else None

    def _parse_categories(self, response):
        categories_list = response.xpath(
            "//div[contains(@class, 'breadcrumbs')]"
            "//a[contains(@href,'category')]/@title"
        ).extract()
        categories = map(self._clean_text, categories_list)

        return categories if categories else None

    def _parse_brand(self, response):
        brand = response.xpath(
            "//div[@itemprop='brand']"
            "//span[@itemprop='name']/text()").extract()
        if brand:
            brand = brand[0].strip()

        return brand if brand else None

    def _parse_price(self, response):
        price = response.xpath("//div[@class='isPrice']/@aria-label | "
                               "//span[@itemprop='lowPrice']/@content |"
                               "//div[contains(@class, 'isPrice')]//span[@itemprop='price']/@content").re(FLOATING_POINT_RGEX)
        currency = response.xpath("//span[@itemprop='priceCurrency']/@content").extract()
        currency = currency[0] if currency else 'USD'
        try:
            price = Price(
                price=float(price[0].replace(',', '').replace('$', '').strip()),
                priceCurrency=currency
            )
            return price
        except:
            self.log('Error while parsing price'.format(traceback.format_exc()), WARNING)

    def _parse_was_now(self, response):
        current_price = response.xpath("//div[@class='isPrice']/@aria-label | "
                                       "//span[@itemprop='lowPrice']/@content |"
                                       "//div[contains(@class, 'isPrice')]"
                                       "//span[@itemprop='price']/@content").re(FLOATING_POINT_RGEX)
        was_price = response.xpath(
            '//div[@class="wasPrice"]/text()'
        ).re(FLOATING_POINT_RGEX)
        if all([current_price, was_price]):
            return '{}, {}'.format(current_price[0], was_price[0])

    def _parse_image(self, response):
        image = response.xpath(
            "//a[@id='mainProductImgZoom']/@data-zoomhref|"
            "//div[@id='s7ProductImageWrapper']//img/@src"
        ).extract()

        if image:
            image_url = 'https:' + image[0]
            return image_url

    @staticmethod
    def _parse_reseller_id(url):
        reseller_id = urlparse(url).path.split('/')[-1]
        return reseller_id

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath(
            '//div[contains(@class, "appendSKUInfo")]//p[contains(@class, "prodSKU")]/text()'
        ).re(r'\d+')
        return sku[0] if sku else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        return not bool(response.xpath('//link[@itemprop="availability" and @href="http://schema.org/InStock"]')) \
               or bool(response.xpath('//div[@class="isPrice" and contains(text(), "Not Available")]'))

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    def _parse_variants(self, response):
        attribute_list = []
        variant_list = []
        attribute_values_list = []
        size_list_all = []

        color_list = filter(lambda x: x.strip(), set(self._get_colors(response)))
        attribute_values_list.append(color_list)

        sizes = self._get_sizes(response)
        for size in sizes:
            size = self._clean_text(size).replace(' ', '')
            size_list_all.append(size)
        if size_list_all:
            size_list_all = [r for r in list(set(size_list_all)) if len(r.strip()) > 0]
            attribute_values_list.append(size_list_all)
        combination_list = list(itertools.product(*attribute_values_list))
        combination_list = [list(tup) for tup in combination_list]
        if color_list:
            if 'color' not in attribute_list:
                attribute_list.append('color')
        if size_list_all:
            if 'size' not in attribute_list:
                attribute_list.append('size')
        for variant_combination in combination_list:
            variant_item = {}
            properties = {}
            for index, attribute in enumerate(attribute_list):
                properties[attribute] = variant_combination[index]
            variant_item['properties'] = properties
            variant_list.append(variant_item)
        return variant_list

    def _parse_buyer_reviews(self, response):
        product = response.meta.get('product')

        try:
            raw_json = json.loads(response.body_as_unicode())
        except Exception as e:
            self.log('Invalid reviews: {}'.format(str(e)))
            return product

        buyer_reviews_data = raw_json.get('BatchedResults', {}).get('q0', {})
        response = response.replace(body=json.dumps(buyer_reviews_data))
        buyer_reviews = BuyerReviews(
            **self.br.parse_buyer_reviews_products_json(response))
        product['buyer_reviews'] = buyer_reviews

        return product

    @staticmethod
    def _get_sizes(response):
        sizes = response.xpath(
            "//select[@id='selectProductSize']"
            "//option/text()").extract()

        return sizes[1:]

    @staticmethod
    def _get_colors(response):
        colors = response.xpath(
            "//ul[contains(@class, 'swatches')]"
            "//li[contains(@class, 'colorSwatchLi')]/@title").extract()

        return colors

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            total_matches = data.get('response').get('numFound')
        except:
            self.log(traceback.format_exc())
            total_matches = 0

        return total_matches

    def _scrape_product_links(self, response):
        links = []
        try:
            data = json.loads(response.body_as_unicode())
            items = data.get('response').get('docs')
            for item in items:
                if item.get('SEO_URL'):
                    links.append(item.get('SEO_URL'))
        except:
            self.log(traceback.format_exc())

        for link in links:
            yield self.PROD_URL.format(link), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        start_num = self.current_page * self.prods_per_page
        if start_num >= self._scrape_total_matches(response):
            return None

        self.current_page += 1
        st = response.meta['search_term']

        return self.SEARCH_URL.format(search_term=st, prods_per_page=self.prods_per_page, start_num=start_num)
