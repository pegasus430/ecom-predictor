# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals

import json
import re
import string
import traceback
import urlparse
import urllib
import math

from future_builtins import map

from scrapy.http import Request
from scrapy.conf import settings
from scrapy.log import ERROR

from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, FormatterWithDefaults,
                                     cond_set, cond_set_value)
from product_ranking.guess_brand import guess_brand_from_first_words


class OcadoProductsSpider(BaseProductsSpider):
    name = 'ocado_products'
    allowed_domains = ["ocado.com"]

    SEARCH_URL = "https://www.ocado.com/webshop/getSearchProducts.do?" \
                 "clearTabs=yes&isFreshSearch=true&entry={search_term}&sortBy={search_sort}"

    PRODUCT_URL = "https://www.ocado.com/webshop/product/ABC/{sku}"

    ENC_PROD_URL = "https://www.ocado.com/webshop/product/{prod_name}/{sku}"

    INFO_PROD_URL = "https://www.ocado.com/webshop/products?skus={}"

    SEARCH_SORT = {
        "default": "default",
        "price_asc": "price_asc",
        "price_desc": "price_desc",
        "name_asc": "name_asc",
        "name_desc": "name_desc",
        "shelf_life": "shelf_life",
        "customer_rating": "customer_rating",
    }

    handle_httpstatus_list = [404]

    def __init__(self, search_sort="default", *args, **kwargs):
        super(OcadoProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                search_sort=self.SEARCH_SORT[search_sort]
            ), *args, **kwargs
        )

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)' \
                          'Chrome/66.0.3359.170 Safari/537.36'

    def start_requests(self):
        for st in self.searchterms:
            request = Request(
                self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote_plus(st.encode('utf-8')),
                ),
                meta={'search_term': st, 'remaining': self.quantity},
                dont_filter=True
            )

            if self.detect_ads:
                request = request.replace(callback=self._start_ads_request, dont_filter=True)
            yield request

        if self.product_url:
            prod = SiteProductItem()
            prod['is_single_result'] = True
            prod['url'] = self.product_url
            prod['search_term'] = ''
            yield Request(self.product_url,
                          self._parse_single_product,
                          meta={'product': prod})

    def clear_desc(self, l):
        return " ".join(
            [it for it in map(string.strip, l) if it])

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        if response.status == 404:
            product['not_found'] = True
            return product

        title_list = response.xpath(
            "//h1[@class='productTitle'][1]//text()").extract()

        if len(title_list) >= 2:
            cond_set_value(product, 'title', self.clear_desc(title_list[-2:]))

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        price_per_volume = self._parse_price_per_volume(response)
        cond_set_value(product, 'price_per_volume', price_per_volume)

        volume_measure = self._parse_volume_measure(response)
        cond_set_value(product, 'volume_measure', volume_measure)

        img_url = response.xpath("//ul[@id='galleryImages']/li[1]/a/@href").extract()
        if img_url:
            cond_set_value(product, 'image_url', urlparse.urljoin(response.url, img_url[0]))

        cond_set_value(product, 'locale', "en_GB")

        promotions = response.xpath('//div[@class="onOffer"]').extract()
        cond_set_value(product, 'promotions', bool(promotions))

        is_out_of_stock = self._is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        regex = "\/(\d+)"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        brand = self.parse_brand(response) or response.xpath(
            "string(//div[@id='bopBottom']//*[@itemprop='brand'])").extract()
        cond_set(product, 'brand', brand, string.strip)

        buyer_reviews = self._parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        # Parse price mechanics
        promotion_block = self._extract_promotions_block(response)

        save_amount = self._parse_save_amount(promotion_block)
        product['save_amount'] = save_amount

        was_now = self._parse_was_now(promotion_block)
        product['was_now'] = was_now

        buy_for = self._parse_buy_for(promotion_block)
        product['buy_for'] = buy_for

        buy_save_percent = self._parse_buy_save_percent(promotion_block)
        product['buy_save_percent'] = buy_save_percent

        buy_save_amount = self._parse_buy_save_amount(promotion_block)
        product['buy_save_amount'] = buy_save_amount

        save_percent = self._parse_save_percent(promotion_block)
        product['save_percent'] = save_percent

        if any([save_amount, save_percent, was_now, buy_for, buy_save_percent, buy_save_amount]):
            product['promotions'] = True
        else:
            product['promotions'] = False

        if product.get('url').startswith('https://www.ocado.com/webshop/product/ABC/'):
            product['url'] = response.url

        return product

    @staticmethod
    def _extract_promotions_block(response):
        return response.xpath(
            '//div[@class="productDescription"]/p[@class="onOffer"]/@data-promotion-name').extract()

    @staticmethod
    def _parse_save_amount(promotion_block):
        if promotion_block:
            promotion_block = promotion_block[0].split(',')
            if 'Save' in promotion_block[0] and not '%' in promotion_block[0]:
                save_amount = re.findall(r'\d+\.*\d*', promotion_block[0])
                if save_amount:
                    for x in save_amount:
                        if x + 'p' in promotion_block[0]:
                            save_amount[save_amount.index(x)] = '0.' + x

                return save_amount[0] if save_amount else None

    @staticmethod
    def _parse_was_now(promotion_block):
        if promotion_block:
            if 'was' in promotion_block[0]:
                was_now = re.findall(r'\d+\.*\d*', promotion_block[0])
                if len(was_now) > 1:
                    save = float(was_now[0])
                    was = float(was_now[1])
                    was_now = "{new}, {old}".format(new=was - save, old=was)
                    return was_now

    @staticmethod
    def _parse_buy_for(promotion_block):
        if promotion_block:
            if all([x in promotion_block[0] for x in ('Buy any', 'for')]):
                buy_for = re.findall(r'\d+\.*\d*', promotion_block[0])
                for x in buy_for:
                    if x + 'p' in promotion_block[0]:
                        buy_for[buy_for.index(x)] = '0.' + x
                return ', '.join(buy_for) if buy_for else None

    @staticmethod
    def _parse_buy_save_percent(promotion_block):
        if promotion_block:
            save_percent_info = promotion_block[0].split(',')
            if all([x in save_percent_info[0].lower() for x in ('save', '%')]):
                save_percent = re.search(r'(\d+)%', save_percent_info[0])
                count = re.search(r'(\d+) save', save_percent_info[0])
                return count.group(1) + ', ' + save_percent.group(1) if save_percent and count else None

    @staticmethod
    def _parse_buy_save_amount(promotion_block):
        if promotion_block:
            if 'Buy any' in promotion_block[0] and 'save' in promotion_block[0] and '%' not in promotion_block[0]:
                buy_save = re.findall(r'\d+\.*\d*', promotion_block[0])
                for x in buy_save:
                    if x + 'p' in promotion_block[0]:
                        buy_save[buy_save.index(x)] = '0.' + x
                return ', '.join(buy_save) if buy_save else None

    @staticmethod
    def _parse_save_percent(promotion_block):
        if promotion_block:
            save_percent_info = promotion_block[0].split(',')
            if all([x in save_percent_info[0].lower() for x in ('save', '%')]):
                save_percent = re.search(r'Save (\d+)%', save_percent_info[0])
                return save_percent.group(1) if save_percent else None

    def _parse_buyer_reviews(self, response):
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        num_of_reviews_info = response.xpath(
            "//span[@class='reviewCount']/text()").extract()

        try:
            review_count = re.findall(r'(\d+)', num_of_reviews_info[0])[0]
            num_of_reviews = int(review_count)
        except:
            num_of_reviews = 0

        rating_star_list = response.xpath(
            "//ul[@class='snapshotList']//li"
            "//span[@class='reviewsCount']/text()").extract()

        for i in range(0, 5):
            try:
                rating_by_star[str(i + 1)] = int(re.findall(r'\d+', rating_star_list[4 - i])[0])
            except:
                rating_by_star[str(i + 1)] = 0

        average_review = response.xpath("//*[@id='rating']/@title").extract()

        try:
            average_rating = float(average_review[0].split('out')[0])
        except:
            average_rating = 0

        buyer_reviews_info = {}
        if rating_by_star:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(average_rating),
                'rating_by_star': rating_by_star
            }

        if buyer_reviews_info:
            return BuyerReviews(**buyer_reviews_info)
        else:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    def _parse_price(self, response):
        price = response.xpath('//meta[@itemprop="price"]/@content').extract()
        priceCurrency = response.xpath('//meta[@itemprop="priceCurrency"]/@content').extract()
        priceCurrency = priceCurrency[0] if priceCurrency else 'GBP'
        if price:
            price = price[0]
            price = float(price.replace(',', ''))
            if price == 0:
                price = response.xpath('//span[@class="nowPrice"]/text()').re(r'[\d\.]+')
                if not price:
                    price = response.xpath('//p[@class="typicalPrice"]/text()').re(r'[\d\.]+')
                try:
                    price = float(price[0])
                except:
                    self.log('Failed to parse price', ERROR)
            return Price(price=price, priceCurrency=priceCurrency)

    def _parse_price_per_volume(self, response):
        price_per_volume = response.xpath('//p[@class="pricePerWeight"]/text()').extract()
        if price_per_volume:
            price_per_volume = re.sub('[^0-9.]', "", price_per_volume[0])
        try:
            return math.floor(float(price_per_volume) * 10 ** 2) / 10 ** 2
        except:
            self.log('Parsing Error: {}'.format(traceback.format_exc()))

    def _parse_volume_measure(self, response):
        volume_measure = response.xpath('//p[@class="pricePerWeight"]/text()').extract()
        return self._clean_text(volume_measure[0].split('per')[-1]) if volume_measure else None

    @staticmethod
    def _is_out_of_stock(response):
        availability = response.xpath('//meta[@itemprop="availability"]/@content').extract()

        if availability:
            if availability[0] == "InStock":
                return False
            return True

    def _scrape_total_matches(self, response):
        totals = response.xpath("string(//h3[@id='productCount'])").re(
            r'(\d+) products')

        if not totals:
            totals = response.xpath("//div[@class='total-product-number']//span[@class='show-for-xlarge']").re('\d+')

        if totals:
            totals = int(totals[0].strip())
        else:
            self.log(
                "Failed to find 'total matches' for %s" % response.url,
                ERROR
            )

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
            for item in items:
                prod_item = SiteProductItem()
                if self.detect_ads is True:
                    prod_item['ads'] = meta.get('ads')
                    prod_item['sponsored_links'] = sponsored_links

                req = Request(
                    url=item,
                    callback=self.parse_product,
                    meta={
                        "product": prod_item,
                        'search_term': st,
                        'remaining': self.quantity,
                    },
                    dont_filter=True
                )
                yield req, prod_item
        else:
            self.log("Found no product links in {url}".format(url=response.url))

    def _scrape_next_results_page_link(self, response):
        pass

    def _get_ads_products(self, response):
        ads_idx = response.meta.get('ads_idx')
        ads_urls = response.meta.get('ads_urls')
        skus = []
        for section in self._extract_sections(response, 'js-productPageJson'):
            for fop in section.get('fops', []):
                sku = fop.get('sku')
                if sku:
                    skus.append(sku)

        if skus:
            meta = response.meta.copy()
            skus = [skus[x:x + 100] for x in range(0, len(skus), 100)]

            meta['sku_idx'] = 0
            meta['skus'] = skus
            skus_list = ','.join(skus[0])
            prods_url = self.INFO_PROD_URL.format(skus_list)

            return Request(url=prods_url,
                           meta=meta,
                           callback=self._parse_ads_products,
                           dont_filter=True)

        if ads_idx < len(ads_urls):
            link = ads_urls[ads_idx]
        else:
            return self.parse(response)

        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_products,
            dont_filter=True
        )

    def _parse_ads_products(self, response):
        ads = response.meta.get('ads', [])
        ads_idx = response.meta.get('ads_idx', 0)
        ads_urls = response.meta.get('ads_urls', [])
        skus = response.meta.get('skus', [])
        sku_idx = response.meta.get('sku_idx', 0)
        product_list = []

        products = self._get_products_info(response)
        product_list.extend([prod for prod in products])

        sku_idx += 1
        if sku_idx < len(skus):
            skus_list = ','.join(skus[sku_idx])
            prods_url = self.INFO_PROD_URL.format(skus_list)
            response.meta['sku_idx'] += 1
            return Request(url=prods_url,
                           meta=response.meta,
                           callback=self._parse_ads_products,
                           dont_filter=True)

        if product_list:
            ads[ads_idx]['ad_dest_products'] = product_list
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
            callback=self._get_ads_products,
            dont_filter=True
        )

    def _get_product_links(self, response):
        return [self.PRODUCT_URL.format(sku=sku) for sku in
                response.xpath('//div[@id="js-productPageFops"]//li[@data-sku]/@data-sku').extract()]

    def _get_item(self, item_info):
        enc_prod_name = item_info.get('product', {}).get('encodedName')
        sku = item_info.get('sku')
        prod_name = item_info.get('product', {}).get('name')

        if sku and prod_name and enc_prod_name:
            return {
                'name': prod_name,
                'url': self.ENC_PROD_URL.format(prod_name=enc_prod_name, sku=sku),
                'reseller_id': sku,
                'brand': guess_brand_from_first_words(prod_name),
            }
        else:
            return None

    def _get_sponsored_links(self, response):
        sponsored_links = []
        for sponsored_section in self._extract_sections(response, 'js-productCarouselData'):
            for sponsored_fop in sponsored_section.get('fops', [])[:3]:
                item = self._get_item(sponsored_fop)
                if item:
                    sponsored_links.append(item)

        for sponsored_section in self._extract_sections(response, 'js-productPageJson'):
            if sponsored_section.get('sectionAttributes', {}).get('analyticsSection') == 'FEATURED':
                for sponsored_fop in sponsored_section.get('fops', []):
                    item = self._get_item(sponsored_fop)
                    if item:
                        sponsored_links.append(item)

        return sponsored_links

    def _get_products_info(self, response):
        items = []

        try:
            info = json.loads(response.body)
            for fop in info.values():
                item = self._get_item(fop)
                if item:
                    items.append(item)
        except:
            self.log('Can not extract ads products json data: {}'.format(traceback.format_exc()))

        return items

    @staticmethod
    def _get_next_page_template(response):
        next_page_template = response.xpath('//div[@class="ws-product-listing-pagination"]'
                                            '/@data-jum-pagination-link-template').extract()
        return next_page_template[0] if next_page_template else None

    def _get_ads_path(self):
        return ['//div[contains(@class, "supplierBanner")]//a',
                '//ul[contains(@class, "fops")]//li[contains(@class, "promotion")]//a',
                '//ul[@class="carousel-panels"]//li//a']

    def _start_ads_request(self, response):
        meta = response.meta.copy()
        ads = []

        ads_urls = []
        image_urls = []
        for ads_xpath in self._get_ads_path():
            ads_urls.extend(
                [urlparse.urljoin(response.url, ad) for ad in response.xpath(ads_xpath + '/@href').extract()])
            image_urls.extend(
                [urlparse.urljoin(response.url, ad) for ad in response.xpath(ads_xpath + '//img/@src').extract()])

        items = self._get_product_links(response)
        meta['items'] = items

        total_matches = self._parse_total_matches(response)
        meta['total_matches'] = total_matches

        meta['next_link'] = self._scrape_next_results_page_link(response)

        sponsored_links = self._get_sponsored_links(response)
        meta['sponsored_links'] = sponsored_links

        for i, url in enumerate(ads_urls):
            ad = {
                'ad_url': url,
                'ad_image': image_urls[i]
            }
            ads.append(ad)
        if ads_urls:
            meta['ads_idx'] = 0
            meta['image_urls'] = image_urls
            meta['ads_urls'] = ads_urls
            meta['ads'] = ads

            return Request(
                url=ads_urls[0],
                meta=meta,
                callback=self._get_ads_products,
                dont_filter=True,
            )
        else:
            return self.parse(response)

    def _extract_sections(self, response, section_name):
        try:
            json_list = []
            json_data = response.xpath(
                '//script[@type="application/json" and @class="%s"]/text()' % section_name).extract()
            if not json_data:
                json_data = response.xpath(
                    '//script[@type="application/json" and @class="js-productCarouselData"]/text()').extract()
            for data in json_data:
                json_list.extend(json.loads(data)['sections'])
            return json_list
        except:
            self.log('Can not extract json data: {}'.format(traceback.format_exc()))
            return []

    def _parse_total_matches(self, response):
        return self._scrape_total_matches(response)

    def _clean_text(self, text):
        return re.sub("[\r\n\t]", "", text).strip()

    def parse_brand(self, response):
        return response.xpath('//h3[text()="Brand"]/following-sibling::p/text()').extract()
