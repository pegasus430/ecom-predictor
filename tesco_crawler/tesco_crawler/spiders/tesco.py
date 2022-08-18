import json
import re

from scrapy.log import (ERROR, INFO)
from scrapy.http import Request
from scrapy.selector import Selector
from scrapy.spider import Spider

from tesco_crawler.items import BazaarVoiceReviewsItem


class TescoReviewSpider(Spider):
    name = 'tesco_review'
    allowed_domains = ["tesco.com", "bazaarvoice.com"]
    start_urls = []

    _BV_TESCO_API_CONF_URL = \
        "http://display.bazaarvoice.com/static/Tesco/bvapi.js"

    _EXTRACT_REVIEWS_URL_RE = re.compile(
        r'prefetchConfigs:\s*\[\s*\{\s*url\s*:\s*"//([^"]+)', re.MULTILINE)

    def __init__(self, start_url=None, start_urls_fn=None, *args, **kwargs):
        super(TescoReviewSpider, self).__init__(*args, **kwargs)

        if start_url is not None:
            self.start_urls = [start_url]

        if start_urls_fn is not None:
            with open(start_urls_fn) as start_urls_f:
                self.start_urls = [url.strip() for url in start_urls_f]

        self.log("Created with urls: " + ', '.join(self.start_urls), INFO)

    def parse(self, response):
        sel = Selector(response)

        # Scrape BV configuration.
        prod_id, = sel.css('.details-container > script').re(
            r"productID\s*=\s*'([\d\w-]+)'")
        self.log("Processing product '%s'." % prod_id, INFO)

        r = Request(self._BV_TESCO_API_CONF_URL,
                    callback=self.parse_bv_conf)
        r.meta['product_id'] = prod_id
        return r

    def parse_bv_conf(self, response):
        prod_id = response.meta['product_id']

        # Parse review URL.
        m = self._EXTRACT_REVIEWS_URL_RE.search(response.body)
        if m is None:
            self.log(
                "Failed to parse URL from tesco.com's BV config URL for "
                "product '%s'." % prod_id, ERROR)
            req = None
        else:
            self.log("Found config for product '%s'." % prod_id, INFO)

            url_template, = m.groups()
            url = 'http://' \
                + url_template.replace('___PRODUCTIDTOKEN___', prod_id)

            req = Request(url, callback=self.parse_bv)
        return req

    def parse_bv(self, response):
        """Parses a BazaarVoice Json response."""
        responses = json.loads(response.body)
        review = BazaarVoiceReviewsItem(
            bv_client="tesco",
            data=responses['BatchedResults']['q1']['Includes']
        )

        self.log("Got reviews for products: %s" % ', '.join(
            review['data']['Products'].keys()), INFO)

        return review
