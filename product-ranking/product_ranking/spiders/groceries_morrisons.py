from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
import urlparse

from scrapy.http import Request
from scrapy.conf import settings
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.utils import get_canonical_url
from product_ranking.validation import BaseValidator


class GroceriesMorrisonsProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'groceries_morrisons_products'
    allowed_domains = ["groceries.morrisons.com"]

    SEARCH_URL = "https://groceries.morrisons.com/webshop" \
                 "/getSearchProducts.do?entry={search_term}"

    PRODUCT_URL = "https://groceries.morrisons.com/webshop/product/ABC/{sku}"

    PRODUCTS_URL = "https://groceries.morrisons.com/webshop/getSearchProducts.do" \
                   "?entry={search_term}&index={page_number}&ajax=true"

    def __init__(self, *args, **kwargs):
        super(GroceriesMorrisonsProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)' \
                          ' Chrome/61.0.3163.100 Safari/537.36'
        self.handle_httpstatus_list = [404]
        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True
        self.current_page = 1

    def start_requests(self):
        for request in super(GroceriesMorrisonsProductsSpider, self).start_requests():
            if not self.product_url and self.detect_ads:
                request = request.replace(callback=self._get_ads_urls)
            yield request

    def _get_ads_urls(self, response):
        meta = response.meta.copy()

        ads_urls = response.xpath('//div[@class="freeHtmlBanners"]//a/@href').extract()

        ads_img_urls = response.xpath('//div[@class="freeHtmlBanners"]//a/img/@src').extract()
        ads_img_urls.extend([None] * (len(ads_urls) - len(ads_img_urls)))

        ads = [{
            'ad_url': ad_url,
            'ad_image': urlparse.urljoin(response.url, ads_img_urls[idx]),
            'ad_dest_products': []
        } for idx, ad_url in enumerate(ads_urls)]

        items = self._get_product_links(response)
        total_matches = len(items)

        if ads_urls and items:
            meta['items'] = items
            meta['ads_idx'] = 0
            meta['ads'] = ads
            meta['total_matches'] = total_matches
            return Request(
                url=ads_urls[0],
                meta=meta,
                callback=self._get_ads_products,
            )
        else:
            return self.parse(response)

    def _get_ads_products(self, response):
        ads_idx = response.meta.get('ads_idx')
        ads = response.meta.get('ads')

        product_links = self._get_product_links(response)
        product_names = self._get_product_names(response)

        ads[ads_idx]['ad_dest_products'] = [{
            'brand': guess_brand_from_first_words(product_names[i]),
            'product_name': product_names[i],
            'url': product_link,
            'reseller_id': self._get_reseller_id(product_link)
        } for i, product_link in enumerate(product_links)]
        response.meta['ads'] = ads
        if ads_idx < len(ads) - 1:
            ads_idx += 1
            response.meta['ads_idx'] = ads_idx
            return Request(
                url=ads[ads_idx]['ad_url'],
                meta=response.meta,
                callback=self._get_ads_products,
                dont_filter=True
            )
        else:
            return self.parse(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        if response.status == 404:
            product["not_found"] = True
            return product

        product_title = self._parse_product_title(response)
        cond_set_value(product, 'title', product_title)

        brand = self._parse_brand(response)
        if not brand and product_title:
            brand = guess_brand_from_first_words(product_title)
        cond_set_value(product, 'brand', brand)

        cond_set_value(product, "reseller_id", self._parse_reseller_id(response.url))

        brand = guess_brand_from_first_words(product.get('title', '').strip())
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        price, currency = self._parse_price(response)
        if not price:
            product["not_found"] = True
            return product
        product['price'] = Price(price=float(price), priceCurrency=currency)

        price_per_weight = response.xpath('//p[@class="pricePerWeight"]/text()').extract()
        if price_per_weight:
            if 'per' in price_per_weight[0]:
                prices = price_per_weight[0].split('per')
            else:
                prices = price_per_weight[0].strip().split(' ')
            if len(prices) > 1:
                try:
                    value = prices[0].strip()
                    if 'p' in value:
                        price_per_volume = float(value[:-1])
                    else:
                        price_per_volume = float(value[1:])
                    volume_measure = prices[1].strip()
                    cond_set_value(product, 'price_per_volume', price_per_volume)
                    cond_set_value(product, 'volume_measure', volume_measure)
                except:
                    self.log('Price weight error {}'.format(traceback.format_exc()))

        buyer_reviews = self.parse_buyer_reviews(response)
        product['buyer_reviews'] = buyer_reviews

        product['locale'] = "en-US"

        upc = response.xpath("//meta[@itemprop='sku']/@content").extract()
        if upc:
            product['upc'] = upc[0][-12:].zfill(12)

        # Parse price mechanics
        promotion_block = self._extract_promotions_block(response)

        save_amount = self._parse_save_amount(promotion_block)
        product['save_amount'] = save_amount

        was_now = self._parse_was_now(promotion_block)
        product['was_now'] = was_now

        buy_for = self._parse_buy_for(promotion_block)
        product['buy_for'] = buy_for

        save_percent = self._parse_save_percent(promotion_block)
        product['save_percent'] = save_percent

        buy_save_amount = self._parse_buy_save_amount(promotion_block)
        product['buy_save_amount'] = buy_save_amount

        if any([save_amount, was_now, buy_for, save_percent, buy_save_amount]):
            product['promotions'] = True
        else:
            product['promotions'] = False

        if product.get('ads_urls'):
            ads = product.get('ads_urls', [])
            for ad in ads:
                return Request(
                    urlparse.urljoin(response.url, ad),
                    self._parse_ads_product,
                    meta={'product': product},
                    dont_filter=True
                )

        canonical_url = get_canonical_url(response)
        if canonical_url:
            product['url'] = canonical_url

        return product

    @staticmethod
    def _extract_promotions_block(response):
        return response.xpath(
            '//div[@class="productDescription"]/p[@class="onOffer"]/@data-promotion-name').extract()

    @staticmethod
    def _get_reseller_id(link):
        reseller_id = re.search('/(\d+)', link)
        return reseller_id.group(1) if reseller_id else None

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
            if 'Offer' in promotion_block[0]:
                was_now = re.findall(r'\d+\.*\d*', promotion_block[0])
                for x in was_now:
                    if x + 'p' in promotion_block[0]:
                        was_now[was_now.index(x)] = '0.' + x
                return ', '.join(was_now) if was_now else None

    @staticmethod
    def _parse_buy_for(promotion_block):
        if promotion_block:
            if re.match(r'.+ \d+ for .+', promotion_block[0]):
                buy_for = re.findall(r'\d+\.*\d*', promotion_block[0])
                for x in buy_for:
                    if x + 'p' in promotion_block[0]:
                        buy_for[buy_for.index(x)] = '0.' + x
                return ', '.join(buy_for) if buy_for else None

    @staticmethod
    def _parse_save_percent(promotion_block):
        if promotion_block:
            save_percent_info = promotion_block[0].split(',')
            if all([x in save_percent_info[0] for x in ('Save', '%')]):
                save_percent = re.findall(r'\d+(?=%)', save_percent_info[0])
                for x in save_percent:
                    if x + 'p' in promotion_block[0]:
                        save_percent[save_percent.index(x)] = '0.' + x
                return save_percent[0] if save_percent else None

    @staticmethod
    def _parse_buy_save_amount(promotion_block):
        if promotion_block:
            if 'Buy any' in promotion_block[0] and 'save' in promotion_block[0]:
                buy_save = re.findall(r'\d+\.*\d*', promotion_block[0])
                for x in buy_save:
                    if x + 'p' in promotion_block[0]:
                        buy_save[buy_save.index(x)] = '0.' + x
                return ', '.join(buy_save) if buy_save else None

    def _parse_product_title(self, response):
        product_title = response.xpath("//title/text()").extract()
        if product_title:
            product_title = re.sub(' +', ' ', self._clean_text(product_title[0]))
            product_title = product_title.replace('(Product Information)', '').replace('Morrisons:', '')

        return product_title

    def _parse_brand(self, response):
        brand = response.xpath(
            "//span[@itemprop='brand']"
            "//a//span[@itemprop='name']/text()").extract()

        return brand[0] if brand else None

    def _parse_categories(self, response):
        categories_list = response.xpath(
            "//ul[@class='categories']"
            "//li//h4//a/text()").extract()

        categories = list(set(categories_list))

        return categories if categories else None

    def _parse_price(self, response):
        currency = 'GBP'
        price_info = response.xpath(
            "//div[@id='bopRight']"
            "//div[@class='productPrice' and @itemprop='offers']"
            "//div[@class='typicalPrice']//h5/text()"
        ).extract()

        if not price_info:
            price_info = response.xpath(
                "//div[@id='bopRight']//div[@class='productPrice' and @itemprop='offers']"
                "//div[@class='typicalPrice']//h5//span[@class='nowPrice']/text()").extract()

        if price_info:
            price = re.sub(r'[\xa3]', '', price_info[0]).strip()
            if 'p' in price:
                price = float(price.replace('p', '')) / 100
            return price, currency

        return 0.00, currency

    @staticmethod
    def _parse_reseller_id(url):
        reseller_id = re.search(r"\/[^\/]+\/(\d+)", url)
        return reseller_id.group(1) if reseller_id else None

    def _parse_image(self, response):
        image_url = response.xpath("//div[@id='zoomedImage']//img/@src").extract()
        if image_url:
            image_url = urlparse.urljoin(response.url, image_url[0])
            return image_url

    def _parse_ads_product(self, response):
        product = response.meta.get('product', {})
        ads_dest_products = []
        ads_product_name = response.xpath("//strong[@itemprop='name']/text()").extract()
        ads_product_links = response.xpath("//h4[@class='productTitle']//a/@href").extract()
        for index, name in enumerate(ads_product_name):
            ads_product = {}
            ads_product['name'] = name
            ads_product['url'] = urlparse.urljoin(response.url, ads_product_links[index])
            ads_dest_products.append(ads_product)
        product["ads_dest_products"] = ads_dest_products
        return product

    def parse_buyer_reviews(self, response):
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}

        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        num_of_reviews_info = response.xpath(
            "//div[@class='reviewSummary']//strong[@itemprop='ratingCount']/text()").extract()
        num_of_reviews = self._find_number(num_of_reviews_info)

        rating_groups = response.xpath(
            "//div[@id='textReviews']//ul[@class='snapshotList']//li")

        for rating_group in rating_groups:
            try:
                star = rating_group.xpath(".//span[@class='starRating']//strong/text()").extract()[0].strip()
                count = rating_group.xpath(".//span[@class='reviewsCount']/text()").extract()[0].strip()
                rating_by_star[str(star)] = int(count)
            except:
                continue

        average_rating = response.xpath(
            "//div[@class='reviewSummary']//span[contains(text(), 'Average rating')]/text()").extract()

        try:
            average_rating = float(re.findall("\d*\.?\d+", average_rating[0])[0])
        except:
            average_rating = None

        buyer_reviews_info = {}
        if rating_by_star:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': average_rating,
                'rating_by_star': rating_by_star
            }

        if buyer_reviews_info:
            return BuyerReviews(**buyer_reviews_info)
        else:
            self.log("Error while parsing reviews")
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    @staticmethod
    def _clean_text(text):
        return re.sub("[\r\n\t]", "", text).strip()

    @staticmethod
    def _find_number(s):
        if not s:
            return 0

        try:
            number = re.findall(r'(\d+)', s[0])[0]
            return int(number)
        except ValueError:
            return 0

    def _scrape_total_matches(self, response):
        return len(list(self._scrape_product_links(response)))

    def _scrape_product_links(self, response):
        meta = response.meta.copy()
        ads = meta.get('ads', [])
        links = meta.get('items', [])

        meta['items'] = None

        if not links:
            links = self._get_product_links(response)

        for link in links:
            prod = SiteProductItem()
            if self.detect_ads and ads:
                prod['ads'] = ads
            yield link, prod

    def _scrape_next_results_page_link(self, response):
        pass

    def _extract_sections(self, response, section_name):
        try:
            return json.loads(
                response.xpath('//script[@type="application/json" and @class="%s"]/text()' % section_name).extract()[0]
            )['sections']
        except:
            self.log('Can not extract json data: {}'.format(traceback.format_exc()))
            return []

    def _get_product_links(self, response):
        product_links = [
            self.PRODUCT_URL.format(sku=fop.get('sku'))
            for section in self._extract_sections(response, 'js-productPageJson')
            for fop in section.get('fops', [])
        ]
        return product_links

    def _get_product_names(self, response):
        product_names = [
            fop.get('product', {}).get('name')
            for section in self._extract_sections(response, 'js-productPageJson')
            for fop in section.get('fops', [])
        ]
        return product_names
