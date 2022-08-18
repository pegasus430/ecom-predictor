from __future__ import division, absolute_import, unicode_literals

import re
import json
import traceback
from scrapy.conf import settings
from urllib import unquote, quote_plus
from urlparse import urljoin, urlparse

from scrapy import Field, Request
from scrapy.log import ERROR

from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.items import SiteProductItem


class GoogleKeywordItem(SiteProductItem):
    google_keyword = Field()
    google_url = Field()
    google_rank = Field()
    google_search_volume = Field()


class GoogleKeywordSpider(BaseProductsSpider):
    name = 'google_keyword_products'
    allowed_domains = ['google.com']

    SEARCH_URL = u'http://api.grepwords.com/related?apikey=7727a2b17dd841d&results=1&start=1&q={search_term}'
    GOOGLE_URL = 'https://www.google.com/search?gl=us&hl=en&num=100&pws=0&filter=0&safe=images&q={keyword}'

    def __init__(self, filter_domain=None, filter_url=None, *args, **kwargs):
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                          'Chrome/57.0.2987.133 Safari/537.36'
        if filter_domain:
            filter_domain = filter_domain.lower()

        self.filter_domain = filter_domain
        self.filter_url = filter_url

        if self.filter_domain or self.filter_url:
            kwargs.pop('quantity', '')

        super(GoogleKeywordSpider, self).__init__(*args, **kwargs)
        settings.overrides['USE_PROXIES'] = True
        settings.overrides['COOKIES_ENABLED'] = False
        settings.overrides['REFERER_ENABLED'] = False

        DEFAULT_REQUEST_HEADERS = settings.get('DEFAULT_REQUEST_HEADERS')
        DEFAULT_REQUEST_HEADERS['Connection'] = 'close'

        DOWNLOADER_MIDDLEWARES = settings.get('DOWNLOADER_MIDDLEWARES')
        DOWNLOADER_MIDDLEWARES['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2

    def _scrape_total_matches(self, response):
        pass

    def _scrape_next_results_page_link(self, response):
        pass

    def start_requests(self):
        for item in super(GoogleKeywordSpider, self).start_requests():
            yield item.replace(callback=self.parse_search_volume, dont_filter=True)

    def parse_search_volume(self, response):
        item = GoogleKeywordItem()
        search_volume = 10

        try:
            data = json.loads(response.body)

            if data:
                search_volume = data[0].get('gms', 10)
        except:
            self.log(traceback.format_exc(), ERROR)

        item['google_search_volume'] = search_volume

        meta = response.meta
        meta['item'] = item
        meta['dont_redirect'] = True
        meta['handle_httpstatus_list'] = [302, 503]

        search_term = meta.get('search_term')
        if search_term:
            url = self.GOOGLE_URL.format(keyword=quote_plus(search_term.encode('utf-8')))

            yield Request(url, meta=meta)

    def parse(self, response):
        # TODO implement this as custom retry middleware
        if response.status == 503 or response.status == 302 \
                and '/sorry/' in response.headers.get('Location', '') and response.meta.get("retries_number", 0) < 15:
            self.log("Redirecting to captcha, try with proxy again")
            retried_req = response.request.replace(dont_filter=True)
            if not retried_req.meta.get("retries_number"):
                retried_req.meta["retries_number"] = 0
            retried_req.meta["retries_number"] += 1
            yield retried_req
        elif response.status == 302 and 'Location' in response.headers and response.meta.get("retries_number", 0) < 15:
            redirected_url = urljoin(response.url, response.headers.get('Location'))
            self.log("Redirecting to {} from {}".format(redirected_url, response.url))
            redirected = response.request.replace(url=redirected_url, dont_filter=True)
            if not redirected.meta.get("retries_number"):
                redirected.meta["retries_number"] = 0
            redirected.meta["retries_number"] += 1
            yield redirected
        else:
            for item in super(GoogleKeywordSpider, self).parse(response):
                yield item

    def _scrape_product_links(self, response):
        links = response.xpath(".//*[@class='g']")

        if links:
            rank = 1

            for link in links:
                url = link.xpath(".//h3/a/@data-href").extract()
                if len(url) == 0:
                    url = link.xpath(".//h3/a/@href").extract()

                if url:
                    url = url[0]
                    url_extract = re.findall(r'[q|url]=([^&]*)&', url)

                    if len(url_extract) > 0 and url_extract[0] \
                            and urlparse(unquote(unquote(url_extract[0]))).scheme:
                        url = url_extract[0]

                    url = unquote(unquote(url))  # double unquote
                    url = urljoin(response.url, url)

                    item = GoogleKeywordItem(response.meta['item'])

                    search_term = response.meta.get('search_term', '')
                    item['google_keyword'] = search_term
                    item['google_url'] = url
                    item['google_rank'] = rank

                    if self.filter_domain:
                        url_parts = urlparse(url)

                        if self.filter_domain in url_parts.netloc:
                            yield None, item
                    elif self.filter_url:
                        url_parts = urlparse(url)
                        filter_url_parts = urlparse(self.filter_url)

                        if url_parts.netloc == filter_url_parts.netloc \
                                and url_parts.path == filter_url_parts.path:
                            yield None, item
                    else:
                        yield None, item

                    rank += 1
                else:
                    continue
