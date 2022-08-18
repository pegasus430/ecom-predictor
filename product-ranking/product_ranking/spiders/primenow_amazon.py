from __future__ import absolute_import, division, unicode_literals

import re
import string
import traceback
import urlparse
import math

import yaml
from lxml import html
from scrapy import Request
from scrapy.log import WARNING

from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FormatterWithDefaults
from product_ranking.utils import extract_first, is_empty
from spiders_shared_code.primenow_amazon_variants import PrimenowAmazonVariants


class PrimenowAmazonProductsSpider(BaseProductsSpider):
    name = "primenow_amazon_products"
    allowed_domains = ["primenow.amazon.com"]

    SEARCH_URL = "https://primenow.amazon.com/search?k={search_term}&page={page_num}"

    WELCOME_URL = "https://primenow.amazon.com"

    def __init__(self, *args, **kwargs):
        url_formatter = FormatterWithDefaults(page_num=1)
        super(PrimenowAmazonProductsSpider, self).__init__(
            url_formatter, site_name=self.allowed_domains[0], *args, **kwargs)
        self.user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                          "Chrome/65.0.3225.181 Safari/537.36"

        self.zip_code = kwargs.get('zip_code', '10036')

    def start_requests(self):
        yield Request(
            self.WELCOME_URL,
            callback=self.login_handler
        )

    def login_handler(self, response):
        csrf_token = response.xpath(
            "//form[@id='locationSelectForm']"
            "//input[@name='offer-swapping-token']"
            "/@value").extract()[0]

        if not csrf_token:
            self.log('Can\'t find csrf token.', WARNING)
            return None

        LOG_IN_URL = "https://primenow.amazon.com/cart/initiatePostalCodeUpdate?newPostalCode=" \
                     "{postalCode}&noCartUpdateRequiredUrl=%2F&allCartItemsSwappableUrl" \
                     "=%2F&someCartItemsUnswappableUrl=%2F&offer-swapping-token" \
                     "={csrf_token}".format(postalCode=self.zip_code, csrf_token=str(csrf_token))

        return Request(
            LOG_IN_URL,
            method='POST',
            callback=self._start_requests,
            dont_filter=True
        )

    def _start_requests(self, response):
        for request in super(PrimenowAmazonProductsSpider, self).start_requests():
            if self.searchterms:
                session_id = re.search('"sessionId":"(.*?)"}', response.body_as_unicode())

                if session_id:
                    request = request.replace(cookies={'session-id': session_id.group(1)})
                else:
                    self.log("Found no session id {}".format(traceback.format_exc()))
                    request = request.replace(self.WELCOME_URL, callback=self.login_handler)

            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product['locale'] = "en-US"

        no_longer_available = self._parse_no_longer_available(response)
        cond_set_value(product, 'no_longer_available', no_longer_available)

        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=lambda x: x.replace('\n', '').strip())

        brand = AmazonBaseClass._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

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

        promotions = any([
            price_volume,
            save_percent_amount,
            buy_save_amount,
            was_now
        ])
        cond_set_value(product, 'promotions', promotions)

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

        origin = self._parse_origin(response)
        cond_set_value(product, 'origin', origin)

        is_out_of_stock = self._parse_stock_status(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        if asin:
            product['reseller_id'] = asin
            product['url'] = "https://primenow.amazon.com/dp/{}".format(asin)
        else:
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
            num_of_reviews = re.match(r'(\d*\.?\d+)', str(self._clean_text(''.join(num_of_reviews_info).replace(',', '')))).group()
        else:
            num_of_reviews = 0

        rating_values = []
        rating_counts = []

        # Get mark of Review
        rating_values_data = response.xpath("//div[contains(@class, 'histoRating')]//text()").extract()
        if rating_values_data:
            for rating_value in rating_values_data:
                rating_values.append(int(re.findall(r'(\d+)', rating_value[0])[0]))

        # Get count of Mark
        rating_count_data = response.xpath("//div[contains(@class, 'histoCount')]//text()").extract()
        if num_of_reviews:
            if rating_count_data:
                for rating_count in rating_count_data:
                    rating_count = int(num_of_reviews) * int(re.findall(r'(\d+)', rating_count)[0]) / 100
                    rating_counts.append(int(format(rating_count, '.0f')))

        if rating_counts:
            rating_counts = list(reversed(rating_counts))

        if len(rating_counts) == 5:
            rating_by_star = {'1': rating_counts[0], '2': rating_counts[1],
                              '3': rating_counts[2], '4': rating_counts[3], '5': rating_counts[4]}
        else:
            rating_by_star = {}

        avarage_rating = response.xpath("//span[@id='acrPopover']/@title").extract()

        if avarage_rating:
            average_rating = re.match(r'(\d*\.?\d+)', avarage_rating[0]).group()
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

    def _parse_price(self, response):
        price = response.xpath(
            '//div[@id="price"]//*[contains(@class, "a-color-price") and contains(@class, "a-size-medium")]/text()'
        ).extract()
        if price:
            price = ''.join(price)
            if '$' not in price:
                self.log('Unknown currency at %s' % response.url)
            else:
                return Price(
                    price=price.replace(',', '').replace(
                        '$', '').strip(),
                    priceCurrency='USD'
                )

    def _parse_model(self, response):
        model = None
        product_detail = response.xpath("//td[@class='bucket']//ul//li").extract()
        product_details = response.xpath("//table[@id='productDetails_detailBullets_sections1']//tr").extract()
        if product_detail:
            for product_info in product_detail:
                if 'Item model number:' in product_info:
                    model = html.fromstring(product_info).xpath("//li/text()")[0]
        else:
            for product_info in product_details:
                if 'Item model number' in product_info:
                    model = html.fromstring(product_info).xpath("//tr//td[@class='a-size-base']/text()")[0]
                    model = self._clean_text(model)
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
            self.log("Can't extract save percent amount {}".format(traceback.format_exc(e)), WARNING)

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
        current_price = response.xpath('//*[contains(@class, "a-color-price") and contains(@class, "a-size-medium")]/text()')

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
        pav = PrimenowAmazonVariants()
        pav.setupSC(response)
        variants = pav._variants()

        return variants

    def _parse_stock_status(self, response):
        is_out_of_stock = is_empty(
            response.xpath("//div[@id='availability']//span/text()").extract(), ''
        )

        is_out_of_stock = "out of stock" in is_out_of_stock.lower()

        return is_out_of_stock

    def _parse_origin(self, response):
        element = response.xpath("//table[@id='productDetails_detailBullets_sections1']//tr").extract()
        for i, attr in enumerate(element):
            if 'origin' in attr.lower():
                origin = html.fromstring(attr).xpath(".//td[@class='a-size-base']/text()")
                return origin[0].strip() if origin else None

    def _scrape_total_matches(self, response):
        total = re.search('"totalResults":(\d+)', response.body)
        return int(total.group(1)) if total else 0

    def _scrape_product_links(self, response):
        links = response.xpath("//ul/li[contains(@class, 'product_grid__item')]"
                               "//a[contains(@class, 'asin_card__productLink')]").extract()
        for item_url in links:
            link = urlparse.urljoin(response.url, item_url)
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        current_page = response.meta.get('current_page', 1)
        total_matches = response.meta.get('total_matches')
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 30
        if (total_matches and results_per_page
            and current_page < math.ceil(total_matches / float(results_per_page))):
            current_page += 1
            response.meta['current_page'] = current_page

            return Request(self.SEARCH_URL.format(search_term=response.meta['search_term'],
                                                  page_num=current_page),
                           meta=response.meta)

    @staticmethod
    def _parse_upc(response):
        upc = (AmazonBaseClass._parse_upc(response)
               or response.xpath('//th[contains(text(), "UPC")]/following-sibling::td/text()').re('[\d\w]+'))
        return is_empty(upc) if isinstance(upc, list) else upc
