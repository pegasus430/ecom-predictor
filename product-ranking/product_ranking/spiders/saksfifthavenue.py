# -*- coding: utf-8 -*-#

from __future__ import division, absolute_import, unicode_literals

from datetime import datetime
import json
import re
import string
import urlparse

import lxml.html
from scrapy import Selector
from scrapy.http import Request
from scrapy.log import DEBUG

from product_ranking.items import Price
from product_ranking.items import SiteProductItem, RelatedProduct, BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX
from product_ranking.spiders import cond_set, cond_set_value


def fromxml(stext, resp):
    if stext:
        return lxml.html.fromstring(stext).text
    return ""


class SaksfifthavenueProductsSpider(BaseProductsSpider):
    name = 'saksfifthavenue_products'
    allowed_domains = [
        "saksfifthavenue.com", "recs.richrelevance.com",
        "saksfifthavenue.ugc.bazaarvoice.com"]
    start_urls = []
    SEARCH_URL = (
        "http://www.saksfifthavenue.com/search/EndecaSearch.jsp"
        "?bmForm=endeca_search_form_one"
        "&bmIsForm=true&bmText=SearchString&SearchString={search_term}"
        "&submit-search=&bmSingle=N_Dim&N_Dim=0&bmHidden=Ntk&Ntk=Entire+Site")
    SORTING = None
    SORT_MODES = {
        'default': None,
        'new': 'new-arrivals',
        'best': 'best-sellers',
        'toprated': 'top-rated',
        'lowtohigh': 'low-to-high',
        'atoz': 'a-to-z',
        'category': None,
        'sale': 'sale-first'}

    def __init__(self, sort_mode=None, *args, **kwargs):
        if sort_mode:
            if sort_mode not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
                sort_mode = 'default'
            self.SORTING = self.SORT_MODES[sort_mode]

        super(SaksfifthavenueProductsSpider, self).__init__(
            None,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)

        if "main/WorldOfDesigner.jsp" in response.url and not response.meta.get('plinks'):
            plinks = response.xpath(
                "//ul[contains(@class,'left-nav-links-container')][2]"
                "/li[contains(@class,'js-left-nav-links')]"
                "/ul"
                "/li/a/@href").extract()
            if plinks:
                url = plinks[0]
                response.meta['plinks'] = plinks[1:]
                self.linkno = 0
                self.links = []
                yield Request(
                    full_url(url), meta=response.meta.copy(),
                    callback=self._parse_links)
                return

        if self.SORTING and not response.meta.get('set_sorting'):
            sortmenu = response.xpath(
                "//span[@id='sort-menu']/ul[@id='sort-by']"
                "/li[@id='{sorting}']"
                "/a/@href".format(sorting=self.SORTING)).extract()
            if sortmenu:
                next_url = "http://www.saksfifthavenue.com" + sortmenu[0]
                new_meta = response.meta.copy()
                new_meta['set_sorting'] = True
                yield Request(url=next_url, meta=new_meta)
                return
        for r in super(SaksfifthavenueProductsSpider, self).parse(response):
            yield r

    def _parse_links(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)
        links = response.xpath(
            "//div[@id='product-container']"
            "/div[contains(@id,'product-')]"
            "/div[@class='product-text']/a/@href").extract()
        # print "REMAINING=", response.meta.get('remaining')
        remaining = response.meta.get('remaining')
        self.linkno += len(links)
        self.links.extend(links)

        if remaining < self.linkno:
            l = list(super(SaksfifthavenueProductsSpider, self).parse(
                response))
            return l

        next_page_links = response.xpath(
            "//ol[@class='pa-page-number']"
            "/li/a/img[@alt='next']"
            "/../@href").extract()
        if next_page_links:
            url = next_page_links[0]
            return Request(
                full_url(url), meta=response.meta.copy(),
                callback=self._parse_links)
        plinks = response.meta.get('plinks')
        if plinks:
            url = plinks[0]
            plinks = plinks[1:]
            response.meta['plinks'] = plinks
            return Request(
                full_url(url), meta=response.meta.copy(),
                callback=self._parse_links)
        else:
            l = list(super(SaksfifthavenueProductsSpider, self).parse(
                response))
            return l

    def parse_product(self, response):
        response = response.replace(encoding='utf-8')
        product = response.meta['product']
        text = response.body_as_unicode()
        # jtext = response.xpath(
        #     "//script[contains(text(),'var mlrs =')]"
        #     "/text()").re(r"var mlrs = (.*)")
        jtext = text
        m = re.search(r"var mlrs = (.*)", text)
        if m:
            jtext = m.group(1)
        try:
            jdata = json.loads(jtext)

            mp = jdata["response"]["body"]["main_products"][0]
            colors = mp["colors"]["colors"]
            sizes = mp["sizes"]["sizes"]
            skus = mp["skus"]["skus"]
            variants = []

            for sku in skus:
                variants_dict = {}
                for color in colors:
                    if color.get("color_id") == sku.get("color_id"):
                        variants_dict["color"] = color.get("label")
                for size in sizes:
                    if size.get("size_id") == sku.get("size_id"):
                        variants_dict["size"] = size.get("value")
                price = re.findall(
                    FLOATING_POINT_RGEX,
                    sku.get("price", {}).get("sale_price")
                )
                if price:
                    variants_dict["price"] = price[len(price)-1]
                variants_dict["is_in_stock"] = False
                if sku.get("status_alias") == "available":
                    variants_dict["is_in_stock"] = True
                if variants_dict:
                    variants.append(variants_dict)
            
            if variants:
                product["variants"] = variants

            cond_set(product, 'title', response.xpath(
                "//header/h2[contains(@class,'short-description')]"
                "/text()").extract())
            cond_set(product, 'brand', response.xpath(
                "//header/h1[contains(@class,'brand-name')]/a/text()").extract(),
                conv=string.strip)
            tprice = fromxml(jdata['response']['body'][
                'main_products'][0]['price']['sale_price'], response)
            price = re.search(FLOATING_POINT_RGEX, tprice)
            if price:
                price = price.group(0)
                product['price'] = Price(
                    price=price, priceCurrency='USD')

            model = fromxml(jdata['response']['body']['main_products'][0]['product_code'], response)
            cond_set_value(product, 'model', unicode(model))

            description = jdata['response']['body'][
                'main_products'][0]['description']
            cond_set_value(product, 'description', description)

            media = jdata['response']['body']['main_products'][0]['media']
            image_url = "http:" + media['images_server_url'] + media['images_path'] + \
                media['images']['product_detail_image']
            cond_set_value(product, 'image_url', image_url)
        except ValueError as e:
            self.log("JSON error({0}): ".format(e.message), DEBUG)
            cond_set(product, "brand", response.xpath(
                "//*[contains(@class, 'brand')]/text()").extract())
            cond_set(product, "title", response.xpath(
                "//*[contains(@class, 'description')]/text()").extract())
            cond_set(product, "model", response.xpath(
                "//*[contains(@class, 'product-code-reskin')]/text()").extract())
            price = response.xpath("//div[contains(@class, 'price')]"
                                   "/div[contains(@class, 'value')]/text()").extract()
            if not price:
                price = response.xpath('//span[@itemprop="price"]/text()').extract()
            if price:
                price = price[0]
                product['price'] = Price(
                    price=price, priceCurrency='USD')

            description = re.search('"description":"(.*?)",', response.body)
            description = description.group(1) if description else None
            cond_set_value(product, 'description', description)

            image_url = response.xpath(
                "//*[@property='og:image']/@content").extract()
            if image_url:
                image_url = image_url[0].split('_')[0] + '_600x800.jpg'
                cond_set_value(product, 'image_url', urlparse.urljoin("http:", image_url))

        cond_set_value(product, 'locale', "en-US")

        if 'model' not in product:
            return product

        bvurl = self._gen_bv_url(response)
        response.meta['bvurl'] = bvurl

        url = self._gen_rr_request(response)

        if url:
            new_meta = response.meta.copy()
            new_meta['product'] = product
            new_meta['handle_httpstatus_list'] = [404]
            return Request(
                url,
                meta=new_meta,
                callback=self._parse_rr,
                dont_filter=True)

    def _gen_rr_request(self, response):
        def jsGetTime():
            diff = datetime(1970, 1, 1)
            return (datetime.utcnow() - diff).total_seconds() * 1000
        product = response.meta['product']
        api = response.xpath(
            "//script[contains(text(),'R3_COMMON.setApiKey')]"
            "/text()").re(r"R3_COMMON\.setApiKey\('(.*)'\)")
        if api:
            api = api[0]
            # http://recs.richrelevance.com/rrserver/p13n_generated.js?a=a92d0e9f58f55a71&ts=1424835239426&cs=%7C0%3Atest&p=0432947704503&pt=%7Citem_page.content2&s=1424776912650O-T93NqpG6x9gPJTzIt99osOmThlw-hhk8mgFUElH3Byu8AJM7iXzur1&rcs=eF4FwbsNgDAMBcAmFaMgPSnPn9jZgD1wCgo6YH7u2nZ_z1V7OmhiqZY5ZCiE6O09D_O5unuBqgHrGWDVhIUL5yIj6wc0SBAV&l=1
            url = (
                "http://recs.richrelevance.com/rrserver/p13n_generated.js"
                "?a={api}"
                "&ts={ts}"
                "&cs=%7C0%3Atest"
                "&p={prodno}"
                "&pt=%7Citem_page.content2"
                "&l=1").format(
                    api=api, prodno=product['model'],
                    ts=int(jsGetTime()))
            return url

    def _parse_rr(self, response):
        product = response.meta['product']

        title = response.xpath("//div[contains(@id, 'rr_strategy')]/text()").extract()
        urls = re.findall("a_href = \"([^\"]*)", response.body)
        names = response.xpath("//div[contains(@class, 'medium')]/text()").extract()
        rp = dict(zip(names, urls))

        product['related_products'] = {}
        prodlist = []
        for k, v in rp.items():
            prodlist.append(RelatedProduct(k, v))
        if prodlist and title:
             product['related_products'] = {
                title[0]: prodlist
             }

        bvurl = response.meta.get('bvurl')
        if bvurl:
            # TODO: add dont_filter
            new_meta = response.meta.copy()
            new_meta['product'] = product
            new_meta['handle_httpstatus_list'] = [404]
            return Request(
                bvurl,
                meta=new_meta,
                callback=self._parse_bv,
                dont_filter=True)
        return product

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

                    sel = Selector(text=html)
                    ilist = sel.xpath("//td[@class='rr_item']")
                    results[placementtype]['items'] = []
                    for iitem in ilist:
                        ilink = iitem.xpath("a/@href").extract()
                        if ilink:
                            ilink = ilink[0]
                            url_split = urlparse.urlsplit(ilink)
                            query = urlparse.parse_qs(url_split.query)
                            original_url = query.get('ct', [None])[0]
                            iname = iitem.xpath(
                                "a/div[@class='rr_item_text']"
                                "/div[@class='medium']"
                                "/text()").extract()
                            if iname:
                                iname = iname[0]
                                iname = iname.encode('utf-8').decode('utf-8')
                                iname = iname.replace(u"\\'", u"'")
                                results[placementtype]['items'].append(
                                    (iname, original_url))
                    return results

    def _gen_bv_url(self, response):
        product = response.meta['product']
        url = (
            "http://saksfifthavenue.ugc.bazaarvoice.com/5000-en_us"
            "/{prodno}/reviews.djs"
            "?format=embeddedhtml").format(prodno=product['model'])
        return url

    def _parse_bv(self, response):
        product = response.meta['product']
        text = response.body_as_unicode().encode('utf-8')
        if response.status == 200:
            x = re.search(
                r"var materials=(.*),\sinitializers=", text, re.M + re.S)
            if x:
                jtext = x.group(1)
                jdata = json.loads(jtext)
                html = jdata['BVRRRatingSummarySourceID']
                sel = Selector(text=html.encode('utf-8'))
                m = re.search(r'"avgRating":(.*?),', text, re.M)
                if m:
                    avrg = m.group(1)
                    try:
                        avrg = float(avrg)
                    except ValueError:
                        avrg = 0.0
                total = sel.xpath(
                    "//div[@class='BVRRHistogram']"
                    "/div[@class='BVRRHistogramTitle']"
                    "/span[contains(@class,'BVRRNonZeroCount')]"
                    "/span[@class='BVRRNumber']/text()").extract()
                if total:
                    try:
                        total = int(total[0])
                    except ValueError:
                        total = 0
                else:
                    total = 0
                hist = sel.xpath(
                    "//div[@class='BVRRHistogram']"
                    "/div[@class='BVRRHistogramContent']"
                    "/div[contains(@class,'BVRRHistogramBarRow')]")
                distribution = {}
                for ih in hist:
                    name = ih.xpath(
                        "span/span[@class='BVRRHistStarLabelText']"
                        "/text()").re("(\d) star")
                    try:
                        if name:
                            name = int(name[0])
                        value = ih.xpath(
                            "span[@class='BVRRHistAbsLabel']/text()").extract()
                        if value:
                            value = int(value[0])
                        distribution[name] = value
                    except ValueError:
                        pass
                if distribution:
                    reviews = BuyerReviews(total, avrg, distribution)
                    cond_set_value(product, 'buyer_reviews', reviews)
                elif not total:
                    cond_set_value(product, 'buyer_reviews',
                                   ZERO_REVIEWS_VALUE)
        return product

    def check_alert(self, response):
        alert = response.xpath("//span[@id='no-results-msg']").extract()
        return alert

    def _scrape_total_matches(self, response):
        if 'plinks' in response.meta:
            return self.linkno
        if self.check_alert(response):
            return
        total = response.xpath(
            "//div[@class='pa-gination']"
            "/span[contains(@class,'totalRecords')]"
            "/text()").extract()
        if total:
            total = total[0].replace(",", "")
            try:
                return int(total)
            except ValueError:
                return
        return 0

    def _scrape_product_links(self, response):
        if 'plinks' in response.meta:
            links = self.links
            for link in links:
                yield link, SiteProductItem()
            return

        if self.check_alert(response):
            return
        links = response.xpath(
            "//div[@id='product-container']"
            "/div[contains(@id,'product-')]"
            "/div[@class='product-text']/a/@href").extract()
        if not links:
            self.log("Found no product links.", DEBUG)
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)
        if self.check_alert(response):
            return
        next_page_links = response.xpath(
            "//ol[contains(@class,'pa-page-number')]"
            "/li/a/img[@alt='next']"
            "/../@href |"
            "//ol[contains(@class,'pa-page-number')]"
            "/li[last()]/a/@href"
        ).extract()
        if next_page_links:
            return full_url(next_page_links[0])
        else:
            return
