from __future__ import division, absolute_import, unicode_literals

import json
import re
import string
import urlparse

from scrapy.http import Request
from scrapy.log import DEBUG
from scrapy.selector import Selector

from product_ranking.items import Price
from product_ranking.items import SiteProductItem, RelatedProduct, BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX
from product_ranking.spiders import cond_set, cond_set_value


LEVEL_MAX = 4       # Max deep of upc lookup


class KatespadeProductsSpider(BaseProductsSpider):
    name = 'katespade_products'
    allowed_domains = ["katespade.com", "katespade.ugc.bazaarvoice.com"]
    start_urls = []
    SEARCH_URL = (
        "http://www.katespade.com/on/demandware.store/Sites-Shop-Site"
        "/en_US/Search-Show?q={search_term}&start=0&sz=550&format=ajax"
    )

    SORT_MODES = {
        "default": "",
        "pricehl": "&srule=price-high-to-low",
        "pricelh": "&srule=price-low-to-high",
        "justadded": "&srule=just-added"
    }

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode:
            if sort_mode not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
                sort_mode = 'relevance'
            self.SEARCH_URL += self.SORT_MODES[sort_mode]
        super(KatespadeProductsSpider, self).__init__(
            None,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)
        product = response.meta['product']

        cond_set(product, 'title', response.xpath(
            "//div[@id='product-content']"
            "/h1[@itemprop='name']/text() | "
            "//div[contains(@class, 'product-name')]"
            "/a[contains(@class, 'item-name')]/text()"
        ).extract(),
            conv=string.strip)

        price = response.xpath(
            "//div[@id='product-content']"
            "/div[contains(@class,'product-price')]"
            "/span[@class='price-sales']/text() | "
            "//div[contains(@class, 'product-price')]"
            "/span[contains(@class, 'price-sales')] |"
            "//div[contains(@class, 'product-price ')]/div/text()"
        ).re(FLOATING_POINT_RGEX)
        if price:
            product['price'] = Price(
                price=price[0], priceCurrency='USD')

        cond_set_value(product, 'brand', 'kate spade new york')

        cond_set(product, 'upc', response.xpath(
            "//form[contains(@class,'pdpForm')]/fieldset"
            "/input[@name='pid']/@value").extract())

        cond_set(product, 'image_url', response.xpath(
            "//div[@class='product-primary-image']/img/@src").extract())

        cond_set_value(product, 'locale', "en-US")

        reseller_id_regex = "/([A-Z0-9]+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        cond_set(product, 'description', response.xpath(
            "//div[@itemprop='description']").extract())

        recoms = response.xpath("//div[@id='recommendations']/a")
        related = []
        for iproduct in recoms:
            title = iproduct.xpath("@title").extract()
            if title:
                title = title[0]
                href = iproduct.xpath("@href").extract()
                if href:
                    href = href[0]
                    related.append(RelatedProduct(title, href))
        if related:
            product['related_products'] = {'recommended': related}

        pname = response.xpath(
            "//script[contains(text(),'getRRDisplayCode')]").re(
            r'configData\.productId = "(.*)";')
        if pname:
            pname = pname[0]
        else:
            pname = response.xpath('//input[@id="pid"]/@value').extract()
            if pname:
                pname = pname[0]

        script = response.xpath(
            "//script[contains(@src,'bazaarvoice')]/@src").extract()
        if script:
            script = script[0]
            url_parts = urlparse.urlsplit(script)
            prefix = url_parts.path.split("/")[2]
            purl = "/".join(["", prefix])
            url_parts = url_parts._replace(path=purl)
            new_path = urlparse.urlunsplit(url_parts)
            url = new_path + "/" + pname + "/reviews.djs?format=embeddedhtml"

            new_meta = response.meta.copy()
            new_meta['handle_httpstatus_list'] = [404]
            new_meta['product_response'] = response
            return Request(
                url=url, callback=self._extract_reviews,
                meta=new_meta)
        return self._product_or_upcreq(response)

    def _product_or_upcreq(self, response):
        product = response.meta['product']
        upc = product.get('upc', '')
        if not upc.isdigit():
            req = self._extract_upc_callback(response)
            return req
        return product

    def _extract_reviews(self, response):
        if response.status != 200:
            return self._product_or_upcreq(response)
        product = response.meta['product']
        text = response.body_as_unicode().encode('utf-8')
        jstext = re.search("var materials=(.*)\,\s+initializers=", text, re.S)
        if jstext:
            jstext = jstext.group(1)
            jsdata = json.loads(jstext)
            source = jsdata['BVRRRatingSummarySourceID']
            sel = Selector(text=source)
            buyer_reviews = self._extract_ratings(sel)
            if buyer_reviews:
                cond_set_value(product, 'buyer_reviews', buyer_reviews)
            else:
                cond_set_value(product, 'buyer_reviews', ZERO_REVIEWS_VALUE)
        return self._product_or_upcreq(response)

    def _extract_upc_callback(self, response):
        response = response.meta.get('product_response', response)
        product = response.meta['product']
        upc = response.xpath(
            "//form[contains(@class,'pdpForm')]"
            "/fieldset"
            "/input[@name='pid']/@value").extract()
        if upc:
            upc = upc[0]
            if upc.isdigit():
                product['upc'] = upc
                return product
        link = self._extract_upc(response)
        if not link:
            return product
        return Request(
            link,
            meta=response.meta.copy(),
            callback=self._extract_upc_callback)

    def _extract_upc(sef, response):
        level = response.meta.get("variations-level", 0)

        # TODO: li @class !contains 'unselectable'
        variations = response.xpath(
            "//div[@class='product-variations']"
            "/ul/li/div[@class='value']")
        iv = variations[level]
        level += 1
        if level > LEVEL_MAX:
            return
        response.meta['variations-level'] = level
        href = iv.xpath("ul/li/a/@href").extract()
        if href:
            return href[0]

    def _extract_ratings(self, sel):
        avrg = sel.xpath(
            "//span[contains(@class,'RatingNumber') "
            "and contains(@class,'value')]/text()").extract()
        if avrg:
            try:
                avrg = float(avrg[0])
            except ValueError:
                return
        rcount = sel.xpath(
            "//span[contains(@class,'BVRRCount')]"
            "/span[contains(@class,'BVRRNumber')]/text()").extract()
        if rcount:
            try:
                rcount = int(rcount[0])
            except ValueError:
                return
        hist = sel.xpath(
            "//div[contains(@class,'BVRRHistogramContent')]"
            "/div[contains(@class,'BVRRHistogramBarRow')]")
        ratings = {}
        for h in hist:
            label = h.xpath(
                "span/span[@class='BVRRHistStarLabelText']"
                "/text()").re("(\d) Star")
            if label:
                label = label[0]
                hcount = h.xpath(
                    "span[@class='BVRRHistAbsLabel']"
                    "/text()").extract()
                if hcount:
                    try:
                        hcount = int(hcount[0])
                    except ValueError:
                        return
                    ratings[label] = hcount
        if not rcount:
            return ZERO_REVIEWS_VALUE
        return BuyerReviews(
            num_of_reviews=rcount,
            average_rating=avrg,
            rating_by_star=ratings)

    def _check_alert(self, response):
        alert = response.xpath(
            "//div[@id='primary' and @class='no-hits']"
            "/div[@class='section-header']"
            "/div[@class='noresults']").extract()
        return alert

    def _scrape_total_matches(self, response):
        if self._check_alert(response):
            return 0
        total = response.xpath(
            "//ul[@class='tabs-menu']"
            "/li/a[@id='pRoduct']"
            "/text()").re("PRODUCTS \((\d+)\)")
        if total:
            try:
                return int(total[0])
            except ValueError:
                return
        return 0

    def _scrape_product_links(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)

        if self._check_alert(response):
            return
        links = response.xpath(
            "//ul[@id='search-result-items']"
            "/li[contains(@class,'grid-tile')]"
            "/div/div[@class='product-name']"
            "/h2/a[@class='name-link']/@href").extract()

        if not links:
            self.log("Found no product links.", DEBUG)
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        pass
