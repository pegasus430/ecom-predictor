# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, unicode_literals

import json
import re
import urlparse

from scrapy import Request

from product_ranking.items import SiteProductItem
from product_ranking.spiders.att import ATTProductsSpider


class ATTShelfPagesSpider(ATTProductsSpider):
    name = "att_shelf_urls_products"
    allowed_domains = ["att.com",
                       'api.bazaarvoice.com',
                       'recs.richrelevance.com']

    JSON_PAGINATE_URL = ''
    HTML_PAGINATE_URL = ''

    def __init__(self, *args, **kwargs):
        self.current_page = 1
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', 1))
        self.shelf_categories = []
        self.page_size = 12
        self.total_matches = 0

        super(ATTShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        if self.product_url:
            yield Request(self.product_url, callback=self._get_stats_firstpage)

    def _get_stats_firstpage(self, response):
        bc = response.xpath('.//*[@class="breadcrumb"]//*/text()').extract()
        shelf_categories = [c.replace('/', '').strip() for c in bc if len(c.strip()) > 1 and not c.strip() == "/"]
        self.shelf_categories = shelf_categories
        item_urls = response.xpath(
            './/*[@class="list-title" or @class="listGridAcc-title" or'
            ' @class="listGridAcc-titleWithBanner"]//a[contains(@class, "clickStreamSingleItem") '
            'or contains(@id, "list-title_")]/@href').extract()
        self.page_size = len(item_urls) if item_urls else 0
        # now lets get proper url for first page
        js_code = response.xpath('.//*[contains(text(),"setlayoutURL")]/text()').extract()
        js_code = js_code[0] if js_code else None
        # here we decide how we will parse first page
        exclusions = ["/hotspots", '/child-gps-locators', ]
        any_true = [e for e in exclusions if e in response.url]
        print any_true
        if any_true:
            yield Request(response.url, callback=self.parse,
                          meta={'search_term': '', 'remaining': self.quantity}, dont_filter=True)
        else:
            if js_code:
                self.JSON_PAGINATE_URL = self._build_base_json_pagination_link(js_code)
                if self.JSON_PAGINATE_URL:
                    proper_link = self.JSON_PAGINATE_URL.format(more_list_size=self.page_size)
                    if '/smartphones' in response.url and not "SMARTPHONES" in proper_link:
                        proper_link += '&taxoStyle=SMARTPHONES'
                    yield Request(proper_link, callback=self.parse,
                                  meta={'search_term': '', 'remaining': self.quantity}, )
                else:
                    # JS code broken, backup plan
                    print "Cant build json pagination link, paring first page only"
                    yield Request(response.url, callback=self.parse,
                                  meta={'search_term': '', 'remaining': self.quantity}, dont_filter=True)

            else:
                self.HTML_PAGINATE_URL = self._build_base_html_pagination_link(response)
                # 13 is magic number hardcoded somewhere in js code
                if self.page_size == 13 or self.page_size == 17:
                    self.page_size = 30
                    simple_firstpage_link = self.HTML_PAGINATE_URL.replace('&offset=1&offsetValue={offset_value}','')
                    proper_link = simple_firstpage_link.format(page_size=self.page_size)
                    yield Request(proper_link, callback=self.parse,
                                  meta={'search_term': '', 'remaining': self.quantity}, )
                else:
                    yield Request(response.url, callback=self.parse,
                                  meta={'search_term': '', 'remaining': self.quantity}, dont_filter=True)


    def _scrape_product_links(self, response):
        item_urls = []
        if '.json' in response.url:
            # try:
            js_response = json.loads(response.body_as_unicode())
            item_list = js_response.get('devices')
            if item_list:
                for item in item_list:
                    item_url = item.get('product').get('url')
                    if item_url:
                        # thats temporary
                        if 'sku6320484' in item_url:
                            item_url = '/tablets/ipad/ipad-retina.html#sku=sku6320484'
                        item_urls.append(item_url)
                    else:
                        body = item.get('usingTheBody')
                        item_url = re.search(r"a\s?href\s?=\s?[^/]+(/[^;]+)", body)
                        item_url = item_url.group(1) if item_url else None
                        if item_url:
                            item_url = 'https://www.att.com{}'.format(item_url)
                            item_urls.append(item_url)
                # since page don't have proper pagination, we remove duplicate items from beginning of the list
                # to not have problems with ranking later
                dup_items_quant = (self.current_page - 1) * self.page_size
                next_items_quant = self.current_page * self.page_size
                # apparently it returns full item json each time
                item_urls = item_urls[dup_items_quant:next_items_quant]
            else:
                item_urls = []
        else:
            item_urls = response.xpath(
                './/*[@class="list-title" or @class="listGridAcc-title" or'
                ' @class="listGridAcc-titleWithBanner"]//a[contains(@class, "clickStreamSingleItem") '
                'or contains(@id, "list-title_")]/@href').extract()

        shelf_categories = self.shelf_categories
        shelf_category = shelf_categories[-1] if shelf_categories else None
        for item_url in item_urls:
            sku = re.search('sku=(.*)', item_url)
            if sku:
                sku = sku.group(1).strip()
            item = SiteProductItem()
            if shelf_category:
                item['shelf_name'] = shelf_category
            if shelf_categories:
                item['shelf_path'] = shelf_categories
            req = Request(
                url=urlparse.urljoin(response.url, item_url),
                callback=self.parse_product,
                meta={
                    "product": item,
                    'search_term': '',
                    'remaining': self.quantity,
                    'sku': sku
                },
                dont_filter=True,
            )
            yield req, item

    @staticmethod
    def _build_base_json_pagination_link(js_code):
        js_url = "https://www.att.com{base_url}flowtype-NEW.deviceGeoTarget-US.deviceGroupType-{dev_group_type}" \
                 ".paymentType-{payment_type}.packageType-undefined.json"

        base_url = re.findall(r"ATT.listPage.setlayoutURL\s?\(\s?[\'\"]([\/a-zA-Z.]+)", js_code)
        base_url = base_url[0].replace('html','').replace('htm','') if base_url else None
        # Yes, missed letter in 'Type' is "intentional".
        dev_group_type = re.search(r"ATT.listPage.setdeviceTye\s?\(\s?[\'\"]([\/a-zA-Z.]+)", js_code)
        dev_group_type = dev_group_type.group(1) if dev_group_type else None
        payment_type = re.search(r"ATT.listPage.setpaymentType\s?\(\s?[\'\"]([\/a-zA-Z.]+)", js_code)
        payment_type = payment_type.group(1) if payment_type else None
        pagination_url = js_url.format(base_url=base_url,
                                       dev_group_type=dev_group_type,
                                       payment_type=payment_type,
                                       )
        # taxo style is only used for smartphones, dont you dare use it on anything else
        taxo_style = re.search(r"filetrDefault\s?=\s?[\'\"]([A-Z]+)", js_code)
        taxo_style = taxo_style.group(1) if taxo_style else None
        pagination_url += "?showMoreListSize={more_list_size}"
        if taxo_style and 'SMARTPHONES' in taxo_style:
            pagination_url += "&taxoStyle={taxo_style}".format(taxo_style=taxo_style)
        if not base_url or not dev_group_type:
            return ''
        return pagination_url

    @staticmethod
    def _build_base_html_pagination_link(response):
        htm_url = "{base_url}.accessoryListGridView.html" \
                  "?taxoCategory={taxo_style}&sortByProperties=bestSelling"
        base_url = re.search(r'([\w,:/.]+www.att.com[\w,:/]+)', response.url)
        base_url = base_url.group(1) if base_url else ''
        taxo_style = response.xpath('.//*[@class="listFilterGroup focus" and @name="taxoCategory"]/@value').extract()
        taxo_style = ','.join(taxo_style) if taxo_style else ''
        pagination_url = htm_url.format(base_url=base_url, taxo_style=taxo_style)
        pagination_url += '&showMoreListSize={page_size}&offset=1&offsetValue={offset_value}'#&_=1468851715141'
        return pagination_url

    def _scrape_next_results_page_link(self, response):
        if list(self._scrape_product_links(response)):
            self.current_page += 1
            if self.JSON_PAGINATE_URL:
                # probably devices category, use json link
                more_list_size = self.current_page * self.page_size
                next_link = self.JSON_PAGINATE_URL.format(more_list_size=more_list_size)
            elif self.HTML_PAGINATE_URL:
                # prob accessories category, use html link
                offset = ((self.current_page - 1) * self.page_size) + 1
                next_link = self.HTML_PAGINATE_URL.format(page_size=self.page_size, offset_value=offset)
            else:
                print "end of pagination reached"
                return None
            return next_link
        else:
            return None

    def _scrape_total_matches(self, response):
        if '.json' in response.url:
            js_response = json.loads(response.body_as_unicode())
            item_list = js_response.get('devices')
            result_count = len(item_list)
        else:
            result_count = re.search(r'var\s?v_accessorySize\s?=\s?(\d+);', response.body_as_unicode())
            result_count = result_count.group(1) if result_count else ''
        if result_count:
            if not isinstance(result_count, int):
                if result_count.isdigit():
                    result_count = int(result_count)
                else:
                    result_count = 0
            return result_count
        else:
            result_count = len(list(self._scrape_product_links(response)))
            return result_count

