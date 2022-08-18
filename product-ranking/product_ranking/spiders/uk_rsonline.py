# -*- coding: utf-8 -*-


import re
import urlparse
import time

from scrapy import Request

from product_ranking.items import RelatedProduct, BuyerReviews, Price, \
    SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import cond_set, cond_set_value, \
    cond_replace_value, dump_url_to_file
from product_ranking.spiders.contrib.product_spider import ProductsSpider


def _itemprop(response, prop, extract=True):
    if extract:
        return response.css('[itemprop="%s"]::text' % prop).extract()
    else:
        return response.css('[itemprop="%s"]' % prop)


USER_AGENT_LIST = [
    'Mozilla/5.0 (Windows NT 6.1; rv:27.3) Gecko/20130101 Firefox/27.3',
    'Mozilla/5.0 (X11; OpenBSD amd64; rv:28.0) Gecko/20100101 Firefox/28.0',
    'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:25.0) Gecko/20100101 Firefox/29.0',
    'Mozilla/5.0 (Windows NT 5.1; rv:31.0) Gecko/20100101 Firefox/31.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10; rv:33.0) Gecko/20100101 Firefox/33.0',
    'Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0',
    'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2226.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2224.3 Safari/537.36',
    'Mozilla/5.0 (X11; OpenBSD i386) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36',
    'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.3319.102 Safari/537.36'
]

