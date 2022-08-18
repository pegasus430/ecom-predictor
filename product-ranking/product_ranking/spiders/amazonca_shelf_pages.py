# ~~coding=utf-8~~
from __future__ import division, absolute_import, unicode_literals

import re

from scrapy.log import ERROR, WARNING
from scrapy.http import Request

from product_ranking.items import SiteProductItem
from product_ranking.utils import is_empty

from .amazonca import AmazonProductsSpider
import urlparse
from random import randint
import json


class AmazonCaShelfPagesSpider(AmazonProductsSpider):
    name = 'amazonca_shelf_urls_products'

    # without this find_spiders() fails
    allowed_domains = [
        "amazon.ca", "www.amazon.ca",
        "amazon.com", "www.amazon.com"  # to avoid requests filtering
    ]

    def _setup_class_compatibility(self):
        """ Needed to maintain compatibility with the SC spiders baseclass """
        self.quantity = 99999
        self.site_name = self.allowed_domains[0]
        self.user_agent_key = None
        self.current_page = 1
        self.captcha_retries = 12

    @staticmethod
    def _setup_meta_compatibility():
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': 99999, 'search_term': ''}.copy()

    def __init__(self, *args, **kwargs):
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.num_pages = min(10, self.num_pages)

        super(AmazonCaShelfPagesSpider, self).__init__(*args, **kwargs)
        self._setup_class_compatibility()

        # For goldbox deals
        self.deal_response_json_list = []
        self.deal_product_url_list = []
        self.sorted_goldbox_deals_ids = []

    @staticmethod
    def valid_url(url):
        if not re.findall(r"http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def start_requests(self):
        if not "/goldbox/" in self.product_url:
            yield Request(
                self.valid_url(self.product_url),
                meta=self._setup_meta_compatibility()
            )
        else:
            self.log("Detected goldbox/lightning deals shelf page.", WARNING)
            yield Request(
                self.valid_url(self.product_url),
                callback=self._start_scrape_goldbox_links
            )

    def _scrape_product_links(self, response):
        """
        Overrides BaseProductsSpider method to scrape product links.
        """
        if self.deal_product_url_list:
            for item in self._generate_goldbox_links_from_deals(response):
                yield item
        else:
            shelf_categories = [c.strip() for c in response.xpath(
                ".//*[@id='s-result-count']/span/*/text()").extract()
                                if len(c.strip()) > 1]
            shelf_category = shelf_categories[-1] if shelf_categories else None

            try:
                lis = response.xpath(
                    "//div[@id='resultsCol']/./ul/li |"
                    "//div[@id='mainResults']/.//ul/li [contains(@id, 'result')] |"
                    "//div[@id='atfResults']/.//ul/li[contains(@id, 'result')] |"
                    "//div[@id='mainResults']/.//div[contains(@id, 'result')] |"
                    "//div[@id='btfResults']//ul/li[contains(@id, 'result')]")
                links = []
                last_idx = -1

                for li in lis:
                    is_prime = li.xpath(
                        "*/descendant::i[contains(concat(' ', @class, ' '),"
                        "' a-icon-prime ')] |"
                        ".//span[contains(@class, 'sprPrime')]"
                    )
                    is_prime_pantry = li.xpath(
                        "*/descendant::i[contains(concat(' ',@class,' '),'"
                        "a-icon-prime-pantry ')]"
                    )
                    data_asin = self._is_empty(
                        li.xpath('@id').extract()
                    )

                    is_sponsored = \
                        bool(li.xpath('.//h5[contains(text(), "ponsored")]').extract())

                    try:
                        idx = int(self._is_empty(
                            re.findall(r'\d+', data_asin)
                        ))
                    except ValueError:
                        continue

                    if idx > last_idx:
                        link = self._is_empty(
                            li.xpath(
                                ".//a[contains(@class,'s-access-detail-page')]/@href |"
                                ".//h3[@class='newaps']/a/@href"
                            ).extract()
                        )
                        if not link:
                            continue

                        if 'slredirect' in link:
                            link = 'http://' + self.allowed_domains[0] + '/' + link

                        links.append((link, is_prime, is_prime_pantry, is_sponsored))
                    else:
                        break

                    last_idx = idx
            except Exception as e:
                self.log('Link fail. ERROR: %s.' % str(e), WARNING)
                links = []

            if not links:
                links2 = []

                try:
                    # added for New fall toys
                    lis = response.xpath(
                        '//div[contains(@class,"a-carousel-viewport")]'
                        '//li[contains(@class,"a-carousel-card")]')
                    for li in lis:
                        is_prime = \
                            bool(li.xpath('.//i[contains(@class,"a-icon-prime")]'))
                        is_prime_pantry = False
                        is_sponsored = False
                        link = li.xpath(
                            './a[contains(@class,"acs_product-image")]/@href'
                        ).extract()
                        if len(link):
                            link = 'http://' + self.allowed_domains[0] + '/' + \
                                   link[0]
                            links2.append((link, is_prime, is_prime_pantry,
                                           is_sponsored))
                except Exception as e:
                    self.log('Links2 is fail. ERROR: %s.' % str(e), WARNING)

                links.extend(links2)

            if not links:
                ul = response.xpath('//div[@id="zg_centerListWrapper"]/'
                                    'div[@class="zg_itemImmersion"]')
                if ul:
                    def __parse_category():
                        _get_text = lambda x: is_empty(x.xpath('text()').extract())

                        __categories = []

                        category_root = \
                            response.xpath('//ul[@id="zg_browseRoot"]')
                        if not category_root:
                            return []

                        curent_ul = \
                            category_root.xpath('//span[@class="zg_selected"]')
                        text = _get_text(curent_ul)
                        if text:
                            __categories.insert(0, text.strip())

                        while curent_ul:
                            curent_ul = curent_ul.xpath(
                                'parent::li/parent::ul/preceding::li[1]/a')
                            text = _get_text(curent_ul)
                            if text:
                                __categories.insert(0, text.strip())
                            if text.strip().startswith('Any'):
                                break

                        return __categories

                    shelf_categories = __parse_category()
                    shelf_category = shelf_categories[-1] if shelf_categories \
                        else None

                    for i, li in enumerate(ul):
                        link = is_empty(li.xpath(
                            './/div[@class="zg_itemImageImmersion"]/a/@href'
                        ).extract())

                        if not link:
                            link = is_empty(li.xpath(".//a/@href").extract())

                        if not link:
                            continue

                        if not "http" in link:
                            link = urlparse.urljoin(response.url, link)

                        prod = SiteProductItem(
                            ranking=i,
                            shelf_path=shelf_categories,
                            shelf_name=shelf_category
                        )
                        self.log(str(prod), WARNING)
                        yield Request(
                            link.strip(),
                            callback=self.parse_product,
                            headers={
                                'Referer': None
                            },
                            meta={
                                'product': prod
                            }
                        ), prod

                    return

            if links:
                for link, is_prime, is_prime_pantry, is_sponsored in links:
                    prime = None
                    if is_prime:
                        prime = 'Prime'
                    if is_prime_pantry:
                        prime = 'PrimePantry'
                    prod = SiteProductItem(
                        prime=prime, shelf_path=shelf_categories,
                        shelf_name=shelf_category, is_sponsored_product=is_sponsored)
                    yield Request(link, callback=self.parse_product,
                                  headers={'Referer': None},
                                  meta={'product': prod}), prod

    def _start_scrape_goldbox_links(self, response):
        all_deal_targets, data = self._get_goldbox_payload(response)
        # prepare payload list
        payload_list = []
        for deal_targets in all_deal_targets:
            cp_data = data.copy()

            cp_data["dealTargets"] = deal_targets
            payload_list.append(cp_data)

        current_payload = payload_list.pop(0)
        no_cache = randint(1480238000000, 1480238999999)
        req = Request(url='https://www.amazon.ca/xa/dealcontent/v2/GetDeals?nocache={0}'.format(no_cache),
                          method="POST",
                          body=json.dumps(current_payload),
                          callback=self._parse_goldbox_deals
                          )
        req.meta["payload_list"] = payload_list
        yield req

    def _get_goldbox_payload(self, response):
        # not a callback, just a method to get payload for ajax requests
        marketplace_id = self._find_between(response.body, "ue_mid='", "',")
        session_id = self._find_between(response.body, "ue_sid='", "',")
        sorted_deal_ids = self._find_between(response.body, '"sortedDealIDs" : [', "],").split(",")
        sorted_deal_ids = [deal_id.strip()[1:-1] for deal_id in sorted_deal_ids]
        self.sorted_goldbox_deals_ids = sorted_deal_ids
        deal_targets_1 = []
        deal_targets_2 = []
        deal_targets_3 = []

        for index in range(12):
            deal_targets_1.append({"dealID": sorted_deal_ids[index]})

        for index in range(12, 24):
            deal_targets_2.append({"dealID": sorted_deal_ids[index]})

        for index in range(24, 32):
            deal_targets_3.append({"dealID": sorted_deal_ids[index]})

        reference_id = self._find_between(response.body, '"originRID" : "', '",')
        widget_id = self._find_between(response.body, '"widgetID" : "', '",')
        slot_name = self._find_between(response.body, '"slotName" : "', '"')

        data = {"requestMetadata":
                    {"marketplaceID": marketplace_id,
                     "clientID": "goldbox_mobile_pc",
                     "sessionID": session_id},
                "dealTargets": None,
                "responseSize": "ALL",
                "itemResponseSize": "DEFAULT_WITH_PREEMPTIVE_LEAKING",
                "widgetContext": {"pageType": "GoldBox",
                                  "subPageType": "Alldeals",
                                  "deviceType": "pc",
                                  "refRID": reference_id,
                                  "widgetID": widget_id,
                                  "slotName": slot_name}}
        return (deal_targets_1, deal_targets_2, deal_targets_3), data

    def _parse_goldbox_deals(self, response):
        payload_list = response.meta.get("payload_list")
        deal_product_url_dict = {}
        self.deal_response_json_list.append(json.loads(response.body))
        # payload_list is empty, we done all 3 requests needed. Generate product urls.
        if not payload_list:
            for deal_response_json in self.deal_response_json_list:
                for deal in deal_response_json.get("dealDetails", {}):
                    egressurl = deal_response_json.get("dealDetails", {}).get(deal, {}).get("egressUrl", '')
                    if egressurl:
                        deal_product_url_dict[deal] = egressurl
                    else:
                        deal_asin = deal_response_json.get("dealDetails", {}).get(deal, {}).get("impressionAsin", '')
                        if deal_asin:
                            deal_product_url_dict[deal] = "https://www.amazon.ca/dp/{}".format(deal_asin)
                        else:
                            self.log("No asin forund for deal id {}".format(deal), WARNING)

            # Generating a list with correctly ordered product urls, important for rankings
            for deal_id in self.sorted_goldbox_deals_ids:
                # We need only first 32 products in right order
                try:
                    self.deal_product_url_list.append(deal_product_url_dict[deal_id])
                except:
                    # TODO self.sorted_goldbox_deals_ids contains sorted ids for more than one page
                    # may do more requests previously and get urls for next pages here
                    pass
            yield Request(
                        self.valid_url(self.product_url),
                        meta={
                            'search_term': '',
                            'remaining': self.quantity
                        },
                        callback=self.parse,
                        dont_filter=True
                        )
        else:
            # not all request are done, call itself again
            current_payload = payload_list.pop(0)
            no_cache = randint(1480238000000, 1480238999999)
            req = Request(url='https://www.amazon.ca/xa/dealcontent/v2/GetDeals?nocache={0}'.format(no_cache),
                          method="POST",
                          body=json.dumps(current_payload),
                          callback=self._parse_goldbox_deals,
                          dont_filter=True
                          )
            req.meta["payload_list"] = payload_list
            yield req

    def _generate_goldbox_links_from_deals(self, response):
        shelf_categories = [c.strip() for c in response.xpath(
            ".//*[@id='s-result-count']/span/*/text()").extract()
                            if len(c.strip()) > 1]
        shelf_category = shelf_categories[-1] if shelf_categories else None

        for index, link in enumerate(self.deal_product_url_list):
            prod = SiteProductItem(ranking=index,
                                   shelf_path=shelf_categories,
                                   shelf_name=shelf_category)
            yield Request(link, callback=self.parse_product,
                          headers={'Referer': None},
                          meta={'product': prod}), prod

    def _find_between(self, s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= self.num_pages:
            return

        self.current_page += 1

        next_link = super(AmazonCaShelfPagesSpider, self)._scrape_next_results_page_link(response)
        if next_link:
            return next_link

        next_link = response.xpath(".//*[@class='zg_pagination']/*[contains(@class,'zg_selected')]"
                                   "/following-sibling::*[1]/a/@href").extract()
        if next_link:
            return next_link[0]
