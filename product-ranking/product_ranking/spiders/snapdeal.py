# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

from urlparse import urljoin
import json
import re

from scrapy.http import Request

from product_ranking.items import SiteProductItem, RelatedProduct, Price, \
    BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, cond_set, cond_set_value, \
    FLOATING_POINT_RGEX
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.utils import is_empty


class SnapdealProductSpider(BaseProductsSpider):
    name = 'snapdeal_products'
    allowed_domains = ["www.snapdeal.com"]

    SEARCH_URL = ("http://www.snapdeal.com/acors/json/product/get/search"
        "/0/0/20?q=&sort={sort}&keyword=&clickSrc=go_header"
        "&viewType=List&lang=en&snr=false")

    START_URL = ("http://www.snapdeal.com/search?keyword={search_term}"
        "&santizedKeyword=&catId=&categoryId=&suggested=false&vertical="
        "&noOfResults=20&clickSrc=go_header&lastKeyword=&prodCatId="
        "&changeBackToAll=false&foundInAll=false&categoryIdSearched="
        "&cityPageUrl=&url=&utmContent=&catalogID=&dealDetail=")

    RELATED_URL = ("http://www.snapdeal.com/acors/json/"
        "getPersonalizationWidgetDataById?"
        "pogId={ppid}&categoryId={catId}&brandId={brandId}")

    REVIEWS_URL = "http://www.snapdeal.com/review/stats/{id}"

    NEXT_PAGI_PAGE = ("http://www.snapdeal.com/acors/json/product/get/search"
        "/{sltab}/{pos}/{start_pos}?q={qparam}&sort={sort}&keyword={keyword}"
        "&clickSrc={clickSrc}&viewType=List&lang=en&snr=false")

    position = 20

    STOP = False

    SORT_MODES = {
        "RELEVANCE": "rlvncy",
        "POPULARITY": "plrty",
        "BESTSELLERS": "bstslr",
        "PRICE": "plth",
        "DISCOUNT": "dhtl",
        "FRESH_ARRIVALS": "rec",
    }

    tm = None
    is_set_sort = False

    def __init__(self, *args, **kwargs):
        super(SnapdealProductSpider, self).__init__(*args, **kwargs)
        if kwargs.get("sort_mode"):
            self.is_set_sort = True
        self.sort_by = self.SORT_MODES.get(
            kwargs.get("sort_mode", "POPULARITY"))

    def start_requests(self):
        if not self.product_url:
            yield Request(
                url=self.START_URL.format(search_term=self.searchterms[0]),
                callback=self.after_start,
            )
        else:
            for req in super(SnapdealProductSpider, self).start_requests():
                yield req

    def after_start(self, response):
        if 'Sorry, no results found for' in response.body_as_unicode():
            return

        self.start_pos = int(is_empty(response.xpath(
            "//input[@id='startProductState']/@value").extract(), 20))

        self.qparam = is_empty(response.xpath(
            "//a[@id='seeMoreProducts']/@qparam").extract(), "")
        sorttype = is_empty(response.xpath(
            "//a[@id='seeMoreProducts']/@sorttype").extract())
        self.slTab = is_empty(response.xpath(
            "//input[@id='selectedTabId']/@value | "
            "//input[@id='categoryIdStoreFront']/@value"
        ).extract(), 0)
        self.keyword = is_empty(response.xpath(
            "//input[@id='keyword']/@value").extract(), "")
        self.clickSrc = is_empty(response.xpath(
            "//input[@id='clickSrc']/@value").extract(), "")
        if not self.is_set_sort:
            srt = is_empty(re.findall(
                "sortTypeVal\s+=\s+\"([^\"]*)", response.body))
            self.sort_by = sorttype or srt or self.SORT_MODES["POPULARITY"]

        self.SEARCH_URL = ("http://www.snapdeal.com/acors/json/product/get/"
            "search/{slTab}/0/{start_pos}?q={qparam}&sort={sort}"
            "&keyword={keyword}&clickSrc={clickSrc}&viewType=List&lang=en"
            "&snr=false".format(
                qparam=self.qparam, slTab=self.slTab, sort=self.sort_by,
                keyword=self.keyword, clickSrc=self.clickSrc,
                start_pos=self.start_pos
            )
        )

        url = is_empty(response.xpath(
            "//div[contains(@class, 'viewallbox')]/a/@href").extract())
        if url:
            return Request(url=url, callback=self.after_start)
        self.tm = self._scrape_total_matches(response)
        return super(SnapdealProductSpider, self).start_requests()

    def parse_product(self, response):
        product = response.meta.get("product")
        reqs = []

        text = response.body_as_unicode()
        text = text.replace('_blank"', '').replace('target="', '')
        response = response.replace(body=text)

        product["locale"] = "en_US"

        title = is_empty(response.xpath(
            "//h1[@itemprop='name']/text()").extract())
        cond_set(product, "title", (title,))

        brand = is_empty(response.xpath(
            "//input[@id='brandName']/@value").extract())
        if not brand:
            brand = guess_brand_from_first_words(title)
        if brand:
            product["brand"] = brand

        cond_set(product, "image_url", response.xpath(
            "//ul[@id='product-slider']/li[1]/img/@src |"
            "//img[@itemprop='image']/@src"
        ).extract())

        model = is_empty(response.xpath(
            "//div[contains(@class, 'buybutton')]/a/@supc |"
            "//div[@id='defaultSupc']/text()"
        ).extract())
        if model:
            product["model"] = model

        description = self._parse_description(response)
        cond_set_value(product, "description", description)

        regex = "\/(\d+)(?:$|\?)"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        price = is_empty(response.xpath(
            "//span[@id='selling-price-id']/text() |"
            "//input[@id='productSellingPrice']/@value |"
            "//span[@itemprop='price']/text()"
        ).extract())

        if price:
            priceCurrency = is_empty(response.xpath(
                "//meta[@itemprop='priceCurrency']/@content").extract())
            product["price"] = Price(
                priceCurrency=priceCurrency or "INR", price=price)

            market_name = is_empty(response.xpath(
                "//span[@id='vendorName']/text()").extract())
            if market_name:
                product["marketplace"] = [{
                    "name": market_name,
                    "price": price,
                    "priceCurrency": priceCurrency,
                }]

        is_out_of_stock = is_empty(response.xpath(
            "//div[contains(@class, 'soldDiscontAlert')]/"
            ".//span[contains(@class, 'alert-heading')]/text()[last()]"
        ).extract(), "")

        sold_out = is_empty(response.xpath(
            "//input[@id='soldOut']/@value").extract())

        if sold_out == "false":
            product["is_out_of_stock"] = False
        elif sold_out == "true":
            product["is_out_of_stock"] = True
        else:
            if "is currently unavailable" in response.body_as_unicode() or \
                    "is sold out" in is_out_of_stock:
                product["is_out_of_stock"] = True
            else:
                product["is_out_of_stock"] = False

        if "This item has been discontinued" in response.body_as_unicode():
            product["is_out_of_stock"] = True

        variantsJSON = is_empty(response.xpath(
            "//input[@id='productAttributesJson']/@value |"
            "//div[@id='attributesJson']/text()"
        ).extract())
        try:
            variants = json.loads(variantsJSON)
        except (ValueError, TypeError):
            variants = []

        product["variants"] = []
        default_cat_id = is_empty(response.xpath(
            "//div[@id='defaultCatalogId']/text() |"
            "//input[@id='productCatalogId']/@value"
        ).extract())
        for variant in variants:
            dc = {
                variant.get("name", "color").lower(): variant.get("value"),
                "image_url": urljoin(
                    "http://n4.sdlcdn.com/", variant["images"][0]),
                "in_stock": not variant.get("soldOut", True),
                "selected": False,
            }
            if str(variant.get("id", -1)) == str(default_cat_id):
                dc["selected"] = True
            product["variants"].append(dc)
        if not product["variants"]:
            product["variants"] = None

        pid = is_empty(response.xpath(
            "//div[@id='pppid']/text() |"
            "//input[@id='pppid']/@value"
        ).extract())
        if not pid:
            pid = is_empty(re.findall("/(\d+)", response.url))

        if pid:
            buyer_reviews_url = Request(
                url=self.REVIEWS_URL.format(id=pid),
                callback=self.parse_buyer_reviews,
                dont_filter=True,
            )
            reqs.append(buyer_reviews_url)
        else:
            product["buyer_reviews"] = ZERO_REVIEWS_VALUE

        related_products = [{"similar products": []}]
        a = response.xpath(
            "//div[contains(@class, 'product_grid_box')]"
            "/.//div[contains(@class, 'product-title')]/a |"
            "//div[contains(@class, 'product-txtWrapper')]/div/a"
        )

        a = response.xpath(
            "//section[contains(@id, 'recommendations')]/.//div/a")

        for item in a:
            title = item.xpath(
                ".//p[contains(@class, 'product-title')]/text() | text()"
            ).extract()
            if len(title) > 1:
                title = ''.join(title).strip()
            link = is_empty(item.xpath("@href").extract(), "")
            related_products[0]["similar products"].append(
                RelatedProduct(title=title, url=link)
            )

        if related_products[0]["similar products"]:
            product["related_products"] = related_products

        brandId = is_empty(response.xpath(
            "//div[@id='brndId']/text() |"
            "//input[@id=brndId]/@value"
        ).extract())
        catId = is_empty(response.xpath(
            "//div[@id='categoryId']/text() | "
            "//input[@id=categoryId]/@value"
        ).extract())

        if brandId and catId and pid:
            url = self.RELATED_URL.format(
                ppid=pid, catId=catId, brandId=brandId)
            reqs.append(
                Request(
                    url=url,
                    callback=self.parse_related
                )
            )

        marketplace_link = is_empty(response.xpath(
            "//a[@id='buyMoreSellerLink']/@href |"
            "//div[contains(@class, 'other-sellers')]/a/@href"
        ).extract())
        if marketplace_link:
            marketplace_link = urljoin(
                "http://www.snapdeal.com/", marketplace_link)
            marketplace_req = Request(
                url=marketplace_link,
                callback=self.parse_marketplace,
            )
            reqs.append(marketplace_req)

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_description(self, response):
        description = response.xpath(
            "//div[contains(@class, 'details-content')] |"
            "//div[@itemprop='description' and @class='detailssubbox']//p/text() |"
            "//section[@id='productSpecs']"
        ).extract()

        return self._clean_text(''.join(description)) if description else None

    def send_next_request(self, reqs, response):
        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def parse_buyer_reviews(self, response):
        product = response.meta.get("product")
        reqs = response.meta.get("reqs")
        total = 0

        rev = is_empty(re.findall("temp\s+=\s+\(([^\)]*)", response.body), "")
        try:
            rev = json.loads(rev)
        except ValueError:
            rev = {}
        if rev:
            for v in rev.values():
                total += int(v)

            avg = is_empty(response.xpath(
                "//p[contains(@class, 'ig-heading')]/span/text()"
            ).extract(), 0)
            if avg:
                avg = float(is_empty(re.findall("([^\/]*)", str(avg)),0))
        else:
            avg = float(is_empty(response.xpath(
                "//div[contains(@class, 'ratetxt')]/span[1]/text()"
            ).re(FLOATING_POINT_RGEX), 0))
            for item in response.xpath(
                    "//div[contains(@class, 'row')]/span"):
                star = is_empty(item.xpath(
                    "span[1]/text()").re(FLOATING_POINT_RGEX))
                if not star:
                    continue
                rev[star] = is_empty(item.xpath(
                    "span[last()]/text()").re(FLOATING_POINT_RGEX))
            for item in response.xpath(
                    "//div[contains(@class, 'row')]"):
                star = is_empty(item.xpath(
                    "span[1]/text()").re(FLOATING_POINT_RGEX))
                if not star:
                    continue
                rev[star] = is_empty(item.xpath(
                    "span[last()]/text()").re(FLOATING_POINT_RGEX))

            for v in rev.values():
                total += int(v)

        if avg and total:
            product["buyer_reviews"] = BuyerReviews(
                num_of_reviews=total, average_rating=avg, rating_by_star=rev)
        else:
            product["buyer_reviews"] = 0

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def parse_marketplace(self, response):
        product = response.meta.get("product")
        reqs = response.meta.get("reqs")

        marketplace = []

        for div in response.xpath("//div[@id='mvfrstVisible']"
                "/div[contains(@class, 'cont')]"):
            name = is_empty(div.xpath(
                ".//a[contains(@class, 'mvLink')]/text()").extract(), "")
            price = is_empty(div.xpath(
                ".//strong/text()").re(FLOATING_POINT_RGEX), "")
            if price:
                price = Price(priceCurrency="INR", price=price)
            if name and price:
                marketplace.append({"price": price, "name": name.strip()})

        for div in response.xpath("//li[contains(@class, 'seller-dtls')]/div"):
            name = is_empty(div.xpath(
                ".//div[contains(@class, 'seller-nm')]/a/text()").extract())
            price = is_empty(div.xpath(
                ".//div[contains(@class, 'price-dtls')]"
                "/p[contains(@class, 'FINAL')]/text()"
            ).re(FLOATING_POINT_RGEX), "")
            if price:
                price = Price(priceCurrency="INR", price=price)
            if name and price:
                marketplace.append({"price": price, "name": name.strip()})

        product["marketplace"] = marketplace

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def parse_related(self, response):
        product = response.meta.get("product")
        reqs = response.meta.get("reqs")
        related_products = []

        try:
            data = json.loads(response.body)
            for rp in data[0]["personalizationWidgetDTO"]["widgetData"]:
                related_products.append(RelatedProduct
                    (
                        title=rp.get("name"),
                        url=urljoin(
                            "http://snapdeal.com", rp.get("pageUrl", "")),
                    )
                )
        except (ValueError, TypeError, IndexError):
            data = []

        if related_products:
            product["related_products"] = related_products

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _scrape_total_matches(self, response):
        if self.tm is None:
            total_matches = is_empty(response.xpath(
                "//span[contains(@class, 'categoryCount')]/text()"
            ).re(FLOATING_POINT_RGEX))
            if not total_matches:
                total_matches = is_empty(response.xpath(
                    "//div[contains(@class, 'catlist-active')]/../"
                    "div[contains(@class, 'catCount')]/text()"
                ).re(FLOATING_POINT_RGEX))
            if not total_matches:
                total_matches = is_empty(re.findall(
                    "totItmsFound\s+\=\s+(\d+)", response.body))
            if not total_matches:
                total_matches = is_empty(response.xpath(
                    "//span[@id='no-of-results-filter']/text() |"
                    "//b[@id='no-of-results-filter']/text()"
                ).extract(), "0")
            if not int(total_matches):
                total_matches = is_empty(response.xpath(
                    "//input[@id='resultsOnPage']/@value").extract(), "0")
            return int(total_matches.replace("+", ""))
        else:
            return self.tm

    def _scrape_product_links(self, response):
        links = []
        try:
            data = json.loads(response.body_as_unicode())
            if data.get("status", "") == "Fail":
                self.STOP = True
            for item in data.get("productOfferGroupDtos") or []:
                url = urljoin(
                    "http://www.snapdeal.com", item.get("pageUrl", ""))
                links.append(url)
        except ValueError:
            nf = is_empty(response.xpath(
                "//div[contains(@class, 'numberFound')]/text()").extract())
            if str(nf) == "0":
                self.STOP = True
            links = response.xpath(
                "//a[@id='prodDetails']/@href").extract()
            if not links:
                links = response.xpath(
                    "//a[contains(@class, 'prodLink')]/@href").extract()

        for link in links:
            yield (link, SiteProductItem())

    def _scrape_next_results_page_link(self, response):
        if self.STOP:
            return None
        url = self.NEXT_PAGI_PAGE.format(sltab=self.slTab, qparam=self.qparam,
            pos=self.position, sort=self.sort_by, keyword=self.keyword,
            clickSrc=self.clickSrc, start_pos=self.start_pos)
        self.position += 20
        return url

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