class UkRsOnlineProductsSpider(ProductsSpider):
    """ uk.rs-online.com product ranking spider

    There are following caveats:

    - sorting not implemented because of different sorting mechanism for different search terms
    - upc, model, is_in_store_only, limited_stock, sponsored_links fields are not scraped
    """

    name = 'uk_rsonline_products'

    allowed_domains = [
        'uk.rs-online.com'
    ]

    SEARCH_URL = "http://uk.rs-online.com/web/c/?searchTerm={search_term}" \
                 "&sra=oss&r=t&vn=1"

    user_agent = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:35.0) Gecko'
                  '/20100101 Firefox/35.0')

    download_delay = 5
    enable_cookies = False

    ERR_URL = 'http://uk.rs-online.com/web/app/error'
    ERR_MSG = 'Your request could not be completed at this time'
    ERR_RETRY_DELAY = 2
    ERR_RETRIES = 10

    def _is_product_page(self, response):
        return response.url.startswith('http://uk.rs-online.com/web/p')

    def _total_matches_from_html(self, response):
        if self._is_product_page(response):
            return 1
        matches = response.css('.viewProdDiv::text').re('f ([\d, ]+) products')
        return int(re.sub('[, ]', '', matches[0])) if matches else 0

    def _scrape_results_per_page(self, response):
        results = response.css('.defaultItem div::text').re('\d+')
        return int(results[0]) if results else None

    def _scrape_next_results_page_link(self, response):
        url = response.css('.checkoutPaginationContent noscript a::attr(href)')
        return url[-2].extract() if len(url) > 1 else None

    def _fetch_product_boxes(self, response):
        if self._is_product_page(response):
            return [response]
        return response.css('.resultRow')

    def _scrape_product_links(self, response):
        for box in self._fetch_product_boxes(response):
            url = urlparse.urljoin(response.url, self._link_from_box(box))
            product = SiteProductItem()
            self._populate_from_box(response, box, product)
            if not product.get('brand', None):
                dump_url_to_file(response.url)
            meta = response.meta.copy()
            meta['product'] = product
            user_agent = USER_AGENT_LIST.pop(0)
            USER_AGENT_LIST.append(user_agent)
            request = Request(url, callback=self.parse_product, meta=meta)
            request.headers.setdefault('User-Agent', user_agent)
            yield request, product

    def _link_from_box(self, box):
        return box.css('.srDescDiv a::attr(href), '
                       '.tnProdDesc::attr(href)')[0].extract()

    def parse_product(self, response):
        is_err_page = response.url.startswith(self.ERR_URL)
        if is_err_page or response.css('.red').re(self.ERR_MSG):
            retry_num = response.meta.get("ERR_RETRY_NUM", 1)
            if retry_num < self.ERR_RETRIES:
                self.log(
                    'Error detected, %i seconds delay (%i/%i retries) %s' %
                    (self.ERR_RETRY_DELAY, retry_num, self.ERR_RETRIES,
                     response.meta['product']['url']))
                time.sleep(self.ERR_RETRY_DELAY)
                response.meta['ERR_RETRY_NUM'] = retry_num + 1
                user_agent = USER_AGENT_LIST.pop(0)
                USER_AGENT_LIST.append(user_agent)
                request = Request(response.meta['product']['url'],
                                  callback=self.parse_product,
                                  meta=response.meta, dont_filter=True)
                request.headers.setdefault('User-Agent', user_agent)
                return [request]
            else:
                self.log('Product page contains an error')
        return list(
            super(UkRsOnlineProductsSpider, self).parse_product(response))

    def _populate_from_box(self, response, box, product):
        if self._is_product_page(response):
            self._populate_from_html(response, product)
            cond_set_value(product, 'is_single_result', True)
            cond_set_value(product, 'url', response.url)
        else:
            cond_set(product, 'price', box.css('.price::text').re(
                u'\u00a3([\d, .]+)'))
            cond_set(product, 'title', box.css('.tnProdDesc::text').extract(),
                     unicode.strip)
            xpath = '//li/span[text()="Brand"]/../a/text()'
            cond_set(product, 'brand', box.xpath(xpath).extract(),
                     unicode.strip)

    def _populate_from_html(self, response, product):
        cond_set(product, 'price', response.css('.price span::text').re(
            u'\u00a3([\d, .]+)'))
        cond_set(product, 'title', _itemprop(response, 'model'), unicode.strip)
        cond_set(product, 'brand',
                 _itemprop(_itemprop(response, 'brand', False), 'name'),
                 unicode.strip)
        cond_set(product, 'image_url', _itemprop(response, 'image', False)
                 .css('img::attr(src)').extract())
        image = product.get('image_url')
        if image and image.endswith('noImage.gif'):
            del (product['image_url'])
        cond_set_value(product, 'is_out_of_stock',
                       response.css('.stockMessaging::text').re(
                           'out of stock|Discontinued product'),
                       bool)

        regex = "\/([0-9]+)[\/\?]"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        details = response.css('.prodDetailsContainer').xpath(
            'node()[normalize-space()]')
        details = [d.extract() for d in details if not d.css('form')]
        if details:
            cond_set_value(product, 'description', details, conv=''.join)
        self._populate_related_products(response, product)
        self._populate_buyer_reviews(response, product)
        price = product.get('price', None)
        if price == 0:
            del (product['price'])
        elif price:
            price = re.sub(', ', '', price)
            cond_replace_value(product, 'price', Price(priceCurrency='GBP',
                                                       price=price))

    def _populate_related_products(self, response, product):
        related_products = {}
        for panel in response.css('.relProPanel'):
            relation = panel.css('h2::text').extract()[0]
            products = []
            for link in panel.css('a.productDesc'):
                url = urlparse.urljoin(response.url, link.css(
                    '::attr(href)')[0].extract())
                title = link.css('::text')[0].extract()
                products.append(RelatedProduct(title=title, url=url))
            related_products[relation] = products
        cond_set_value(product, 'related_products', related_products)

    def _populate_buyer_reviews(self, response, product):
        regexp = 'http://img-europe.electrocomponents.com/siteImages/browse' \
                 '/stars-(\d+-\d+).gif'
        stars = response.css('img::attr(src)').re(regexp)
        if not stars:
            product['buyer_reviews'] = ZERO_REVIEWS_VALUE
            return
        stars.pop(0)
        stars = map(float, (s.replace('-', '.') for s in stars))
        by_star = {star: stars.count(star) for star in stars}
        total = len(stars)
        average = sum(stars) / total
        cond_set_value(product, 'buyer_reviews',
                       BuyerReviews(num_of_reviews=total,
                                    average_rating=average,
                                    rating_by_star=by_star))

    def _parse_single_product(self, response):
        return self.parse_product(response)