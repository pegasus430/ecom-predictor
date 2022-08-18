# ~~coding=utf-8~~
from __future__ import division, absolute_import, unicode_literals

from itertools import islice
import re

from scrapy.log import ERROR, WARNING, INFO
from scrapy.http import Request, FormRequest

from product_ranking.items import SiteProductItem
from product_ranking.marketplace import Amazon_marketplace
from product_ranking.spiders import cond_set_value

from .amazon import AmazonProductsSpider
import urlparse
from random import randint
import json


is_empty = lambda x: x[0] if x else None


class AmazonShelfPagesSpider(AmazonProductsSpider):
    name = 'amazon_shelf_urls_products'

    # without this find_spiders() fails
    allowed_domains = ["amazon.com", "www.amazon.com"]

    def _setup_class_compatibility(self):
        """ Needed to maintain compatibility with the SC spiders baseclass """
        self.quantity = 99999
        self.site_name = self.allowed_domains[0]
        self.user_agent_key = None
        self.current_page = 1

    @staticmethod
    def _setup_meta_compatibility():
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': 99999, 'search_term': ''}.copy()

    def __init__(self, *args, **kwargs):
        self.product_url = kwargs['product_url']

        # See https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=3313#c0
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.num_pages = min(10, self.num_pages)

        # Default price currency
        self.price_currency = 'USD'
        self.price_currency_view = '$'

        # Locale
        self.locale = 'en-US'

        self.mtp_class = Amazon_marketplace(self)

        # #backup when total matches cannot be scraped
        # self.total_items_scraped = 0
        # # self.ranking_override = 0
        self.total_matches_re = r'of\s([\d\,]+)\s'
        self.other_total_matches_re = r'([\d,\s]+)results\sfor'
        self.over_matches_re = r'over\s?([\d,.\s?]+)'

        super(AmazonShelfPagesSpider, self).__init__(*args, **kwargs)
        # We don't use those in shelf reports
        self.ignore_variant_data = True
        self.scrape_reviews = True

        self._setup_class_compatibility()

        # For goldbox deals
        self.deal_response_json_list = []
        self.deal_product_url_list = []
        self.sorted_goldbox_deals_ids = []

        self.detect_shelf_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_shelf_ads = True

    @staticmethod
    def valid_url(url):
        if not url.startswith('http'):
            url = 'http://' + url
        return url

    def start_requests(self):
        if not "/goldbox/" in self.product_url:
            request = Request(
                self.valid_url(self.product_url),
                meta={
                    'search_term': '',
                    'remaining': self.quantity
                },
            )
            if self.detect_shelf_ads:
                request = request.replace(callback=self._start_ads_requests)

            yield request
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
        meta = response.meta.copy()
        links = meta.get('items')
        if links:
            meta['items'] = None
            sponsored_links = meta.get('sponsored_links')

            if self.detect_shelf_ads is True and not sponsored_links:
                sponsored_links = self._get_sponsored_links(response)

            for link, is_prime, is_prime_pantry, is_sponsored in links:
                prime = None
                if is_prime:
                    prime = 'Prime'
                if is_prime_pantry:
                    prime = 'PrimePantry'
                prod_item = SiteProductItem(prime=prime)
                if self.detect_shelf_ads is True:
                    prod_item['ads'] = meta.get('ads')
                    prod_item['sponsored_links'] = sponsored_links

                req = Request(
                    url=link,
                    callback=self.parse_product,
                    headers={'Referer': None},
                    meta={
                        "product": prod_item
                    },
                    dont_filter=True
                )
                yield req, prod_item

        else:
            shelf_categories = [c.strip() for c in response.xpath(
                ".//*[@id='s-result-count']/span/*/text()").extract()
                                if len(c.strip()) > 1]
            shelf_category = shelf_categories[-1] if shelf_categories else None

            try:
                lis = response.xpath(
                    "//li[contains(@id, 'result')]")
                if not lis:
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
                        idx = self._is_empty(
                            re.findall(r'\d+', data_asin)
                        )
                        if idx:
                            idx = int(idx)
                        else:
                            continue
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

            links2 = []
            try:
                if not links:
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

            links += links2

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

                    prod['ads'] = meta.get('ads') if self.detect_shelf_ads is True else None

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

                    # break

                if ul:
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
                    prod['ads'] = meta.get('ads') if self.detect_shelf_ads is True else None

                    yield Request(link, callback=self.parse_product,
                                  headers={'Referer': None},
                                  meta={'product': prod}), prod

    def _get_products(self, response):
        remaining = response.meta['remaining']
        search_term = response.meta['search_term']
        prods_per_page = response.meta.get('products_per_page')
        total_matches = response.meta.get('total_matches')
        scraped_results_per_page = response.meta.get('scraped_results_per_page')

        if self.deal_product_url_list:
            prods = self._generate_goldbox_links_from_deals(response)
        else:
            prods = self._scrape_product_links(response)

        if prods_per_page is None:
            # Materialize prods to get its size.
            prods = list(prods)
            prods_per_page = len(prods)
            response.meta['products_per_page'] = prods_per_page

        if scraped_results_per_page is None:
            scraped_results_per_page = self._scrape_results_per_page(response)
            if scraped_results_per_page:
                self.log(
                    "Found %s products at the first page" %scraped_results_per_page
                    , INFO)
            else:
                scraped_results_per_page = prods_per_page
                if hasattr(self, 'is_nothing_found'):
                    if not self.is_nothing_found(response):
                        self.log(
                            "Failed to scrape number of products per page", WARNING)
            response.meta['scraped_results_per_page'] = scraped_results_per_page

        if total_matches is None:
            total_matches = self._scrape_total_matches(response)
            if total_matches is not None:
                response.meta['total_matches'] = total_matches
                self.log("Found %d total matches." % total_matches, INFO)
            else:
                if hasattr(self, 'is_nothing_found'):
                    if not self.is_nothing_found(response):
                        self.log(
                            "Failed to parse total matches for %s" % response.url,WARNING)

        if total_matches and not prods_per_page:
            # Parsing the page failed. Give up.
            self.log("Failed to get products for %s" % response.url, WARNING)
            return

        for i, (prod_url, prod_item) in enumerate(islice(prods, 0, remaining)):
            # Initialize the product as much as possible.
            prod_item['site'] = self.site_name
            prod_item['search_term'] = search_term
            prod_item['total_matches'] = total_matches
            prod_item['results_per_page'] = prods_per_page
            prod_item['scraped_results_per_page'] = scraped_results_per_page
            # The ranking is the position in this page plus the number of
            # products from other pages.
            prod_item['ranking'] = (i + 1) + (self.quantity - remaining)
            if self.user_agent_key not in ["desktop", "default"]:
                prod_item['is_mobile_agent'] = True

            if prod_url is None:
                # The product is complete, no need for another request.
                yield prod_item
            elif isinstance(prod_url, Request):
                cond_set_value(prod_item, 'url', prod_url.url)  # Tentative.
                yield prod_url
            else:
                # Another request is necessary to complete the product.
                url = urlparse.urljoin(response.url, prod_url)
                cond_set_value(prod_item, 'url', url)  # Tentative.
                yield Request(
                    url,
                    callback=self.parse_product,
                    meta={'product': prod_item},
                )

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
        req = Request(url='https://www.amazon.com/xa/dealcontent/v2/GetDeals?nocache={0}'.format(no_cache),
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
                            deal_product_url_dict[deal] = "https://www.amazon.com/dp/{}".format(deal_asin)
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
            req = Request(url='https://www.amazon.com/xa/dealcontent/v2/GetDeals?nocache={0}'.format(no_cache),
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
        next_link = super(AmazonShelfPagesSpider, self)._scrape_next_results_page_link(response)
        if next_link:
            return next_link

    def _get_sponsored_links(self, response):
        sponsored_links = response.xpath("//a[contains(@class, 's-access-detail-page')]/@href").extract()
        return sponsored_links

    def _parse_total_matches(self, response):
        return self._scrape_total_matches(response)

    def _get_ads_path(self):
        return ["//div[@class='acs-shwcs-image-single']//a",
                "//div[@class='acsUxWidget']//div[contains(@class, 'bxc-grid__column--12-of-12')]"
                "//div[contains(@class, 'bxc-grid__image')]//a"]

    def _get_product_links(self, response):
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

            is_sponsored = bool(li.xpath('.//h5[contains(text(), "ponsored")]').extract())

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

        if not links:
            self.log("Found no product links.")

        return links

    def _get_products_info(self, response):
        items = []
        special_product_info = []
        product_info = response.xpath("//a[contains(@class, 's-access-detail-page')]")
        if not product_info:
            special_product_info = response.xpath("//div[@class='a-carousel-viewport']")
        if special_product_info:
            product_info = special_product_info[0].xpath(".//a[contains(@class, 'a-size-small')]")
        for prod in product_info:
            item = {}
            item['name'] = ''.join(prod.xpath("./@title").extract())
            item['url'] = ''.join(prod.xpath("./@href").extract())
            items.append(item)

        return items

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')

        products = None
        m = re.match(r'https://www.amazon.com/gp/product/[A-Za-z\d]{10}/.*', response.url)
        if bool(m) is True:
            name = self._parse_title(response)
            products = [
                {
                    'url': response.url,
                    'name': name,
                }
            ]
        else:
            products_info = self._get_products_info(response)
            if products_info:
                products = [
                    {
                        'url': item['url'],
                        'name': item['name'],
                    } for item in products_info
                ]

        ads[ads_idx]['ad_dest_products'] = products
        response.meta['ads'] = ads

        ads_idx += 1
        if ads_idx < len(ads_urls):
            link = ads_urls[ads_idx]
            response.meta['ads_idx'] += 1

            return Request(
                url=link,
                meta=response.meta,
                callback=self._parse_ads_product,
                dont_filter=True
            )
        else:
            return self.parse(response)

    def _start_ads_requests(self, response):
        meta = response.meta.copy()
        ads = []

        ads_urls = []
        image_urls = []
        for ads_xpath in self._get_ads_path():
            ad_groups = response.xpath(ads_xpath)
            for ad_group in ad_groups:
                ad_url = ad_group.xpath('./@href').extract()
                ad_image = ad_group.xpath('.//img/@src').extract()
                if not ad_image:
                    ad_image = ad_group.xpath('.//img/@data-src').extract()

                if ad_url and ad_image:
                    ad_url = urlparse.urljoin(response.url, ad_url[0])
                    ad_image = urlparse.urljoin(response.url, ad_image[0])
                    ads.append({
                        'ad_url': ad_url,
                        'ad_image': ad_image
                    })
                    ads_urls.append(ad_url)
                    image_urls.append(ad_image)

        items = self._get_product_links(response)
        totals = self._parse_total_matches(response)
        next_link = self._parse_next_page_link(response)
        meta['totals'] = totals
        meta['next_link'] = next_link
        meta['items'] = items

        sponsored_links = self._get_sponsored_links(response)
        meta['sponsored_links'] = sponsored_links

        if ads_urls:
            meta['ads_idx'] = 0
            meta['image_urls'] = image_urls
            meta['ads_urls'] = ads_urls
            meta['ads'] = ads

            return Request(
                url=ads_urls[0],
                meta=meta,
                callback=self._parse_ads_product,
                dont_filter=True,
            )
        else:
            return self.parse(response)

    def _parse_next_page_link(self, response):
        next_page = response.xpath('//span[@class="pagnRA"]/a[@class="pagnNext"]'
                                   '/@href').extract()
        if next_page:
            next_page = urlparse.urljoin(response.url, next_page[0])
            return next_page
