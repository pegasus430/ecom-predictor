# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import urlparse
import re
import urllib

from scrapy import Selector
from scrapy.http import Request
from scrapy.log import DEBUG

from product_ranking.items import Price, BuyerReviews
from product_ranking.items import SiteProductItem, RelatedProduct
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX
from product_ranking.spiders import cond_set, cond_set_value, dump_url_to_file


class PcworldcoukProductsSpider(BaseProductsSpider):
    name = 'pcworldcouk_products'
    allowed_domains = ["pcworld.co.uk", "recs.richrelevance.com", 'mark.reevoo.com']
    start_urls = []
    SEARCH_URL_TEMPLATE = (
        "http://www.pcworld.co.uk/gbuk/search-keywords"
        "/xx_xx_xx_xx_xx/{search_term}/%sxx-criteria.html")
    SCRIPT_URL = "http://recs.richrelevance.com/rrserver/p13n_generated.js"
    DO_DESCRIPTION = True

    SORT_MODES = {
        "relevance": "",
        "brandaz": "1_20/brand-asc/",
        "brandza": "1_20/brand-desc/",
        "pricelh": "1_20/price-asc/",
        "pricehl": "1_20/price-desc/",
        "rating":  "1_20/rating-desc/"
    }

    def __init__(self, sort_mode=None, *args, **kwargs):
        if 'searchterms_str' in kwargs:
            kwargs['searchterms_str'] = urllib.quote(kwargs['searchterms_str'])
        if sort_mode:
            if sort_mode not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
                sort_mode = 'relevance'
        else:
            sort_mode = 'relevance'
        self.SEARCH_URL = self.SEARCH_URL_TEMPLATE % self.SORT_MODES[sort_mode]
        formatter = None
        super(PcworldcoukProductsSpider, self).__init__(
            formatter,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def parse_product(self, response):
        product = response.meta['product']

        cond_set(product, 'title', response.xpath(
            "//section[@itemscope]/h1"
            "/span[@itemprop='name']/text()").extract())

        cond_set(product, 'brand', response.xpath(
            "//section[@itemscope]/h1"
            "/span[@itemprop='brand']/text()").extract())

        if not product.get('brand', None):
            dump_url_to_file(response.url)

        cond_set(product, 'upc', response.xpath(
            "//section[@itemscope]/meta[@itemprop='identifier']"
            "/@content").extract())

        price = response.xpath(
            "//section[@itemscope]/div[contains(@class,'productDetail')]"
            "/section[contains(@class,'description')]"
            "/div/div[contains(@class,'productPrices')]"
            "/span[@itemprop='price']/ins/text()").re(FLOATING_POINT_RGEX)

        if price:
            product['price'] = Price(
                price=price[0], priceCurrency='GBP')

        cond_set(product, 'image_url', response.xpath(
            "//section[@itemscope]/descendant::section[@class='productMedias']"
            "/div[@id='currentView']/a/img/@src").extract())

        regex = "(\d+)-pdt"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        if self.DO_DESCRIPTION:
            cond_set(product, 'description', response.xpath(
                "//section[@id='longDesc']").extract())

        cond_set_value(product, 'locale', "en-GB")

        out_of_stock = response.xpath(
            "//div[contains(@class,'productDetail')]"
            "/section[@class='col3']/div[@class='nested']"
            "/strong/text()").re(r"Out of stock")
        if out_of_stock:
            product['is_out_of_stock'] = True

        # review = response.xpath(
        #     "//div[contains(@class,'productDetail')]"
        #     "/section[@class='col3']/p[@id='reviews']"
        #     "/a/@href"
        #     ).extract()

        payload = self._extract_rr_parms(response)
        productid = payload['p']
        product['upc'] = productid

        review_url = (
            'http://mark.reevoo.com/reevoomark/en-GB/product?sku={sku}'
            '&trkref=PCG').format(sku=productid)
        new_meta = response.meta.copy()
        new_meta['handle_httpstatus_list'] = [404]
        reevoo_request = Request(
            url=review_url,
            callback=self._parse_reevoo,
            meta=new_meta)
        response.meta['reevoo'] = reevoo_request

        if payload:
            new_meta = response.meta.copy()
            rr_url = urlparse.urljoin(
                self.SCRIPT_URL, "?" + urllib.urlencode(payload))
            return Request(
                rr_url,
                self._parse_rr_json,
                meta=new_meta)
        else:
            self.log("No {rr} payload at %s" % response.url, DEBUG)

        return product

    def _extract_rr_parms(self, response):
        rscript = response.xpath(
            "//script[contains(text(),'R3_COMMON')]").extract()
        if rscript:
            rscript = rscript[0]
        else:
            self.log(
                "No {rr} scrtipt with R3_COMMON at %s" % response.url, DEBUG)
            return
        m = re.match(r".*R3_COMMON\.setApiKey\('(\S*)'\);", rscript,
                     re.DOTALL)
        if m:
            apikey = m.group(1)
        else:
            self.log("No {rr} apikey at %s" % response.url, DEBUG)
            return

        m = re.match(r".*R3_ITEM\.setId\('(\S*)'\);", rscript, re.DOTALL)
        if m:
            productid = m.group(1)
        else:
            self.log("No {rr} productid at %s" % response.url, DEBUG)
            return

        m = re.findall(
            r"R3_COMMON\.addPlacementType\(([^\)]*)\);",
            rscript, re.DOTALL + re.M)
        pt = ""
        if m:
            pt = [x.strip("'") for x in m]
            pt = "".join("|" + x for x in pt)

        m = re.findall(
            r"R3_ITEM\.addCategory\((.*)\,\s+(.*)\);",
            rscript, re.DOTALL + re.M)
        cs = ""
        if m:
            csr = []
            for im in m:
                im = [x.strip("'") for x in im]
                r = ":".join(im)
                csr.append(r)
            cs = "".join("|" + x for x in csr)

        # TODO: generate u,s
        payload = {"a": apikey,
                   "cs": urllib.quote(cs),
                   "p": productid,
                   "re": 'true',
                   "pt": urllib.quote(pt),
                   "u": 'c4e19f181ac49938303bf77c146141bf',
                   "s": 'c4e19f181ac49938303bf77c146141bf',
                   "flv": "16.0.0",
                   "l": 1}
        return payload

    def _parse_rr_json(self, response):
        product = response.meta['product']
        text = response.body_as_unicode().encode('utf-8')
        rr_data = self._parse_rr_js(text)
        if rr_data:
            placements = {'item_page.centre_bottom': 'recommendation'}
            product['related_products'] = {}
            for place, value in rr_data.items():
                items = value['items']
                prodlist = []
                for item_name, item_url in items:
                    prodlist.append(RelatedProduct(item_name, item_url))

                pp_key = placements.get(place)
                if pp_key:
                    product['related_products'][pp_key] = prodlist
        return response.meta['reevoo']

    def _parse_rr_js(self, text):
        m = re.match(
            r"^.*var rr_recs=\{placements:\[\{(.*)\}\]\}",
            text, re.DOTALL)
        if m:
            data = m.group(1)
            m2 = re.findall(
                r"placementType:'([^']*)',html:'(([^\\']+|\\.)*)'",
                data, re.DOTALL)
            if m2:
                results = {}
                for pt in m2:
                    html = pt[1]
                    placementtype = pt[0]
                    results[placementtype] = {}
                    s = Selector(text=html)
                    iplace = s.xpath(
                        "//div[@class='inner_space']"
                        "/p/strong/text()").extract()
                    if iplace:
                        iplace = iplace[0]

                    results[placementtype]['title'] = iplace
                    iitems = s.xpath(
                        "//div[@class='col2']/article[@class='product']/a")
                    results[placementtype]['items'] = []
                    for iitem in iitems:
                        ilink = iitem.xpath("@href").extract()
                        if ilink:
                            ilink = ilink[0]
                            original_url = None
                            iname = None

                            url_split = urlparse.urlsplit(ilink)
                            query = urlparse.parse_qs(url_split.query)
                            original_url = query.get('ct')[0]

                        iname = iitem.xpath("img/@alt").extract()
                        if iname:
                            iname = iname[0]
                            iname = iname.encode('utf-8').decode('utf-8')
                            iname = iname.replace(u"\\'", u"'")
                        if original_url and iname:
                            results[placementtype]['items'].append(
                                (iname, original_url))
                return results

    def _parse_reevoo(self, response):
        product = response.meta['product']
        if response.status == 404:
            return product
        text = response.body_as_unicode().encode('utf-8')
        sel = Selector(text=text)
        summary = sel.xpath("//header/h3/text()").re("(\d+) reviews")
        if summary:
            try:
                summary = int(summary[0])
            except ValueError:
                summary = 0
        average = sel.xpath(
            "//section/div[contains(@class,'average_score')]"
            "/@title").re("is (.*) out of")
        if average:
            try:
                average = float(average[0])
            except ValueError:
                average = 0.0
        scores = sel.xpath(
            "//section[@class='score_breakdown']"
            "/table[@class='scores']/tbody/tr")
        results = []
        for s in scores:
            name = s.xpath("th/text()").extract()
            if name:
                name = name[0]
                val = s.xpath("td/div/span/@data-score").extract()
                if val:
                    try:
                        val = float(val[0])
                    except ValueError:
                        val = 0.0
                    results.append((name, val))
        br = BuyerReviews(
            num_of_reviews=summary,
            average_rating=average,
            rating_by_star=dict(results))
        product['buyer_reviews'] = br if summary else ZERO_REVIEWS_VALUE
        return product

    def _scrape_total_matches(self, response):
        is_product = response.xpath("//meta[@property='og:type']/@content").re('product')
        if is_product:
            return 1
        total = response.xpath(
            "//section[@role='main']"
            "/div[@class='mboxDefault']"
            "/div[contains(@class,'row')]"
            "/strong/text()").re("of (\d+) results")
        if total:
            try:
                return int(total[0])
            except ValueError:
                return
        return 0

    def _scrape_product_links(self, response):

        def full_url(url):
            return urlparse.urljoin(response.url, url)

        is_product = response.xpath("//meta[@property='og:type']/@content").re('product')
        links = response.xpath(
            "//div[contains(@class,'row')]/div[contains(@class,'resultList')]"
            "/article/a/@href").extract()

        if not links:
            if is_product:
                yield response.url + "?_=123", SiteProductItem()
                return
            self.log("Found no product links.", DEBUG)

        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page_links = response.xpath(
            "//ul[@class='pagination']"
            "/li/a[contains(text(),'→')]/@href").extract()
        if next_page_links:
            return next_page_links[0]

    def _parse_single_product(self, response):
        return self.parse_product(response)
