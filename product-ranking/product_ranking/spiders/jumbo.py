# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import string
import json
import re
import traceback
import urlparse

from scrapy.conf import settings
from scrapy.log import INFO, WARNING
from lxml import html

from product_ranking.items import SiteProductItem, Price
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import is_empty
from scrapy import Request


class JumboProductsSpider(BaseProductsSpider):
    name = 'jumbo_products'
    allowed_domains = ["jumbo.com", "plus.nl"]
    start_urls = []

    handle_httpstatus_list = [404]

    SEARCH_URL = "https://www.jumbo.com/zoeken?SearchTerm={search_term}"
    HOME_URL = 'https://www.jumbo.com'
    NEXT_PAGE_URL = "https://www.jumbo.com/producten?PageNumber={page_number}&SearchTerm={search_term}"
    STORE_INFO_URL = 'https://www.jumbo.com/INTERSHOP/rest/WFS/Jumbo-Grocery-Site/webapi/stores/{}'

    def __init__(self, *args, **kwargs):
        # middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        # middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        # settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
        # settings.overrides['USE_PROXIES'] = True
        super(JumboProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args, **kwargs)

        store = kwargs.pop('store', 'R74KYx4XucoAAAFIqY8YwKxK')
        self.cookies = {
            'HomeStore': store
        }

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

        self.current_page = 1
        self.total_match = 0
        self.ADS_NEWT_PAGE_PARAM = '/?PageNumber={}'
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36" \
                          " (KHTML, like Gecko) Chrome/66.0.3359.170 Safari/537.36"

    def start_requests(self):
        yield Request(
            self.HOME_URL,
            callback=self._get_cookies
        )

    def _get_cookies(self, response):
        url = self.STORE_INFO_URL.format(self.cookies['HomeStore'])
        yield Request(
            url,
            callback=self._get_store_info
        )

    def _get_store_info(self, response):
        try:
            store_data = json.loads(response.body)
            zip_code = store_data.get('postalCode')
            store = store_data.get('uuid')
            response.meta['store'] = store
            response.meta['zip_code'] = zip_code
            return self._start_requests(response)
        except:
            self.log('Wrong Store Number: {}'.format(traceback.format_exc()), WARNING)
            self.cookies['HomeStore'] = 'R74KYx4XucoAAAFIqY8YwKxK'
            self.log('Set store number to R74KYx4XucoAAAFIqY8YwKxK and try again', WARNING)
            return self._get_cookies(response)

    def _start_requests(self, response):
        """Generate Requests from the SEARCH_URL and the search terms."""
        meta = response.meta.copy()
        store = meta.get('store')
        zip_code = meta.get('zip_code')
        for request in super(JumboProductsSpider, self).start_requests():
            meta = request.meta.copy()
            meta['store'] = store
            meta['zip_code'] = zip_code
            if not self.product_url and self.detect_ads:
                request = request.replace(callback=self._get_ads_product)
            yield request.replace(cookies=self.cookies, meta=meta)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']


        # Set locale
        product['locale'] = 'en_US'

        # parse reseller id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        if response.status == 404:
            cond_set_value(product, 'no_longer_available', True)
            return product

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        if categories:
            cond_set_value(product, 'department', categories[-1])

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse stock status
        is_out_of_stock = self._is_out_of_stock(response)
        product["is_out_of_stock"] = is_out_of_stock

        # Parse price per volume
        price_per_volume, volume_measure = self._parse_volume_price(response)
        cond_set_value(product, 'price_per_volume', price_per_volume)
        cond_set_value(product, 'volume_measure', volume_measure)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url, conv=string.strip)

        # Parse save_percent
        promotion_selector = response.xpath(
            "//div[@class='jum-product-image-group ']//div[@class='jum-promotion-group']//img/@alt"
        ).extract()

        if promotion_selector:
            save_percent = self._parse_save_percent(response, promotion_selector)
            product['save_percent'] = save_percent

            # Parse multi_single_save_percent
            ms_save_percent = self._parse_multi_single_save_percent(response, promotion_selector)
            product['multi_single_save_percent'] = ms_save_percent

            # Parse buy_for
            buy_for = self._parse_buy_for(response, promotion_selector[0])
            product['buy_for'] = buy_for

            # Parse free_shipping_count
            shipping_count = self._parse_free_shipping_count(response, promotion_selector)
            product['free_shipping_count'] = shipping_count

        # Parse promotions
        product['promotions'] = any(
            [
                product.get('save_percent'),
                product.get('multi_single_save_percent'),
                product.get('buy_for'),
                product.get('free_shipping_count')
            ]
        )

        if not product.get('store'):
            store = meta.get('store')
            cond_set_value(product, 'store', store)

        if not product.get('zip_code'):
            zip_code = meta.get('zip_code')
            cond_set_value(product, 'zip_code', zip_code)

        return product

    def _parse_volume_price(self, response):
        try:
            raw_price = response.xpath('//div[@class="jum-item-price"]//span[@class="jum-price-format ' \
                                       'jum-comparative-price"]/text()').extract()
            raw_price = raw_price[0].split('/')
            price_per_volume = float(raw_price[0].replace(',', '.').replace('(', ''))
            volume_measure = raw_price[1].replace(')', '')
            return price_per_volume, volume_measure
        except:
            self.log("Failed to parse price per volume: {}".format(traceback.format_exc()))
            return None, None

    def _parse_reseller_id(self, response):
        reseller_id = re.search(r'([A-Z]*[0-9]*[A-Z]+)', response.url)
        return reseller_id.group() if reseller_id else None

    @staticmethod
    def _parse_title(response):
        title = is_empty(response.xpath('//h1[@data-dynamic-block-id]/text()').extract())
        return title

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//div[contains(@class, "jum-product-info-group")]'
                               '/div[contains(@class, "jum-add-product")]/@data-jum-brand').extract()
        if brand:
            return brand[0]

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath(
            '//nav[contains(@class, "jum-breadcrumb")]/ol/li/a/text()'
        ).extract()
        return [x for x in categories if x.strip()]

    @staticmethod
    def _parse_price(response):
        currency = "EUR"
        price = response.xpath('//div[contains(@class, "jum-sale-price")]'
                               '//input/@jum-data-price').extract()
        if price:
            price = price[0]
            return Price(price=float(price), priceCurrency=currency)

    @staticmethod
    def _is_out_of_stock(response):
        return bool(response.xpath(
            '//div[@class="jum-product-not-available"] |'
            '//form[@data-jum-role="pdp-add-cart" and not(.//button[contains(@id,"addToCart")])]'
        ))

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//div[@class="jum-product-image-figure"]'
                                   '/figure/img/@data-jum-hr-src').extract()
        if image_url:
            return image_url[0]

    @staticmethod
    def _parse_promotions(response):
        promotions = response.xpath("//div[@class='jum-promotion-group']//img/@src").extract()
        return True if promotions else False

    def _parse_save_percent(self, response, korting_info):
        try:
            korting = re.match(r'(\d*\.\d+|\d+)% korting', korting_info[0]).group(1)
            return korting
        except:
            self.log('Save percent error {}'.format(traceback.format_exc()))

    def _parse_multi_single_save_percent(self, response, ms_save_percent_info):
        try:
            count = re.match(r'(\d+)e.*prijs', ms_save_percent_info[0]).group(1)
            ms_save_percent = "{}, {}".format(1, 100 / int(count))
            return ms_save_percent
        except:
            self.log('Multi single save percent error {}'.format(traceback.format_exc()))

    def _parse_buy_for(self, response, buy_for_info):
        try:
            buy_for = re.findall(r'\d+\.*\d*', buy_for_info.replace(',', '.'))
            if len(buy_for) == 2:
                return buy_for[0] + ',' + buy_for[1]
        except:
            self.log('Getfree error {}'.format(traceback.format_exc()))

    def _parse_free_shipping_count(self, response, shipping_info):
        try:
            shipping_count = re.search('.*bij (\d+) stuks', shipping_info[0].lower()).group(1)
            return shipping_count
        except:
            self.log('Shiping count error {}'.format(traceback.format_exc()))

    def _scrape_total_matches(self, response):
        meta = response.meta.copy()
        totals = meta.get('totals')
        if not totals:
            totals = response.xpath('//h2[contains(@class, "jum-search-result-info")]'
                                    '/text()').extract()
        else:
            meta['totals'] = None
        if totals:
            totals = re.search('(\d+)', totals[0])
            self.total_match = int(totals.group()) if totals else 0
        return self.total_match

    @staticmethod
    def _get_product_links(response):
        links = response.xpath('//h3[@data-jum-action="ellipsis"]/a/@href | '
                               '//div[contains(@class, "jum-content-row-group")]//p//a/@href').extract()
        for link in links:
            link = link.replace("http://www.jumbo.com:80", "https://www.jumbo.com")
            yield urlparse.urljoin(response.url, link)

    @staticmethod
    def _get_product_names(response):
        item_names = []
        items = response.xpath('//h3[@data-jum-action="ellipsis"]/a | '
                               '//div[contains(@class, "jum-content-row-group")]//a//strong//span | '
                               '//div[contains(@class, "jum-content-row-group")]//span//a').extract()

        for item in items:
            item_names.append(''.join(html.fromstring(item).xpath("./text()")))
        return item_names

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        items = meta.get('items')
        if not items:
            items = self._get_product_links(response)
        else:
            meta['items'] = None

        ads = meta.get('ads')
        st = meta.get('search_term')
        if items:
            for item in items:
                prod_item = SiteProductItem()
                if self.detect_ads is True:
                    prod_item['ads'] = ads
                req = Request(
                    url=item,
                    callback=self.parse_product,
                    meta={
                        "product": prod_item,
                        'search_term': st,
                        'remaining': self.quantity
                    },
                    dont_filter=True
                )
                prod_item['store'] = meta.get('store')
                prod_item['zip_code'] = meta.get('zip_code')
                yield req, prod_item
        else:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        page_count = self.total_match / 9

        search_term = response.meta['search_term']
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)

        if current_page < page_count:
            current_page += 1
            meta['current_page'] = current_page
            next_page = self.url_formatter.format(self.NEXT_PAGE_URL, page_number=current_page,
                                                  search_term=search_term)
            return Request(
                next_page,
                meta=meta
            )

    def _get_ads_product(self, response):
        meta = response.meta.copy()
        ads = []
        ads_ids = []
        ads_xpath = '//div[@data-jum-group-id="YYsKYx4X_kUAAAFND9o7fr8R"]//a'
        ads_urls = response.xpath(ads_xpath + '/@href').extract()
        image_urls = response.xpath(ads_xpath + '//img/@src').extract()
        spec_ads_xpath = '//aside//div[@data-endeca-component="IntershopContent"]//a'
        spec_ads_urls = response.xpath(spec_ads_xpath + '/@href').extract()
        spec_ads_images = response.xpath(spec_ads_xpath + '//img/@src').extract()
        for index, url in enumerate(spec_ads_urls):
            if not 'INTERSHOP' in url:
                ads_urls.append(url)
                ads_ids.append(index)
        for i in ads_ids:
            image_urls.append(spec_ads_images[i])

        totals = response.xpath('//h2[contains(@class, "jum-search-result-info")]'
                                '/text()').extract()
        meta['totals'] = totals
        ads_urls = [urlparse.urljoin(response.url, ad) for ad in ads_urls]
        image_urls = [urlparse.urljoin(response.url, ad) for ad in image_urls]
        items = list(self._get_product_links(response))
        meta['items'] = items
        category_url = self._get_next_page_template(response)
        meta['category_url'] = category_url if category_url else None
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
            meta['ad_dest_products'] = []
            meta['current_page'] = 1
            return Request(
                url=ads_urls[0],
                meta=meta,
                callback=self._parse_ads_product,
                cookies=self.cookies,
                dont_filter=True,
            )
        else:
            return self.parse(response)

    @staticmethod
    def _get_next_page_template(response):
        next_page_template = response.xpath('//div[@class="ws-product-listing-pagination"]'
                                            '/@data-jum-pagination-link-template').extract()
        return next_page_template[0] if next_page_template else None

    def _parse_ads_product(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')
        ad_dest_products = response.meta.get('ad_dest_products')
        current_page = response.meta.get('current_page')

        product_links = list(self._get_product_links(response))
        product_names = self._get_product_names(response)
        link = None
        if product_links:
            products = [{
                            'url': product_links[i],
                            'name': product_names[i],
                        } for i in range(len(product_links))]

            ad_dest_products += products
            if current_page == 1:
                page_link = self._get_next_page_template(response)
                link = page_link.replace('PageNumber=N', 'PageNumber=' + str(current_page)) if page_link else None
            else:
                link = response.url.replace('?PageNumber=' + str(current_page - 1), '?PageNumber=' + str(current_page))

            response.meta['current_page'] = current_page + 1
            response.meta['ad_dest_products'] = ad_dest_products
            ads.append(ad_dest_products)
        response.meta['ads'] = ads

        if len(product_links) < 9 or not link:
            ads_idx += 1
            response.meta['current_page'] = 1
            if ads_idx < len(ads_urls):
                link = ads_urls[ads_idx]
                response.meta['ads_idx'] += 1
            else:
                return self.parse(response)
        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_product,
            cookies=self.cookies,
            dont_filter=True
        )
