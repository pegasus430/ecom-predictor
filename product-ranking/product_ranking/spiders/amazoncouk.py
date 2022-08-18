# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function

import json
import traceback
import urllib
import urlparse
from datetime import datetime

import re
from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.items import SiteProductItem
from product_ranking.utils import is_empty
from scrapy.http import Request, FormRequest
from scrapy.log import ERROR, WARNING
from scrapy.selector import Selector
from scrapy.conf import settings


class AmazonProductsSpider(AmazonBaseClass):
    name = "amazoncouk_products"
    allowed_domains = ["www.amazon.co.uk", "amazon.com"]

    SEARCH_URL = 'https://{domain}/s/ref=nb_sb_noss_1?url=field-keywords={search_term}'
    ADS_PRODUCT_URLS = "https://www.amazon.co.uk/ams/getAsins/details?sEcho=2&iColumns=1" \
                       "&sColumns=&iDisplayStart=0&iDisplayLength=-1&mDataProp_0=0&asins={}&merchantId=&_=1506992959437"

    handle_httpstatus_list = [503]

    fresh_cookies = {
        "csm-hit": "09RVG4WB2W1A49JWXZAF+s-SG1ZK0EEPNPE4EM514DG|1508280606345",
        "lc-acbuk": "en_GB",
        "session-id": "262-4982414-1378213",
        "session-token": "HpCcW+sdWDFyPSCoK4eXCWx/4l80uQUT7ENiLgZm6PKo8gt5JEPQEkmrn6GjcQWLuaqg290oRMJV/" \
                         "ALy3aPOmIDtNQdoJzN3NgvHG9tnHrX0S/CYJQIzInNRayWpmV0zSRJz9hWSp0JAL2sMuEGdmbMySn5+cvGXATbn12J+T5" \
                         "new4TDbTDvDh5rheu80zDNbUUFXcX2ltdjRnMJU8hwjsq2rSRgNsrSuDPaZBgaokUsHYeRSOz71cypjymXq6YG",
        "ubid-acbuk": "258-2227148-8106401",
        "x-wl-uid": "1HPg4fV/XDO302Z/+f3weGk++t2wfaDxkL22GyVI21Mu8kGqHKB2m8PLFZV0nYsLbmBMLPFT5xgc="
    }

    # REVIEW_DATE_URL = "https://www.amazon.co.uk/product-reviews/" \
    #                   "{product_id}/ref=cm_cr_pr_top_recent?" \
    #                   "ie=UTF8&showViewpoints=0&" \
    #                   "sortBy=bySubmissionDateDescending"

    QUESTIONS_URL = "https://www.amazon.co.uk/ask/questions/inline/{asin_id}/{page}"

    SET_ZIP_CODE_URL = "https://www.amazon.co.uk/gp/delivery/ajax/address-change.html"

    # REVIEW_URL_1 = 'https://{domain}/ss/customer-reviews/ajax/reviews/get/ref=cm_cr_arp_d_hist_{star_idx}'

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        # String from html body that means there's no results ( "no results.", for example)
        self.total_match_not_found_re = 'did not match any products.'
        # Regexp for total matches to parse a number from html body
        self.total_matches_re = r'of\s?([\d,.\s?]+)'
        self.over_matches_re = r'over\s?([\d,.\s?]+)'

        # Price currency
        self.price_currency = 'GBP'
        self.price_currency_view = '£'

        # Locale
        self.locale = 'en_GB'

        self.zip_code = kwargs.get('zip_code', 'EC2R 6AB')

        self.is_fresh = self.search_alias == "amazonfresh"

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

        self.scrape_reviews = True

        retry_http_codes = settings.get('RETRY_HTTP_CODES')
        if 404 in retry_http_codes:
            retry_http_codes.remove(404)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)" \
                          " Chrome/65.0.3325.181 Safari/537.36"

    def _format_last_br_date(self, date):
        """
        Parses date that is gotten from HTML.
        """
        date = self._is_empty(
            re.findall(
                r'on (\d+ \w+ \d+)', date
            ), ''
        )

        if date:
            date = date.replace(',', '').replace('.', '')

            try:
                d = datetime.strptime(date, '%d %B %Y')
            except ValueError:
                d = datetime.strptime(date, '%d %b %Y')

            return d

        return None

    def start_requests(self):
        for st in self.searchterms:
            data = {
                'locationType': 'LOCATION_INPUT',
                'zipCode': self.zip_code,
                'deviceType': 'web',
                'pageType': 'Search',
                'actionSource': 'glow'
            }
            yield Request(
                url=self.SET_ZIP_CODE_URL,
                method='POST',
                body=urllib.urlencode(data),
                meta={'search_term': st},
                headers={'content-type': 'application/x-www-form-urlencoded;charset=UTF-8'},
                callback=self._search_with_zip_code
            )

        if self.product_url:
            if self.is_fresh:
                self.product_url = self._build_fresh_product_link(self.product_url)
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            prod['fresh'] = self.is_fresh
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod},
                          cookies=self.fresh_cookies if self.is_fresh else None)

    def _search_with_zip_code(self, response):
        st = response.meta.get('search_term')
        request = Request(
            self.url_formatter.format(
                self.SEARCH_URL,
                search_term=urllib.quote_plus(st.encode('utf-8')),
            ),
            meta={'search_term': st, 'remaining': self.quantity},
        )

        if self.detect_ads:
            request = request.replace(callback=self._get_ads_product)
        if self.is_fresh:
            request = request.replace(cookies=self.fresh_cookies)
        yield request

    def _parse_prime_pantry(self, response):
        if response.xpath('//img[@id="pantry-badge"]').extract():
            return 'PrimePantry'
        if response.css('.feature i.a-icon-prime').extract():
            return 'Prime'

    def _parse_price_per_volume(self, response):
        xpathes = '//span[@class="a-size-small a-color-price"]/text() |' \
                  '//span[@class="a-color-price a-size-small"]/text() |' \
                  '//tr[@id="priceblock_dealprice_row"]//td/text()'

        price_volume = response.xpath(xpathes).re(r'\(.*\/.*\)')
        if price_volume:
            try:
                groups = re.sub(r'[()]', '', price_volume[0]).split('/')
                price_per_volume = float(re.findall(r'\d*\.\d+|\d+', groups[0])[0])
                volume_measure = groups[1].strip()

                return price_per_volume, volume_measure
            except Exception as e:
                self.log("Can't extract price per volume {}".format(traceback.format_exc(e)), WARNING)

    def _search_page_error(self, response):
        sel = Selector(response)

        try:
            found1 = sel.xpath('//div[@class="warning"]/p/text()').extract()[0]
            found2 = sel.xpath(
                '//div[@class="warning"]/p/strong/text()'
            ).extract()[0]
            found = found1 + " " + found2
            if 'did not match any products' in found:
                self.log(found, ERROR)
                return True
            return False
        except IndexError:
            return False

    def _extract_save_block(self, response, save_block_regexp='//tr[contains(., "You Save:")]//td/text()'):
        return super(AmazonProductsSpider, self)._extract_save_block(
            response,
            save_block_regexp
        )

    def _scrape_total_matches(self, response):
        meta = response.meta.copy()
        totals = meta.get('totals')
        if not totals:
            totals = self._parse_total_matches(response)
        return totals

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        items = meta.get('items')
        if not items:
            items = self._get_product_links(response)
        else:
            meta['items'] = None

        sponsored_links = meta.get('sponsored_links')
        st = meta.get('search_term')

        if self.detect_ads is True and not sponsored_links:
            sponsored_links = self._get_sponsored_links(response)

        if items:
            for link, is_prime, is_prime_pantry, is_sponsored in items:
                prime = None
                if is_prime:
                    prime = 'Prime'
                if is_prime_pantry:
                    prime = 'PrimePantry'
                prod_item = SiteProductItem(prime=prime)
                if self.detect_ads is True:
                    prod_item['ads'] = meta.get('ads')
                    prod_item['sponsored_links'] = sponsored_links

                prod_item['fresh'] = self.is_fresh

                req = Request(
                    url=link,
                    callback=self.parse_product,
                    headers={'Referer': None},
                    meta={
                        "product": prod_item,
                        'search_term': st,
                        'remaining': self.quantity,
                    },
                    dont_filter=True
                )
                yield req, prod_item

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        next_link = meta.get('next_link')
        if not next_link:
            next_link = self._parse_next_page_link(response)
        if next_link:
            return next_link

    def _get_ads_product(self, response):
        meta = response.meta.copy()
        ads = []

        ads_urls = response.xpath("//a[contains(@class, 'textLink')]/@href").extract()
        image_urls = response.xpath(
            "//div[@class='imageContainer']//img[@class='mediaCentralImage imageContainer__image']/@src").extract()

        items = self._get_product_links(response)
        totals = self._parse_total_matches(response)
        next_link = self._parse_next_page_link(response)
        meta['totals'] = totals
        meta['next_link'] = next_link
        meta['items'] = items

        sponsored_links = self._get_sponsored_links(response)
        meta['sponsored_links'] = sponsored_links

        for i, url in enumerate(ads_urls):
            ad = {
                'ad_url': url,
                'ad_image': image_urls[i]
            }
            ads.append(ad)
        if ads_urls and items:
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

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')

        products_info = self._get_products_info(response)
        if products_info:
            for item in products_info:
                if not item.get('name') and item.get('asins'):
                    return Request(
                        url=self.ADS_PRODUCT_URLS.format(item.get('asins')),
                        callback=self._parse_ads_api_product,
                        meta=response.meta,
                        dont_filter=True
                    )
                products = [
                    {
                        'url': item['url'],
                        'name': item['name'],
                    }
                ]

            ads[ads_idx]['ad_dest_products'] = products
        response.meta['ads'] = ads

        ads_idx += 1
        if ads_idx < len(ads_urls):
            link = ads_urls[ads_idx]
            response.meta['ads_idx'] += 1
        else:
            return self.parse(response)

        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_product,
            dont_filter=True
        )

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
            self.log("Found no product links.", WARNING)

        return links

    def _get_sponsored_links(self, response):
        sponsored_links = response.xpath("//a[contains(@class, 's-access-detail-page')]/@href").extract()
        return sponsored_links

    def _get_products_info(self, response):
        items = []
        product_info = response.xpath("//a[contains(@class, 's-access-detail-page')]")
        try:
            asins = json.loads(re.search('aoData.push\((.*?)\);', response.body).group(1))
            asins = asins.get('value')
        except:
            self.log('Error while parsing asins{}'.format(traceback.format_exc()))
            asins = None

        item = {}
        if not product_info and asins:
            item['asins'] = asins
            items.append(item)
        elif product_info:
            for prod in product_info:
                item = {}
                item['name'] = prod.xpath("./@title").extract()
                item['url'] = prod.xpath("./@href").extract()
                items.append(item)
        return items

    def _parse_ads_api_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')
        items = []
        try:
            data = json.loads(response.body)
            prod_data = data.get('aaData', {})
            for dt in prod_data:
                item = {}
                item['name'] = dt['title']
                item['url'] = dt['detailPageUrl']
                items.append(item)
            if items:
                products = [
                    {
                        'url': item['url'],
                        'name': item['name'],
                    } for item in items
                ]

                ads[ads_idx]['ad_dest_products'] = products
            response.meta['ads'] = ads

            ads_idx += 1
            if ads_idx < len(ads_urls):
                link = ads_urls[ads_idx]
                response.meta['ads_idx'] += 1
            else:
                return self.parse(response)

            return Request(
                url=link,
                meta=response.meta,
                callback=self._parse_ads_product,
                dont_filter=True
            )
        except:
            self.log('Error while parsing json data {}'.format(traceback.format_exc()))

    def _parse_total_matches(self, response):
        try:
            total_xpath = is_empty(response.xpath('//*[@id="s-result-count"]/text()').extract())
            if total_xpath:
                total_xpath = total_xpath.replace(',', '')
                total_matches = re.findall(r'\d+', total_xpath)
                if not total_matches:
                    total_matches = re.findall(self.over_matches_re, total_xpath)
                return int(total_matches[-1])
        except:
            self.log("Found no total matches {}".format(traceback.format_exc()))
            return 0

    def _parse_no_longer_available(self, response):
        if response.xpath('//*[contains(@id, "availability")]'
                          '//*[contains(text(), "navailable")]'):  # Unavailable or unavailable
            return True
        if response.xpath('//*[contains(@id, "outOfStock")]'
                          '//*[contains(text(), "navailable")]'):  # Unavailable or unavailable
            return True
        if response.xpath('//*[contains(@class, "availRed")]'
                          '[contains(text(), "navailable")]'):
            return True

        fresh_time_avail = response.xpath('//div[@id="freshAsinLeadTimeMessage_feature_div"]').extract()
        if fresh_time_avail and 'not available' in fresh_time_avail[0]:
            return True

    def _parse_next_page_link(self, response):
        next_page = response.xpath('//span[@class="pagnRA"]/a[@class="pagnNext"]'
                                   '/@href').extract()
        if next_page:
            next_page = urlparse.urljoin(response.url, next_page[0])
            return next_page

    @staticmethod
    def _build_fresh_product_link(url):
        scheme, netloc, link, params, query, fragment = urlparse.urlparse(url)
        if not '=fresh' in query:
            query = urlparse.parse_qsl(query)
            query.append(('ppw', 'fresh'))
            query = urllib.urlencode(query)
        link = urlparse.urlunparse((scheme, netloc, link, params, query, fragment))
        return link

    @staticmethod
    def _parse_product_id(url):
        prod_id = None
        asin_info = urlparse.urlparse(url).path.split('/')[-1]
        m = re.match(r"B[A-Z0-9]{4,20}", asin_info)
        if m:
            prod_id = [m.group()]

        if not prod_id:
            prod_id = re.findall(r'/dp?/(?:product/)?(\w+)/?', url)

        if prod_id and isinstance(prod_id, (list, tuple)):
            prod_id = filter(None, prod_id)
            return prod_id[0] if prod_id else None

    # def _create_get_requests(self, response):
    #     """
    #     Method to create request for every star count.
    #     """
    #     meta = response.meta.copy()
    #     meta['_current_star'] = {}
    #     for star in self.buyer_reviews_stars:
    #         args = '?ie=UTF8&reviewerType=all_reviews&filterByStar={star}&pageNumber=1'.format(star=star)
    #         url = urlparse.urlparse(response.url).path + args
    #         meta['_current_star'] = star
    #         yield Request(
    #             urlparse.urljoin(response.url, url),
    #             meta=meta,
    #             callback=self._get_rating_by_star_by_individual_request,
    #             dont_filter=True
    #         )
    #
    # def _create_post_requests(self, response):
    #     """
    #     Method to create request for every star count.
    #     """
    #     meta = response.meta.copy()
    #     meta['_current_star'] = {}
    #     asin = meta['product_id']
    #
    #     for idx, star in enumerate(self.buyer_reviews_stars):
    #         args = {
    #             'asin': asin, 'filterByStar': star,
    #             'filterByKeyword': '', 'formatType': 'all_formats',
    #             'pageNumber': '1', 'pageSize': '10', 'sortBy': 'helpful',
    #             'reftag': 'cm_cr_arp_d_hist_{}'.format(5-idx), 'reviewerType': 'all_reviews',
    #             'scope': 'reviewsAjax0',
    #         }
    #         meta['_current_star'] = star
    #         yield FormRequest(
    #             url=self.REVIEW_URL_1.format(domain=self.allowed_domains[0], star_idx=5-idx),
    #             formdata=args, meta=meta,
    #             callback=self._get_rating_by_star_by_individual_request,
    #             dont_filter=True
    #         )
