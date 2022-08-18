# -*- coding: utf-8 -*-#
import re
import json
import urllib
import urlparse
import traceback
from lxml import html

from scrapy.http import Request
from scrapy.conf import settings

from product_ranking.items import SiteProductItem
from product_ranking.utils import replace_http_with_https

from .sainsburys_uk import SainsburysProductsSpider


class SainsburysUkPagesSpider(SainsburysProductsSpider):
    name = 'sainsburys_uk_shelf_urls_products'
    allowed_domains = ['www.sainsburys.co.uk', 'sainsburysgrocery.ugc.bazaarvoice.com']

    SHELF_URL = "https://www.sainsburys.co.uk/webapp/wcs/stores/servlet/AjaxApplyFilterBrowseView?" \
                "langId=44&storeId=10151&catalogId=10123&categoryId={categoryid}" \
                "&parent_category_rn={top_category}&top_category={top_category}" \
                "&pageSize=36&orderBy={orderby}&searchTerm=&beginIndex={beginindex}&requesttype=ajax"

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

        super(SainsburysUkPagesSpider, self).__init__(*args, **kwargs)

        self.current_page = 1

        self.required_params = ['categoryid', 'top_category', 'orderby', 'beginindex']

        self.product_url = replace_http_with_https(self.product_url)

        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3325.181 Safari/537.36"

    def _setup_meta_compatibility(self):
        """ Needed to prepare first request.meta vars to use """
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        format_parameters = self._parse_required_url_parameters(
            self.product_url,
            self.required_params
        )
        if format_parameters:
            self.product_url = self.SHELF_URL.format(**format_parameters)
            request = Request(
                url=self.product_url,
                dont_filter=True,
                meta=self._setup_meta_compatibility()

            )
        else:
            request = Request(
                url=self.product_url,
                dont_filter=True,
                callback=self._extract_url_data
            )

        if self.detect_ads:
            url = self.product_url.replace('shop/gb/groceries', 'webapp/wcs/stores/servlet/gb/groceries')
            url = url.split('?')
            request = Request(
                url=replace_http_with_https(url[0]),
                callback=self._get_cookies,
                meta={
                    'search_term': '',
                    'remaining': self.quantity,
                    'dont_redirect': True,
                    'handle_httpstatus_list': [302]
                },
            )

        yield request

    def _extract_url_data(self, response):
        format_parameters = {
            param: response.xpath(
                '//input[@type="hidden" and translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ",'
                '"abcdefghijklmnopqrstuvwxyz")="{}"]/@value'.format(param)).extract()[0]
            for param in self.required_params
            }
        if format_parameters:
            self.product_url = self.SHELF_URL.format(**format_parameters)
            yield Request(url=self.product_url,
                          meta=self._setup_meta_compatibility())

    def _scrape_total_matches(self, response):
        try:
            total_matches = re.search(r'(\d+) products available', response.body_as_unicode(), re.DOTALL).group(1)
            if not total_matches:
                json_res = json.loads(response.body_as_unicode())
                total_matches = re.search(r'(\d+)', json_res[0].get('pageHeading'), re.DOTALL).group(1)
            return int(total_matches)
        except:
            self.log("Exception looking for total_matches, Exception Error: {}".format(traceback.format_exc()))
            return 0

    def _scrape_product_links(self, response):
        meta = response.meta.copy()

        items = self._get_product_links(response)[0]

        if items:
            for item in items:
                prod_item = SiteProductItem()
                if self.detect_ads is True:
                    prod_item['ads'] = meta.get('ads')

                req = Request(url=urlparse.urljoin(response.url, item),
                              callback=self.parse_product,
                              meta={
                                  'product': prod_item,
                                  'remaining': self.quantity,
                                  'search_term': ''
                              },
                              dont_filter=True)

                yield req, prod_item
        else:
            self.log("Found no product links in {url}".format(url=response.url))

    def _scrape_next_results_page_link(self, response):
        totals = self._scrape_total_matches(response)
        begin_index = self.current_page * 36

        if begin_index >= totals:
            return None

        if self.current_page < self.num_pages:
            format_parameters = self._parse_required_url_parameters(
                self.product_url,
                self.required_params
            )
            if format_parameters:
                format_parameters['beginindex'] = 36 * self.current_page
                self.current_page += 1
                return self.SHELF_URL.format(**format_parameters)

    @staticmethod
    def _parse_required_url_parameters(url, required_parameters_keys):
        parsed_url = urlparse.urlparse(url.lower())
        parameters = urlparse.parse_qs(parsed_url.fragment or parsed_url.query)

        if all(param in parameters for param in required_parameters_keys):
            return {
                param: urllib.quote_plus(parameters.get(param)[0]).upper()
                for param in required_parameters_keys
                }

    def _get_product_links(self, response):
        product_links = []
        products = []
        product_links_info = None
        json_resp = True

        try:
            product_json = json.loads(response.body_as_unicode())
            for data in product_json:
                if data.get('productLists', {}):
                    product_links_info = data['productLists'][0]['products']

            if product_links_info:
                for link_info in product_links_info:
                    link_by_html = html.fromstring(link_info['result']).xpath('//li[@class="gridItem"]//h3/a/@href')
                    name_by_html = html.fromstring(link_info['result']).xpath('//li[@class="gridItem"]//h3/a/text()')
                    if link_by_html and name_by_html:
                        product_links.append(link_by_html[0])
                        products.append({
                            'name': name_by_html[0].strip(),
                            'url': link_by_html[0],
                        })
        except:
            self.log("Exception looking for total_matches, Exception Error: {}".format(traceback.format_exc()))
            json_resp = False

        if json_resp is False:
            prods = response.xpath('//div[contains(@class, "productNameAndPromotions")]//h3//a')
            for prod in prods:
                prod_link = prod.xpath('./@href').extract()
                prod_name = prod.xpath('./text()').extract()
                if prod_link and prod_name:
                    url = self._clean_text(prod_link[0]).replace("\\", "").replace('"', "")
                    product_links.append(url)
                    products.append({
                        'name': prod_name[0],
                        'url': url,
                    })

        return product_links, products

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()

    def _scrape_ad_products(self, response):
        meta = response.meta.copy()
        ads = meta.get('ads', [])
        ad_idx = meta.get('ad_idx', 0)
        products = [
            {
                'name': prod_info.xpath('./text()').extract()[0].strip(),
                'url': urlparse.urljoin(response.url, prod_info.xpath('./@href').extract()[0])
            }
            for prod_info
            in response.xpath('//div[@id="productLister"]'
                              '//div[contains(@class, "product")]'
                              '//div[@class="productNameAndPromotions"]'
                              '//h3//a[not(contains(@href, "cat.hlserve.com"))]')
            if prod_info.xpath('./text()') and prod_info.xpath('./@href')
            ]
        ads[ad_idx]['ad_dest_products'] += products
        meta['ads'] = ads
        next_link = response.xpath('//ul[@class="pages"]/li[@class="next"]/a/@href').extract()
        ad_idx += 1
        if next_link:
            next_link = urlparse.urljoin(response.url), next_link[0]
        elif ad_idx < len(ads):
            meta['ad_idx'] = ad_idx
            next_link = ads[ad_idx]['ad_url']
        if next_link:
            return Request(
                next_link,
                callback=self._scrape_ad_products,
                meta=meta,
                dont_filter=True
            )

        return self._scrape_ads(ads)

    def _get_cookies(self, response):
        meta = response.meta
        return Request(
            url=response.request.url,
            dont_filter=True,
            callback=self._scrape_ads_links,
            meta=meta
        )

    def _scrape_ads_links(self, response):
        meta = response.meta.copy()
        ads_xpath = '//div[contains(@class, "es-grape-bg") and //a[contains(text(),"Shop now")]]' \
                    '//div[@class="es-border-box-100"]/a[img]'

        if response.xpath('//body[@id="departmentPage" or @id="shelfPage" or @id="shelfPage"]').extract():
            ads_xpath = '//div[contains(@class, "es-grape-bg") and //a[contains(text(),"Shop now")] ' \
                        'and not(ancestor::div[contains(@class, "hide")])]' \
                        '//div[@class="es-border-box-100"]/a[img]'

        ads_urls = [urlparse.urljoin(response.url, i) for i in response.xpath(ads_xpath + '/@href').extract()]
        image_urls = [urlparse.urljoin(response.url, i) for i in response.xpath(ads_xpath + '//img/@src').extract()]

        ads = [{
                   'ad_url': ad_link,
                   'ad_image': image_urls[idx],
                   'ad_dest_products': []
               } for (idx, ad_link) in enumerate(ads_urls)]

        meta['ads'] = ads
        meta['ad_idx'] = 0

        if ads:
            return Request(
                url=ads[0]['ad_url'],
                callback=self._scrape_ad_products,
                meta=meta,
                dont_filter=True
            )
        return self._scrape_ads([])

    @staticmethod
    def _scrape_ads(ads):
        prod = SiteProductItem()
        prod['ads'] = ads
        return prod
