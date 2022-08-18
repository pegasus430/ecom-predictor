from __future__ import division, absolute_import, unicode_literals
#from future_builtins import *

import re
import sys
import json
import urllib
import urllib2
import string

from scrapy.selector import Selector
from scrapy.log import ERROR
from scrapy import Request

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import SiteProductItem, \
    Price, RelatedProduct, BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, \
    cond_set, cond_set_value, FLOATING_POINT_RGEX

is_empty = lambda x, y=None: x[0] if x else y


def _strip_non_ascii(s):
    return filter(lambda x: x in string.printable, s)


class TescoDirectProductsSpider(BaseProductsSpider):
    """This site have MARKETPLACE, but it does not implemented
    """

    name = 'tescodirect_products'
    allowed_domains = ["www.tesco.com"]

    pages_count = 0
    product_iteration = 1

    tot_matches = 0

    stack = []
    stack_total = []

    link_begin = "http://www.tesco.com"

    sort_by = ""

    SORT_MODES = {
        "Relevance": False,
        "Best Sellers": 1,
        "Customer Rating": 2,
        "Price (Low - High)": 3,
        "Price (High - Low)": 4,
        "Special Offers": 5,
        "Name (A-Z)": 6,
        "Name (Z-A)": 7,
        "Release (Most Recent)": 8,
        "New In": 10,
    }

    # TODO: change the currency if you're going to support different countries
    #  (only UK and GBP are supported now)
    SEARCH_URL = "http://www.tesco.com/direct/search-results/" \
       "results.page?_DARGS=/blocks/common/flyoutSearch.jsp"

    def __init__(self, *args, **kwargs):
        self.search = kwargs.get("searchterms_str")
        if "search_modes" in kwargs:
            self.sort_by = self.SORT_MODES[kwargs["search_modes"]]
        super(TescoDirectProductsSpider, self).__init__(*args, **kwargs)
        self.site_name = "www.tesco.com/direct"

    def start_requests(self):
        """Generate Requests from the SEARCH_URL and the search terms."""
        #IMPORTANT!!!!!!
        #Here we takes data - from POST request(search form)
        data = "%2Fcom%2Ftesco" \
            "%2Fbns%2FformHandlers%2FBasicSearchFormHandler" \
            ".snpSrchResURL=%2Fdirect%2Fsearch-results%2Fresults" \
            ".page&_D%3A%2Fcom%2Ftesco%2Fbns%2FformHandlers%2F" \
            "BasicSearchFormHandler.snpSrchResURL=+&%2Fcom%2F" \
            "tesco%2Fbns%2FformHandlers%2FBasicSearchFormHandler" \
            ".snpZeroResURL=%2Fdirect%2Fsearch-results%2Fzero-" \
            "results.page&_D%3A%2Fcom%2Ftesco%2Fbns%2FformHandlers" \
            "%2FBasicSearchFormHandler.snpZeroResURL=+&%2Fcom" \
            "%2Ftesco%2Fbns%2FformHandlers%2FBasicSearchFormHandler" \
            ".currentUrl=catId%3D4294960317&_D%3A%2Fcom%2Ftesco%2F" \
            "bns%2FformHandlers%2FBasicSearchFormHandler." \
            "currentUrl=+&%2Fcom%2Ftesco%2Fbns%2FformHandlers" \
            "%2FBasicSearchFormHandler.snpBuyingGuideURL=%2F" \
            "direct%2Fsearch-help%2Fsearch-results-help.page" \
            "&_D%3A%2Fcom%2Ftesco%2Fbns%2FformHandlers%2F" \
            "BasicSearchFormHandler.snpBuyingGuideURL=+&%2Fcom" \
            "%2Ftesco%2Fbns%2FformHandlers%2FBasicSearchFormHandler" \
            ".Search=Search&_D%3A%2Fcom%2Ftesco%2Fbns%2FformHandlers" \
            "%2FBasicSearchFormHandler.Search=+&%2Fcom%2Ftesco%2Fbns" \
            "%2FformHandlers%2FBasicSearchFormHandler.strSrchIntrface" \
            "=Entire+Site%7C%7C4294967294&_D%3A%2Fcom%2Ftesco%2Fbns" \
            "%2FformHandlers%2FBasicSearchFormHandler.strSrchIntrface" \
            "=+&_D%3Asearch=+&_DARGS=%2Fblocks%2Fcommon" \
            "%2FflyoutSearch.jsp&search=" + str(self.search)
        for st in self.searchterms:
            yield Request(
                url=self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                method="POST",
                meta={'search_term': st, 'remaining': self.quantity,},
                body=data,
                headers={'Content-type': 'application/x-www-form-urlencoded'},
                callback=self.handler,
            )
        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['site'] = "www.tesco.com/direct"
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})


    def handler(self, response):
        if not re.search("&sortBy=" + str(self.sort_by), response.url) \
            and re.search("&sortBy=", response.url):
            url = re.sub(
                "&sortBy=\d+",
                "&sortBy=" + str(self.sort_by),
                response.url
            )
            yield self.request_for_sort(url)
        elif self.sort_by == False and re.search("&sortBy=", response.url):
            url = re.sub(
                "&sortBy=\d+",
                "",
                response.url
            )
            yield self.request_for_sort(url)
        else:
            self.first_response = response
            for i in self.get_pages_for_total_matches(response):
                yield i

    def request_for_sort(self, url):
        return Request(
                url,
                meta={
                    'search_term': self.search,
                    'remaining': sys.maxint
                },
                callback=self.handler,
            )

    def parse(self, response):
        if self._search_page_error(response):
            remaining = response.meta['remaining']
            search_term = response.meta['search_term']

            self.log("For search term '%s' with %d items remaining,"
                     " failed to retrieve search page: %s"
                     % (search_term, remaining, response.request.url),
                     ERROR)
        else:
            prods_count = -1  # Also used after the loop.
            for prods_count, request_or_prod in enumerate(
                    self._get_products(response)):
                yield request_or_prod
            prods_count += 1  # Fix counter.
            request = self._get_next_products_page(response, prods_count)
            if request is not None:
                yield request
            else:
                remaining = response.meta.get('remaining', sys.maxint)
                yield self.next_stack_request(remaining)

    def getResponse(self, response):
        if self.push_to_stack_category(response, self.stack):
            remaining = response.meta.get("remaining", sys.maxint)
            yield self.next_stack_request(remaining)
        else:
            for item in self.parse(response):
                yield item

    #Crawl next category
    def next_stack_request(self, remaining=sys.maxint):
        if self.stack:
            next_url = self.stack.pop(0)
            sb = ""
            if self.sort_by:
                sb = "&sortBy=" + str(self.sort_by)
            return Request(
                    self.link_begin + next_url + \
                    sb,
                    meta = {
                        'search_term': self.search,
                        'remaining': remaining
                    },
                    callback=self.getResponse,
            )

    #Push categories to stack
    def push_to_stack_category(self, response, stack):
        categories = self.get_visual_nav(response)
        stack[:0] = categories
        return categories

    #Get categories from response
    def get_visual_nav(self, response):
        visual_nav = response.xpath(
            '//div[@id="visual-nav"]/ul/li/a/@href'
        ).extract()
        brandwall = response.xpath(
            '//div[@class="brandwall"]/a/@href').extract()
        if visual_nav:
            return visual_nav
        elif brandwall:
            for i in range(0, len(brandwall)):
                rep = re.findall("/direct/.*", brandwall[i])
                if rep:
                    brandwall[i] = rep[0]
            return brandwall
        return []

    def parse_product(self, response):
        product = response.meta["product"]
        product["total_matches"] = self.tot_matches

        title = response.xpath(
            '//h1[@class="page-title"]/text()').extract()
        title = _strip_non_ascii(title[0]) if title else ''
        product['title'] = title

        if title:
            brand = guess_brand_from_first_words(title)
            cond_set(product, 'brand', (brand,))

        price = response.xpath(
            '//p[@class="current-price"]/text()').re(FLOATING_POINT_RGEX)
        if price:
            product["price"] = Price(price=price[0], priceCurrency="GBP")

        title_marketplace = response.xpath(
            '//div[@class="header-wrapper"]/span[@class="available-from"]/text()').extract()
        if title_marketplace:
            title_marketplace = re.findall("Available from (.*)", title_marketplace[0])
            if title_marketplace:
                product["marketplace"] = [{
                    "name": title_marketplace[0],
                    "price": product["price"]
                }]

            for item in response.xpath(
                    "//div[contains(@class, 'other-sellers')]"):
                name = is_empty(item.xpath(
                    ".//div/span[contains(@class, 'available-from')]/text()"
                ).extract())
                name = is_empty(re.findall("Available from (.*)", name))

                price = is_empty(item.xpath(
                    ".//div[contains(@class, 'price-info')]/p/text()"
                ).re(FLOATING_POINT_RGEX))
                price = Price(price=price, priceCurrency="GBP")
                product["marketplace"].append({
                    "name": name,
                    "price": price,
                })

        desc = response.xpath(
            '//section[@id="product-details-link"]'
            '/section[@class="detailWrapper"]'
        ).extract()
        cond_set(product, 'description', desc)

        regex = "([A-Z0-9\-]+)\.prd"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        is_out_of_stock = response.xpath(
            '//div[@id="bbSeller1"]').extract()
        if is_out_of_stock:
            if "product is currently unavailable." in is_out_of_stock[0]:
                is_out_of_stock = True
            else:
                is_out_of_stock = False

            product["is_out_of_stock"] = is_out_of_stock

        image_url = response.xpath(
            '//div[@class="static-product-image scene7-enabled"]' \
            '/img[@itemprop="image"]/@src'
        ).extract()
        cond_set(product, 'image_url', image_url)

        resc_url = "http://recs.richrelevance.com/rrserver/p13n_generated.js?"
        apiKey = is_empty(re.findall("setApiKey\(\'(\w+)", response.body), "")
        if apiKey:
            apiKey = "a=" + apiKey
        pt = is_empty(re.findall(
            "addPlacementType\(\'(.*)\'", response.body), "")
        if pt:
            if len(pt) > 1:
                pt = "&pt=|" + pt[0] + "|" + pt[1]
            else:
                pt = "&pt=|" + pt[0]
        l = "&l=1"
        chi = is_empty(re.findall(
            "addCategoryHintId\(\'(.*)\'", response.body), "")
        if chi:
            chi = "&chi=|" + chi[0]
        else:
            chi = is_empty(response.xpath(
                '//meta[contains(@name, "parent_category")]/@content'
            ).extract(), "")
            chi = "&chi=|" + chi

        resc_url = resc_url + apiKey + pt + l + chi
        ajax = urllib2.urlopen(resc_url)
        resp = ajax.read()
        ajax.close()

        #related_products
        rp = []
        sel_all = re.findall('html:(\s+){0,1}\'([^\}]*)', resp)
        if sel_all:
            for item in sel_all:
                for el in item:
                    if not el:
                        continue
                    get = Selector(text=el).xpath(
                        '//div[@class="title-author-format"]/h3/a')
                    title = get.xpath('text()').extract()
                    url = get.xpath('@href').extract()
                    title = [title.strip() for title in title]
                    for i in range(0, len(title)):
                        title[i] = _strip_non_ascii(title[i])
                        rp.append(
                            RelatedProduct(
                                title=title[i],
                                url=url[i]
                            )
                        )
                    product["related_products"] = {"recommended": rp}

        #buyer_reviews
        upc = response.xpath('//meta[@property="og:upc"]/@content').extract()
        if upc:
            rating_url = "http://api.bazaarvoice.com/data/batch.json?" \
                "passkey=asiwwvlu4jk00qyffn49sr7tb&apiversion=5.5" \
                "&displaycode=1235-en_gb&resource.q0=products" \
                "&stats.q0=reviews&filteredstats.q0=reviews" \
                "&filter_reviews.q0=contentlocale%3Aeq%3Aen_AU" \
                "%2Cen_CA%2Cen_DE%2Cen_GB%2Cen_IE%2Cen_NZ%2Cen_US" \
                "&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen" \
                "_AU%2Cen_CA%2Cen_DE%2Cen_GB%2Cen_IE%2Cen_NZ%2Cen_US" \
                "&resource.q1=reviews" \
                "&filter.q1=isratingsonly%3Aeq%3Afalse" \
                "&filter.q1=contentlocale%3Aeq%3Aen_AU%2Cen_CA%2Cen_DE" \
                "%2Cen_GB%2Cen_IE%2Cen_NZ%2Cen_US" \
                "&sort.q1=submissiontime%3Adesc&stats.q1=reviews" \
                "&filteredstats.q1=reviews" \
                "&include.q1=authors%2Cproducts%2Ccomments" \
                "&filter_reviews.q1=contentlocale%3Aeq%3Aen_AU%2Cen_CA" \
                "%2Cen_DE%2Cen_GB%2Cen_IE%2Cen_NZ%2Cen_US" \
                "&filter_reviewcomments.q1=contentlocale%3Aeq%3Aen_AU" \
                "%2Cen_CA%2Cen_DE%2Cen_GB%2Cen_IE%2Cen_NZ%2Cen_US" \
                "&filter_comments.q1=contentlocale%3Aeq%3Aen_AU%2Cen_CA" \
                "%2Cen_DE%2Cen_GB%2Cen_IE%2Cen_NZ%2Cen_US" \
                "&limit.q1=5&offset.q1=0&limit_comments.q1=3"
            rating_url += "&filter.q0=id%3Aeq%3A" + str(upc[0])
            rating_url += "&filter.q1=productid%3Aeq%3A" + str(upc[0])

            ajax = urllib2.urlopen(rating_url)
            resp = ajax.read()
            ajax.close()

            data = json.loads(resp)
            try:
                num_of_reviews = data["BatchedResults"]["q1"] \
                    ["Includes"]["Products"][upc[0]] \
                    ["ReviewStatistics"]["TotalReviewCount"]
            except KeyError:
                num_of_reviews = None

            try:
                average_rating = round(data["BatchedResults"]["q1"] \
                    ["Includes"]["Products"][upc[0]] \
                    ["ReviewStatistics"]["AverageOverallRating"], 2)
            except KeyError:
                average_rating = None

            try:
                rating_by_star = { 1:0, 2:0, 3:0, 4:0, 5:0 }
                rbs = data["BatchedResults"]["q1"] \
                    ["Includes"]["Products"][upc[0]] \
                    ["ReviewStatistics"]["RatingDistribution"]
                for mark in rbs:
                    rating_by_star[mark["RatingValue"]] = mark["Count"]
            except KeyError:
                rating_by_star = None

            if average_rating or num_of_reviews:
                product["buyer_reviews"] = BuyerReviews(
                    average_rating=average_rating,
                    num_of_reviews=num_of_reviews,
                    rating_by_star=rating_by_star,
                )
            else:
                product['buyer_reviews'] = ZERO_REVIEWS_VALUE

        product["locale"] = "en_GB"

        return product

    #Sum total_matches from all Categories
    def next_total_stack_request(self):
        if self.stack_total:
            next_url = self.stack_total.pop(0)
            yield Request(
                    self.link_begin + next_url,
                    meta = {
                        'search_term': self.search,
                        'remaining': sys.maxint
                    },
                    callback=self.get_pages_for_total_matches,
                    dont_filter=True,
            )
        else:
            for req in self.getResponse(self.first_response):
                yield req

    #Crawl pages to sum total_matches
    def get_pages_for_total_matches(self, response):
        if self.push_to_stack_category(response, self.stack_total):
            next_req =  self.next_total_stack_request()
        else:
            next_req = self.sum_total_matches(response)

        return next_req

    def sum_total_matches(self, response):
        if "0 results found" in response.body_as_unicode():
            total_matches = 0
        else:
            total_matches = response.xpath(
                '//div[@class="filter-productCount"]/b/text()'
            ).extract()

        if total_matches:
            self.tot_matches += int(total_matches[0])
        next_req =  self.next_total_stack_request()
        return next_req


    def _scrape_total_matches(self, response):
        if "0 results found" in response.body_as_unicode():
            total_matches = 0
        else:
            total_matches = response.xpath(
                '//div[@class="filter-productCount"]/b/text()'
            ).extract()

        if not total_matches:
            return 0
        self.pages_count = int(round(
            (int(total_matches[0]) / 20) + 0.5
        ))
        total_matches = is_empty(total_matches)

        return int(total_matches)

    def _scrape_product_links(self, response):
        links = response.xpath('//ul[@class="products"]/' \
            'li[contains(@class, "product-tile")]' \
            '/div[contains(@class, "product")]/div/a/@href'
        ).extract()
        for link in set(links):
            if link != '#':
                link = self.link_begin + link
                yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if self.pages_count >= self.product_iteration:#search and
            offset = "&offset=" + str(self.product_iteration * 20)
            if re.search("&offset=\d+", response.url):
                url = re.sub("&offset=\d+", offset, response.url)
            else:
                url = response.url + offset
            link = url
            self.product_iteration += 1
            return link
        self.product_iteration = 1
        return None

    def _parse_single_product(self, response):
        return self.parse_product(response)
