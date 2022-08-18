# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import re
import urllib
import urlparse

from scrapy.log import ERROR
from scrapy.http.cookies import CookieJar
from scrapy.http import Request

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, Price, BuyerReviews, RelatedProduct
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    FLOATING_POINT_RGEX, cond_set_value
from product_ranking.settings import ZERO_REVIEWS_VALUE



# scrapy crawl amazoncouk_products -a searchterms_str="iPhone"

currencys = {"£": "GBP","€": "EUR","$": "USD"}

is_empty = lambda x: x[0] if x else ""

user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64)) AppleWebKit/537.36" \
    " (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"


class EllisbrighamProductsSpider(BaseProductsSpider):
    name = "ellisbrigham_products"
    allowed_domains = ["www.ellis-brigham.com"]
    start_urls = []

    add_url = "http://www.ellis-brigham.com"
    sort_url = "01"
    
    SEARCH_URL = "http://www.ellis-brigham.com/search?s={search_term}"

    SORT_MODES = {
        "Most relevant": "01",
        "Most recent": "02",
        "Price (High - Low)": "03",
        "Price (Low - High)": "04",
        "Alphabetically": "05",
    }

    def __init__(self, *args, **kwargs):
        if "sort_modes" in kwargs:
            self.sort_url = self.SORT_MODES[kwargs["sort_modes"]]
        super(EllisbrighamProductsSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        for st in self.searchterms:
            yield Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                meta={'search_term': st, 'remaining': self.quantity},
                callback=self.set_sort,
                dont_filter=True,
            )

    def set_sort(self, response):
        EVT = "ctl00$ctl00$ContentPlaceHolder1$SearchResults_1$rptSort$ctl%s$lbtnSortBy" % (self.sort_url,)
        CTL = "ctl00$ctl00$ContentPlaceHolder1$SearchResults_1$upSearch|"
        data = urllib.urlencode(
            self.collect_data_for_request(response, EVT, CTL))
        return self.compose_request(response, self.scrape_requests, data)

    def scrape_requests(self, response):
        cookieJar = response.meta.setdefault('cookiejar', CookieJar())
        self.coockies = cookieJar.extract_cookies(response, response.request)
        self.cookie = {}
        for c in cookieJar:
            self.cookie[c.name] = c.value

        for req in super(EllisbrighamProductsSpider, self).start_requests():
            req.cookies = self.cookie
            yield req

    def parse_product(self, response):
        prod = response.meta['product']

        title = response.xpath(
            '//div[contains(@class, "product-detail")]/h1/text()').extract()
        if title:
            cond_set(prod, 'title', (title[0].strip(),))
        brand = response.xpath('//title/text()').extract()
        if brand:
            cond_set(prod, 'brand',
                     (guess_brand_from_first_words(brand[0].strip()),))

        xpath = '//div[@class="product-detail"]/h2/span[@class="price"]/text()'
        price = response.xpath(xpath).extract()
        if price:
            price = price[0].strip().replace(',', '').strip()
            currency = is_empty(re.findall("£|€|$", price[0]))
            price = re.findall("\d+.{0,1}\d+", price)
            if currency not in currencys:
                 self.log('Currency symbol not recognized: %s' % response.url,
                          level=ERROR)
            else:
                prod['price'] = Price(
                    priceCurrency=currencys[currency],
                    price=price[0]
                )

        xpath = '//div[@class="product-detail-zoom"]/a/@href'
        image_url = response.xpath(xpath).extract()
        if image_url:
            image_url = "http:" + image_url[0]
        else:
            xpath = '//div[@class="product-detail-zoom"]/img/@src'
            image_url = response.xpath(xpath).extract()
            image_url = "http:" + image_url[0]
        cond_set(prod, "image_url", (image_url,))

        xpath = '//div[@class="product-detail"]/p/text()'
        desc = response.xpath(xpath).extract()
        if desc:
            cond_set(prod, 'description', (desc[0].strip(),))

        reviews = response.xpath('//span[@class="rating"]')
        average_rating = reviews.xpath('img/@src').extract()
        if average_rating:
            average_rating = re.findall("star-(\d+)", average_rating[0])
        num_of_reviews = reviews.xpath('text()').re(FLOATING_POINT_RGEX)
        css = 'img[id*=_rptReviews_imgStarImage]::attr(src)'
        by_star = response.css(css).re('/img/rating/star-(\d+).png')
        by_star = {int(stars): by_star.count(stars) for stars in by_star}
        if int(is_empty(num_of_reviews)) or float(is_empty(average_rating)):
            prod["buyer_reviews"] = BuyerReviews(
                num_of_reviews=int(is_empty(num_of_reviews)),
                average_rating=float(is_empty(average_rating)),
                rating_by_star=by_star
            )
        else:
            prod["buyer_reviews"] = ZERO_REVIEWS_VALUE

        prod["locale"] = "en_GB"
        prod['url'] = response.url

        reseller_id_regex = "\/(\d+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(prod, 'reseller_id', reseller_id)
        self._populate_related_products(response, prod)
        return prod

    def _scrape_total_matches(self, response):
        xpath = '//li[@class="search-results"]/text()'
        total_matches = response.xpath(xpath).re(FLOATING_POINT_RGEX)
        if total_matches:
            return int(total_matches[0])    
        return 0

    def _scrape_product_links(self, response):
        boxes = response.css('.product-description')
        for box in boxes:
            product = SiteProductItem()
            url = box.xpath('h3/a/@href').extract()
            cond_set(product, 'brand', box.xpath('p/text()').extract())
            yield url[0], product

    def _scrape_next_results_page_link(self, response):
        if not self._scrape_total_matches(response):
            return None
        xpath = '//div[@class="pagination-right"]/a[last()]/@href'
        if response.xpath(xpath).extract():
            EVT = "ctl00$ctl00$ContentPlaceHolder1$SearchResults_1$PagingCtrl1$lbtnNext"
            CTL = "ctl00$ctl00$ContentPlaceHolder1$SearchResults_1$upnlFilter|"
            data = urllib.urlencode(self.collect_data_for_request(response, EVT, CTL))
            return self.compose_request(response, self.parse, data)
        return None

    def collect_data_for_request(self, response, EVT, CTL):
        VS = is_empty(
            response.xpath('//input[@id="__VIEWSTATE"]/@value').extract())
        VSG = is_empty(response.xpath(
            '//input[@id="__VIEWSTATEGENERATOR"]/@value').extract())

        if not VS:
            VS = is_empty(re.findall("__VIEWSTATE\|([^\|]*)", response.body))
            VSG = is_empty(
                re.findall("__VIEWSTATEGENERATOR\|([^\|]*)", response.body))

        data = {
            "__EVENTTARGET": EVT,
            "ctl00$ctl00$sm": CTL+EVT,
            "__VIEWSTATE": VS,
            "__VIEWSTATEGENERATOR": VSG,
            "ctl00$ctl00$HeaderNavigation1$txtSearchText": "",
            "__ASYNCPOST": "true",
        }

        return data

    def compose_request(self, response, callback1, data):
        return Request(
                response.url,
                meta=response.meta,
                method="POST",
                headers={
                    "Content-Type":
                        "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": user_agent,
                },
                body=data,
                callback=callback1,
                dont_filter=True,
            )

    def _populate_related_products(self, response, product):
        rp_placeholders = response.css('li::attr(id)').re(
            'ContentPlaceHolder\d+_RecommendedSummary\d+')
        related_products = {}
        for placeholder in rp_placeholders:
            rel_cls = "%s_RecommendedListItem" % placeholder
            xpath = '//li[contains(@id, "%s")]/h2/text()' % rel_cls
            relation = u''.join(response.xpath(xpath).extract()).strip()
            prod_cls = '%s_rptRecommended_hlProductLink' % placeholder
            products = []
            for prod_elt in response.css('a[id*=%s]' % prod_cls):
                title = prod_elt.css('::text').extract()
                url = prod_elt.css('::attr(href)').extract()
                if not (title and url):
                    continue
                title = title[0]
                url = url[0]
                url = urlparse.urljoin(response.url, url)
                products.append(RelatedProduct(title=title, url=url))
            related_products[relation] = products
        cond_set_value(product, 'related_products', related_products)