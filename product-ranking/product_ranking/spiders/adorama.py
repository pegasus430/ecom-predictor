import urllib

from scrapy import Request
from scrapy.conf import settings

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders import (BaseProductsSpider, cond_set_value, cond_set,
                                     FLOATING_POINT_RGEX, FormatterWithDefaults)


class AdoramaProductsSpider(BaseProductsSpider):
    name = 'adorama_products'
    allowed_domains = ['adorama.com']
    handle_httpstatus_list = [404, 403, 502, 520]

    SEARCH_URL = "https://www.adorama.com/searchsite/default.aspx?SearchInfo={search_term}&Page=1"
    HEADERS = {"upgrade-insecure-requests": "1",
               "referer": "https://www.adorama.com/",
               "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
               "accept-encoding": "gzip, deflate, sdch, br",
               "accept-language": "en-US,en;q=0.8",
               "cache-control": "max-age=0",
               "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/61.0.3163.100 Safari/537.36"
               }

    def __init__(self, *args, **kwargs):
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        settings.overrides['RETRY_HTTP_CODES'] = [500, 502, 503, 504, 400, 403, 408, 429]
        settings.overrides['DOWNLOAD_DELAY'] = 1
        settings.overrides['CONCURRENT_REQUESTS'] = 2
        settings.overrides['USE_PROXIES'] = True
        settings.overrides['COOKIES_ENABLED'] = False
        settings.overrides['REFERER_ENABLED'] = False

        super(AdoramaProductsSpider, self).__init__(
            url=self.SEARCH_URL,
            site_name=self.allowed_domains[0],
            *args, **kwargs)

        self.headers = {
                        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) '
                                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                                      'Chrome/61.0.3163.100 Safari/537.36'
                        }

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.custom_middlewares.IncapsulaRequestMiddleware'] = 3
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

    def start_requests(self):
        for st in self.searchterms:
            yield Request(
                url=self.SEARCH_URL.format(search_term=urllib.quote_plus(st.encode('utf-8'))),
                headers=self.HEADERS,
                meta={'search_term': st, 'remaining': self.quantity},
                dont_filter=True
            )
            yield Request(url=self.SEARCH_URL.format(search_term=urllib.quote_plus(st.encode('utf-8'))),
                          meta={'search_term': st, 'remaining': self.quantity},
                          headers=self.headers,
                          dont_filter=True)

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod},
                          headers=self.HEADERS)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en_GB"

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        avaliable_online = self._parse_avaliable_online(response)
        cond_set_value(product, 'available_online', avaliable_online)

        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        brand = self._parse_brand(response)
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        model = self._parse_model(response)
        cond_set_value(product, 'model', model)

        reseller_id = self._parse_resellerId(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        categories = self._parse_categories(response)
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        average_rating = response.xpath(
            '//span[@itemprop="ratingValue"]/text()').extract()

        num_of_reviews = response.xpath(
            '//span[@itemprop="ratingCount"]/text()').extract()

        rating_by_star = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for li in response.xpath('//ul/li'):
            i = li.xpath(
                'span[@class="pr-histogram-label"]/text()'
            ).re(FLOATING_POINT_RGEX)
            count = li.xpath(
                'span[@class="pr-histogram-count"]/text()'
            ).re(FLOATING_POINT_RGEX)
            if i and count:
                rating_by_star[int(i[0])] = int(count[0])

        if average_rating and num_of_reviews:
            product["buyer_reviews"] = BuyerReviews(
                num_of_reviews=int(num_of_reviews[0]),
                average_rating=float(average_rating[0]),
                rating_by_star=rating_by_star,
            )
        else:
            product["buyer_reviews"] = ZERO_REVIEWS_VALUE

        return product

    def _parse_title(self, response):
        title = response.xpath(
                '//div[@class="primary-info cf clear "]//h1//span/text()'
            ).extract()

        if title:
            title = ''.join(title)
        else:
            title = None

        return title

    def _parse_price(self, response):
        currency = self._parse_currency(response)
        price = response.xpath(
                '//div[@class="price-final"]//strong[@class="your-price"]'
            ).re(FLOATING_POINT_RGEX)

        if price:
            price = Price(currency, price)
        else:
            price = None

        return price

    def _parse_brand(self, response):
        brand = response.xpath("//span[@itemprop='brand']/text()").extract()
        return brand[0] if brand else None
    def _parse_currency(self, response):
        currency = response.xpath("//meta[@itemprop='priceCurrency']/@content").extract()
        return currency[0] if currency else 'USD'

    def _parse_image_url(self, response):
        image_url = response.xpath(
                '//img[@class="largeImage productImage"]/@data-src'
            ).extract()

        return image_url[0] if image_url else None

    def _parse_description(self, response):
        description = response.xpath(
                '//div[@class="description-wrap"]/p/node()[normalize-space()]'
            ).extract()

        if description:
            description = ''.join(description)
        else:
            description = None

        return description

    def _parse_categories(self, response):
        categories = response.xpath(
            '//nav[@class="breadcrumbs"]//a//span/text()'
        ).extract()

        return categories

    def _parse_sku(self, response):
        sku = response.xpath('//i[@class="product-sku"]//span/text()').extract()

        if sku:
            sku = sku[0]
        else:
            sku = None

        return sku

    def _parse_model(self, response):
        model = response.xpath('//i[@itemprop="mpn"]//span/text()').extract()
        return model[0] if model else None

    def _parse_resellerId(self, response):
        reseller_id = response.xpath('//i[@itemprop="productID"]//span/text()').extract()
        return reseller_id[0] if reseller_id else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        return not bool(response.xpath('//span[@class="stock-in stock"]'))

    @staticmethod
    def _parse_avaliable_online(response):
        return bool(response.xpath('//form[@itemprop="offers"]'))

    @staticmethod
    def _parse_no_longer_available(response):
        return bool(response.xpath('//div[contains(@class, "item-not-avilable")]'))

    def _scrape_total_matches(self, response):

        total_matches = response.xpath('//span[@class="index-count-total"]/text()').extract()

        if total_matches:
            total_matches = int(total_matches[0])
        else:
            total_matches = None

        return total_matches

    def _scrape_product_links(self, response):
        st = response.meta.get('search_term')
        self.product_links = response.xpath('//div[@class="item"]//a[@class="tappable-item"]/@href').extract()

        if self.product_links:
            for link in self.product_links:
                prod_item = SiteProductItem()
                req = Request(
                    url=link,
                    headers=self.HEADERS,
                    callback=self.parse_product,
                    meta={
                        'product': prod_item,
                        'search_term': st,
                        'remaining': self.quantity
                    },
                    dont_filter=True
                )
                yield req, prod_item
        else:
            return

    def _scrape_next_results_page_link(self, response):
        st = response.meta.get('search_term')
        if not self.product_links:
            return

        next_page = response.xpath('//div[@class="pagination"]//a[@class="page-next page-control"]/@href').extract()
        if next_page:
            return next_page[0]

        if next_page:
            return Request(
                next_page[0],
                meta={
                    'search_term': st,
                    'remaining': self.quantity
                },
                headers=self.headers,
                dont_filter=True
            )
