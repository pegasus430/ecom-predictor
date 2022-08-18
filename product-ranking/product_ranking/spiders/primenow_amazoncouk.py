# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals

import re
import string
import traceback
import urlparse
import yaml

from lxml import html
from scrapy import Request
from scrapy.log import WARNING
from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX
from product_ranking.utils import extract_first, is_empty
from spiders_shared_code.primenow_amazoncouk_variants import PrimenowAmazonCoUkVariants


class PrimenowAmazonCoUkProductsSpider(BaseProductsSpider):
    name = "primenow_amazoncouk_products"
    allowed_domains = ["primenow.amazon.co.uk"]

    SEARCH_URL = "https://primenow.amazon.co.uk/search?k={search_term}"

    WELCOME_URL = "https://primenow.amazon.co.uk"
    ZIP_CODE = 'EC2R 6AB'

    def __init__(self, *args, **kwargs):
        super(PrimenowAmazonCoUkProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def start_requests(self):
        yield Request(
            self.WELCOME_URL,
            callback=self.login_handler
        )

    def login_handler(self, response):
        csrf_token = response.xpath(
            "//form[@id='locationSelectForm']"
            "//input[@name='offer-swapping-token']"
            "/@value").extract()

        if not csrf_token:
            self.log('Can\'t find csrf token.', WARNING)
            return None

        csrf_token = csrf_token[0]

        LOG_IN_URL = "https://primenow.amazon.co.uk/cart/initiatePostalCodeUpdate?newPostalCode=" \
                     "{postalCode}&noCartUpdateRequiredUrl=%2F&allCartItemsSwappableUrl" \
                     "=%2F&someCartItemsUnswappableUrl=%2F&offer-swapping-token" \
                     "={csrf_token}".format(postalCode=self.ZIP_CODE, csrf_token=str(csrf_token))

        return Request(
            LOG_IN_URL,
            method='POST',
            callback=self._start_requests,
            dont_filter=True
        )

    def _start_requests(self, response):
        return super(PrimenowAmazonCoUkProductsSpider, self).start_requests()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en-GB"

        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=lambda x: x.replace('\n', '').strip())

        brand = AmazonBaseClass._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse price per volume
        price_volume = self._parse_price_per_volume(response)
        if price_volume:
            cond_set_value(product, 'price_per_volume', price_volume[0])
            cond_set_value(product, 'volume_measure', price_volume[1])

        save_percent_amount = self._parse_save_percent_amount(response)
        if save_percent_amount:
            cond_set_value(product, 'save_percent', save_percent_amount[0])
            cond_set_value(product, 'save_amount', save_percent_amount[1])

        buy_save_amount = self._parse_buy_save_amount(response)
        cond_set_value(product, 'buy_save_amount', buy_save_amount)

        was_now = self._parse_was_now(response)
        cond_set_value(product, 'was_now', was_now)

        model = self._parse_model(response)
        cond_set_value(product, 'model', model, conv=string.strip)

        asin = AmazonBaseClass._parse_asin(response)
        cond_set_value(product, 'asin', asin)

        upc = self._parse_upc(response)
        cond_set_value(product, 'upc', upc)

        subs_discount_percent = AmazonBaseClass._parse_percent_subscribe_save_discount(response)
        cond_set_value(product, 'subs_discount_percent', subs_discount_percent)

        buyer_reviews = self.parse_buyer_reviews(response)
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        canonical_url = response.xpath('//link[@rel="canonical"]/@href').extract()
        if canonical_url:
            product['url'] = urlparse.urljoin(response.url, canonical_url[0])

        return product

    def parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }

        num_of_reviews_info = response.xpath(
            "//div[@class='crIFrameHeaderHistogram']"
            "//div[@class='tiny']//text()").extract()

        # Count of Review
        if num_of_reviews_info:
            num_of_reviews = re.match(r'(\d*\.?\d+)', str(self._clean_text(''.join(num_of_reviews_info).replace(',', ''))))
            num_of_reviews = num_of_reviews.group().replace('.', '') if num_of_reviews else 0
        else:
            num_of_reviews = 0

        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        # Get mark of Review
        ratings = response.xpath("//div[@class='histoCount']/text()").re('\d+')

        # Get count of Mark
        if num_of_reviews:
            for idx, rating in enumerate(ratings):
                rating_by_star[str(5-idx)] = int(rating)

        avarage_rating = response.xpath("//span[@id='acrPopover']/@title").extract()

        if avarage_rating:
            average_rating = re.match(r'(\d*\.?\d+)', avarage_rating[0])
            average_rating = average_rating.group() if average_rating else 0
        else:
            average_rating = 0

        if rating_by_star:
            buyer_reviews_info = {
                'num_of_reviews': int(num_of_reviews),
                'average_rating': float(average_rating),
                'rating_by_star': rating_by_star
            }
            return BuyerReviews(**buyer_reviews_info)
        else:
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    def _parse_title(self, response):
        title = extract_first(response.xpath(
            "//span[@id='productTitle']"
            "//text()"))
        return title

    def _clean_text(self, text):
        return re.sub("[\n\t]", "", text).strip()

    def _parse_no_longer_available(self, response):
        message = None
        no_longer_available_info = response.xpath(
            "//div[@id='availability']"
            "//span[@class='a-size-medium a-color-price']"
            "/text()").extract()
        if no_longer_available_info:
            message = ''.join(no_longer_available_info).replace('\n', '').strip()
        return bool(message)

    def _parse_description(self, response):
        description = None

        ul_description = response.xpath("//ul[@class='a-vertical a-spacing-none']//li//span").extract()
        bookDescription = response.xpath("//div[@id='bookDescription_feature_div']//div//p/text()").extract()
        productDescription = response.xpath("//div[@id='productDescription']//p/text()").extract()

        if ul_description:
            ul_description = self._clean_text(''.join(ul_description))
            description =  ul_description
        elif bookDescription:
            bookDescription = ''.join(bookDescription)
            description = bookDescription
        elif productDescription:
            productDescription = ''.join(productDescription)
            description = productDescription
        return description

    def _parse_price(self, response):
        price = response.xpath('//span[contains(@class, "a-color-price") and contains(@class, "a-size-medium")]/text()').extract()
        if price:
            price = ''.join(price)
            if '£' not in price:
                self.log('Unknown currency at' % response.url)
            else:
                return Price(
                    price=price.replace(',', '').replace(
                        '£', '').strip(),
                    priceCurrency='GBP'
                )

    def _parse_model(self, response):
        model = None
        product_detail = response.xpath("//td[@class='bucket']//ul//li").extract()
        product_details = response.xpath("//table[@id='productDetails_detailBullets_sections1']//tr").extract()
        product_techdetails = response.xpath("//div[@class='wrapper GBlocale']"
                                             "//div[@class='pdTab']//table//tr").extract()
        if product_detail:
            for product_info in product_detail:
                if 'Item model number:' in product_info:
                    model = html.fromstring(product_info).xpath("//li/text()")
                    model = model[0] if model else None
        elif product_details:
            for product_info in product_details:
                if 'Item model number' in product_info:
                    model = html.fromstring(product_info).xpath("//tr//td[@class='a-size-base']/text()")
                    model = self._clean_text(model[0]) if model else None
        elif product_techdetails:
            for i, attr in enumerate(product_techdetails):
                if 'model number' in attr.lower():
                    model = html.fromstring(attr).xpath(".//td[@class='value']/text()")
                    return model[0].strip() if model else None
        return model

    def _parse_image_url(self, response):
        image = extract_first(response.xpath("//div[@id='imgTagWrapperId']//img/@data-old-hires"))
        if not image:
            try:
                json_data = yaml.safe_load(
                    response.xpath('//script[@type="text/javascript" and contains(., "P.when(\'A\').register")]/text()'
                                   ).re(re.compile(r'var\s+data\s*=\s*(\{.+?\});', re.DOTALL))[0]
                )
                image = json_data['colorImages']['initial'][0]['large']
            except:
                self.log('Can not extract image url from yaml data: {}'.format(traceback.format_exc()))
        return image

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

    def _parse_save_percent_amount(self, response):
        save_percent_amount_info = response.xpath("//td[@class='a-span12 a-color-price a-size-base']/text() | "
                                                  "//p[@class='a-size-mini a-color-price ebooks-price-savings']/text()").extract()
        try:
            if save_percent_amount_info:
                save_percent = re.findall(r'\d+(?=%)', save_percent_amount_info[0])[0]
                save_amount = re.findall(r'\d+\.?\d*(?!=%)', save_percent_amount_info[0])[0]
                return float(save_percent), float(save_amount)
        except Exception as e:
            self.log("Can't extract price per volume {}".format(traceback.format_exc(e)), WARNING)

    def _parse_buy_save_amount(self, response):
        buy_save = None
        save_amount = response.xpath("//span[@class='apl_m_font']/text()").extract()
        if save_amount and 'Buy' in save_amount[0] and ', Save' in save_amount[0]:
            buy_save = re.findall(r'\d+\.?\d*', save_amount[0])

        return ', '.join(buy_save) if buy_save else None

    def _parse_was_now(self, response):
        was_now = None
        past_price = response.xpath('//span[contains(@class, "a-text-strike")]/text() | '
                                    '//td[@class="a-color-base a-align-bottom a-text-strike"]/text()')
        current_price = response.xpath('//span[contains(@class, "a-color-price") and contains(@class, "a-size-medium")]/text()')

        if past_price and current_price:
            past_price = past_price[0].re('\d+\.?\d*')
            current_price = current_price[0].re('\d+\.?\d*')
            if past_price and current_price:
                was_now = ', '.join([current_price[0], past_price[0]])
        return was_now

    def _parse_variants(self, response):
        """
        Parses product variants.
        """
        pav = PrimenowAmazonCoUkVariants()
        pav.setupSC(response)
        variants = pav._variants()

        return variants

    def _parse_stock_status(self, response):
        is_out_of_stock = is_empty(
            response.xpath("//div[@id='availability']//span/text()").extract(), ''
        )

        is_out_of_stock = "out of stock" in is_out_of_stock.lower()

        return is_out_of_stock

    def _scrape_total_matches(self, response):
        total_info = response.xpath(
            "//div[contains(@class, 'grid-header-label')]"
            "//h2[@id='house-normal-result-label']"
            "//text()").extract()
        if total_info:
            total = re.findall(r'\d+', ''.join(total_info))
        else:
            total = 0

        if total:
            total_matches = int(total[0])
        else:
            total_matches = 0
        return total_matches if total_matches else 0

    def _scrape_product_links(self, response):
        links = response.xpath("//div[@id='house-search-result']"
                               "//a[@class='a-link-normal asin_card_dp_link a-text-normal']/@href").extract()
        for item_idx, item_url in enumerate(links):
            prod = SiteProductItem()
            unit_price = response.xpath('//div[@class="grid-item"][position()={}]'
                                        '//span[contains(@id, "unit-price")]'.format(str(item_idx+1))).re('\((.*?)\)')

            if unit_price:
                unit_price = unit_price[0].split('/')
                prod['price_per_volume'] = unit_price[0] if unit_price else None
                prod['volume_measure'] = unit_price[1] if len(unit_price) > 1 else None

            yield item_url, prod

    def _scrape_next_results_page_link(self, response):
        next_page_link = response.xpath("//div[@id='house-search-pagination']//li[contains(@class, 'a-last')]//a/@href").extract()
        if next_page_link:
            return urlparse.urljoin(response.url, next_page_link[0])
        else:
            self.log('There is no more pages')

    @staticmethod
    def _parse_upc(response):
        upc = (AmazonBaseClass._parse_upc(response)
               or response.xpath('//th[contains(text(), "UPC")]/following-sibling::td/text()').re('[\d\w]+'))
        return is_empty(upc) if isinstance(upc, list) else upc