# -*- coding: utf-8 -*-#
import re
import json
import urllib
import urlparse
import traceback

from lxml import html
from scrapy import Request
from scrapy.log import WARNING
from scrapy.conf import settings
from OpenSSL import SSL

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (FLOATING_POINT_RGEX, BaseProductsSpider,
                                     FormatterWithDefaults, cond_set_value)
from product_ranking.utils import is_empty, replace_http_with_https, SupressHandshakeErrorContextFactory


class SainsburysContextFactory(SupressHandshakeErrorContextFactory):

    def __init__(self):
        self.hostname = 'sainsburys.co.uk'

class SainsburysProductsSpider(BaseProductsSpider):
    name = 'sainsburys_uk_products'
    allowed_domains = [
        'sainsburys.co.uk',
        'sainsburysgrocery.ugc.bazaarvoice.com'
    ]

    SEARCH_URL = "https://www.sainsburys.co.uk/shop/webapp/wcs/stores/servlet/AjaxApplyFilterSearchResultView?" \
                 "langId=44&storeId=10151&catalogId=10241&categoryId=&parent_category_rn=&top_category=&pageSize=36&orderBy=" \
                 "%5BLjava.lang.String%3B%404b114b11&searchTerm={search_term}&beginIndex={product_index}&categoryFacetId1=&requesttype=ajax"

    PRODUCT_URL = 'https://www.sainsburys.co.uk/webapp/wcs/stores/servlet/gb/groceries/{product_id}'

    REVIEWS_URL = 'https://sainsburysgrocery.ugc.bazaarvoice.com/8076-en_gb/' \
                  '{product_id}/reviews.djs?format=embeddedhtml'

    BASE_PROMOTION_URL = "https://www.sainsburys.co.uk/webapp/wcs/stores/servlet/PromotionDisplayView?{args}&krypto={krypto}"

    handle_httpstatus_list = [302]

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(SainsburysProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(product_index=0),
            site_name=self.allowed_domains[0],
            *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.spiders.sainsburys_uk.SainsburysContextFactory'
        settings.overrides['DOWNLOAD_DELAY'] = 2

        self.current_page = 1

        self.scrape_questions = kwargs.get('scrape_questions', None)
        if self.scrape_questions not in ('1', 1, True, 'true', 'True') or self.summary:
            self.scrape_questions = False

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3325.181 Safari/537.36"

    def start_requests(self):
        for req in super(SainsburysProductsSpider, self).start_requests():
            meta = req.meta.copy()
            meta['dont_redirect'] = True
            if self.product_url:
                if 'ProductDisplay' in self.product_url:
                    self.log("url with ProductDisplay, changing it", WARNING)
                    query = urlparse.urlparse(self.product_url).query.split('&')
                    product_id_query = filter(lambda x: x.startswith('productId'), query)
                    if product_id_query:
                        product_id_query = product_id_query[0].split('=')
                        if len(product_id_query) == 2:
                            product_id = product_id_query[1]
                            self.product_url = self.PRODUCT_URL.format(product_id=product_id)
                    else:
                        self.log("url with ProductDisplay, can't parse it, might not work", WARNING)

                req = req.replace(
                    url=replace_http_with_https(self.product_url),
                    meta=meta,
                    dont_filter=True
                )
            elif self.detect_ads:
                req = req.replace(
                    url=req.url.replace(
                        'AjaxApplyFilterSearchResultView',
                        'SearchDisplayView'
                    ),
                    callback=self._get_cookies,
                    meta=meta
                )
            yield req

    def _get_cookies(self, response):
        meta = response.meta.copy()
        location = response.headers.get('Location')
        if location:
            krypto = re.search(r'krypto=(.*?)&', location)
            if krypto:
                meta['krypto'] = krypto.group(1)
        return response.request.replace(
            callback=self._get_ads_content,
            meta=meta,
            dont_filter=True
        )

    def _ads_url_check(self, link, krypto=None):
        if '?' in link and krypto:
            return self.BASE_PROMOTION_URL.format(
                    args=link.split('?')[1],
                    krypto=krypto
                )
        else:
            return link

    def _get_ads_content(self, response):
        meta = response.meta.copy()
        ads_block = response.xpath(
            '//div[contains(@class, "eSpotContainer") and'
            ' not(contains(@class, "bottomESpots"))]'
            '//div[contains(@id,"myAutoRotator")]'
            '//div[@class="es-border-box-100" and ./a]'
        )
        ads_image_urls = [
            urlparse.urljoin(response.url, x) 
            for x in ads_block.xpath('.//img/@src').extract()
        ]
        ads_urls = [
            urlparse.urljoin(response.url, x) 
            for x in ads_block.xpath('./a/@href').extract()
        ]
        if ads_urls:
            meta['ads_idx'] = 0
            meta['ads_image_urls'] = ads_image_urls
            meta['ads_urls'] = ads_urls
            ads_url = self._ads_url_check(ads_urls[0], krypto=meta.get('krypto'))
            return Request(
                url=ads_url,
                meta=meta,
                callback=self._parse_ads_product,
                dont_filter=True,
            )
        else:
            return Request(
                    url=self.SEARCH_URL.format(
                        search_term=response.meta.get('search_term'),
                        product_index=0
                    ),
                    meta=meta
                )

    def _parse_ads_product(self, response):
        meta = response.meta.copy()
        ads = meta.get('ads', [])
        ads_idx = meta.get('ads_idx')
        ads_urls = meta.get('ads_urls')
        image_urls = meta.get('ads_image_urls')
        if not ads and len(ads_urls) == len(image_urls):
            for i, url in enumerate(ads_urls):
                ad = {
                    'ad_url': url,
                    'ad_image': image_urls[i]
                }
                ads.append(ad)

        product_links = self._get_ads_product_links(response)
        product_names = self._get_ads_product_names(response)
        if product_links:
            products = [{
                'url': product_links[i],
                'name': product_names[i].strip(),
                'brand': guess_brand_from_first_words(product_names[i].strip()),
            } for i in range(len(product_links))]
            if len(ads) >= ads_idx:
                ads[ads_idx]['ad_dest_products'] = products
        meta['ads'] = ads

        ads_idx += 1
        if ads_idx < len(ads_urls):
            link = self._ads_url_check(ads_urls[ads_idx], krypto=meta.get('krypto'))
            meta['ads_idx'] += 1
        else:
            return Request(
                url=self.SEARCH_URL.format(
                    search_term=response.meta.get('search_term'),
                    product_index=0
                ),
                meta=meta
            )

        return Request(
            url=link,
            meta=meta,
            callback=self._parse_ads_product,
            dont_filter=True
        )

    @staticmethod
    def _get_ads_product_links(response):
        return response.xpath(
            '//ul[contains(@class, "productLister")]/li//h3/a/@href'
        ).extract()

    @staticmethod
    def _get_ads_product_names(response):
        return response.xpath(
            '//ul[contains(@class, "productLister")]/li//h3/a/text()'
        ).extract()

    def _parse_single_product(self, response):
        # here we replace '%' to '%25', because server when redirect, converts this sign incorrect in Location header
        if response.status == 302 \
                and response.headers.get('Location', None):
            url = response.headers.get('Location')
            url = url.replace('%', '%25')
            meta = response.meta.copy()

            return Request(
                url=url,
                callback=self._parse_single_product,
                meta=meta
            )
        else:
            return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en_GB"

        title = self._parse_title(response)
        if title:
            brand = guess_brand_from_first_words(title)
            cond_set_value(product, 'title', title)
            cond_set_value(product, 'brand', brand)

        cond_set_value(product, 'is_out_of_stock', False)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        product['price_per_volume'] = self._parse_price_per_volume(response)
        product['volume_measure'] = self._parse_volume_measure(response)

        promotion_block = self._extract_promotions_block(response)

        save_amount, was_now, buy_for, save_percent, buy_save = self._parse_promotions(promotion_block)

        product['save_amount'] = save_amount
        product['was_now'] = was_now
        product['buy_for'] = buy_for
        product['save_percent'] = save_percent
        product['buy_save_amount'] = buy_save

        if any([save_amount, was_now, buy_for, save_percent, buy_save]):
            product['promotions'] = True
        else:
            product['promotions'] = False

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id)
        cond_set_value(product, 'sku', reseller_id)

        categories = self._parse_categories(response)
        if categories:
            cond_set_value(product, 'categories', categories)
            cond_set_value(product, 'department', categories[-1])

        product_id = re.search("productId:\s*\\'(.*)\\'", response.body)
        if product_id:
            return Request(
                self.REVIEWS_URL.format(product_id=product_id.group(1)),
                self.br.parse_buyer_reviews,
                meta={'product': product},
            )

        return product

    @staticmethod
    def _extract_promotions_block(response):
        return "".join(response.xpath(
            '//div[@class="promotion"]//a//text()').extract()).strip()

    def _parse_promotions(self, promotion_block):
        try:
            promotion_block = promotion_block.split(':')

            short_promotion = promotion_block[0].strip()
            long_promotion = promotion_block[1].strip() if len(promotion_block) > 1 else ''

            old_price = re.findall(ur'(?<=Was £)(\d+\.?\d*)', long_promotion)
            old_price = old_price[0] if old_price else None

            new_price = re.findall(ur'(?<=Now £)(\d+\.?\d*)', long_promotion)
            new_price = new_price[0] if new_price else None

            only_price = re.findall(ur'(?<=Only £)(\d+\.?\d*)', short_promotion)
            only_price = only_price[0] if only_price else None

            was_now = ', '.join([new_price, old_price]) if old_price and new_price else None

            old_price = float(old_price) if old_price else None
            new_price = float(new_price) if new_price else None
            only_price = float(only_price) if only_price else None

            save_amount = re.findall(ur'(?<=Save £)(\d+\.?\d*)', short_promotion) \
                if not only_price \
                else re.findall(ur'(?<=Save £)(\d+\.?\d*)', long_promotion)
            if save_amount:
                save_amount = float(save_amount[0])
            elif old_price and new_price:
                save_amount = format(old_price - new_price, '.2f')

            buy_for = None

            if 'Half Price' in short_promotion:
                save_percent = '50'
            else:
                save_percent = re.findall(r'(?<=Save )(\d+)(?=%)', short_promotion)
                if save_percent:
                    save_percent = save_percent[0]
                elif old_price and new_price:
                    save_percent = format(((old_price - new_price) / old_price) * 100, '.0f')
                elif only_price and save_amount:
                    save_percent = format((save_amount / only_price) * 100, '.0f')

            buy_save = None

            return save_amount, was_now, buy_for, save_percent, buy_save
        except:
            self.log("Failed to parse promotion offers: {}".format(traceback.format_exc()))
            return None, None, None, None, None

    def _parse_title(self, response):
        title = is_empty(
            response.xpath(
                '//div[@class="productTitleDescriptionContainer"]//h1/text()'
            ).extract()
        )

        return title

    @staticmethod
    def _parse_price_per_volume(response):
        price = is_empty(
            response.xpath(
                './/*[@class="pricePerMeasure"]/text()'
            ).re(FLOATING_POINT_RGEX)
        )
        return price

    @staticmethod
    def _parse_volume_measure(response):
        volume_measure = is_empty(
            response.xpath(
                './/*[@class="pricePerMeasureMeasure"]/text()'
            ).extract()
        )
        return volume_measure

    def _parse_price(self, response):
        price = is_empty(
            response.xpath(
                '//*[@class="pricePerUnit"]'
            ).re(FLOATING_POINT_RGEX)
        )

        if price:
            price = Price('GBP', price)

        return price

    def _parse_image_url(self, response):
        image_url = is_empty(
            response.xpath(
                '//img[@id="productImageID"]/@src'
            ).extract()
        )

        if image_url and 'no-image' in image_url:
            image_url = None

        if image_url:
            image_url = urlparse.urljoin(response.url, image_url)

        return image_url

    def _parse_categories(self, response):
        categories = response.xpath(
            '//ul[@id="breadcrumbNavList"]/li/a//text()'
        ).extract()

        return [category.strip() for category in categories if category.strip()]

    def _parse_reseller_id(self, response):
        reseller_id = is_empty(
            response.xpath('//*[@class="itemCode"]/text()').re('\d+'))
        return reseller_id

    def _parse_no_longer_available(self, response):
        return bool(response.xpath('//div/p[contains(text(), "Product not available")]'))

    def _scrape_total_matches(self, response):
        try:
            total_matches = re.search('found\s([\d,]+)\sproducts', response.body_as_unicode()).group(1)
            return int(total_matches.replace(',', ''))
        except:
            self.log("Found no total matches: {}".format(traceback.format_exc()))
            return 0

    def _scrape_product_links(self, response):
        product_links = []
        product_links_info = None
        try:
            product_json = json.loads(response.body_as_unicode())
            for data in product_json:
                if data.get('productLists', {}):
                    product_links_info = data['productLists'][0]['products']

            if product_links_info:
                for link_info in product_links_info:
                    link_by_html = html.fromstring(link_info['result']).xpath('//li[@class="gridItem"]//h3/a/@href')
                    if link_by_html:
                        product_links.append(link_by_html[0])
        except:
            self.log("Exception looking for total_matches, Exception Error: {}".format(traceback.format_exc()))

        for link in product_links:
            product_item = SiteProductItem()
            if self.detect_ads:
                product_item['ads'] = response.meta.get('ads')
            yield link, product_item

    def _scrape_next_results_page_link(self, response):
        if not self._scrape_product_links(response):
            return

        self.current_page += 1

        results_per_page = response.meta['scraped_results_per_page']
        product_index = self.current_page * int(results_per_page)
        if product_index > self._scrape_total_matches(response):
            return
        next_page = self.SEARCH_URL.format(
            search_term=urllib.quote_plus(response.meta.get('search_term').encode('utf-8')),
            product_index=product_index)

        return urlparse.urljoin(response.url, next_page)