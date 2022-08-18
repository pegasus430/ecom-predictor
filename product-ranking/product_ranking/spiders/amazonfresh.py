from __future__ import absolute_import, division, unicode_literals

import copy
import json
import random
import re
import string
import traceback
import urlparse
from lxml import html

from scrapy import FormRequest
from scrapy.conf import settings
from scrapy.dupefilter import BaseDupeFilter
from scrapy.http import Request
from scrapy.log import ERROR, WARNING

from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import cond_set, cond_set_value
from product_ranking.utils import is_empty


class CustomDupeFilter(BaseDupeFilter):
    """ Custom dupefilter - counts attempts """

    urls = {}

    def __init__(self, max_attempts=50, *args, **kwargs):
        self.max_attempts = max_attempts
        super(CustomDupeFilter, self).__init__(*args, **kwargs)

    def request_seen(self, request):
        if request.url not in self.urls:
            self.urls[request.url] = 0
        self.urls[request.url] += 1
        if self.urls[request.url] > self.max_attempts:
            self.log('Too many dupe attempts for url %s' % request.url, ERROR)
            return True


class AmazonFreshProductsSpider(AmazonBaseClass):
    """Spider for fresh.amazon.com site.

    Allowed search sort:
    'relevance'
    'bestselling'
    'price_lh'
    'price_hl'

    to run:
    scrapy crawl -a searchterms_str=banana [-a zip_code=12345]
    [-a order=relevance]

    related_products, upc, is_in_stock_only fields don't populated
    Note: if item marked as 'out_of_stock' price can not be parsed.
    """
    name = "amazonfresh_products"
    allowed_domains = ["www.amazon.com","amazon-adsystem.com"]

    SEARCH_URL = "https://www.amazon.com/s/ref=nb_sb_noss_2?" \
                 "url=search-alias%3Damazonfresh&field-keywords={search_term}"

    WELCOME_URL = "https://www.amazon.com/b?node=10329849011"

    ZIP_URL = "https://www.amazon.com/gp/delivery/ajax/address-change.html"

    search_sort = {
        'relevance': 'relevance',  # default
        'bestselling': 'bestselling',
        'price_lh': 'price_low_to_high',
        'price_hl': 'price_high_to_low',
    }
    zip_codes_to_recrawl = {
        'Seattle': 98101,
        'San Francisco': 94107,
        'New York': 10128,
        'Santa Monica': 90404
    }

    def __init__(self, zip_code='94117', order='relevance', *args, **kwargs):
        settings.overrides['DUPEFILTER_CLASS'] = 'product_ranking.spiders.amazonfresh.CustomDupeFilter'
        self.zip_code = zip_code
        detect_ads = kwargs.pop('detect_ads', False)
        self.detect_ads = detect_ads in (1, '1', 'true', 'True', True)

        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
        super(AmazonFreshProductsSpider, self).__init__(*args, **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')

        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['scrapy.contrib.downloadermiddleware.redirect.MetaRefreshMiddleware'] = None

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def start_requests(self):
        yield Request(
            self.WELCOME_URL,
            callback=self.login_handler
        )

    def login_handler(self, response):
        return FormRequest(
            self.ZIP_URL,
            formdata={
                'locationType': 'LOCATION_INPUT',
                'zipCode': self.zip_code,
                'deviceType': 'web',
                'pageType': 'Landing',
                'actionSource': 'glow'
            },
            callback=self.after_login,
            dont_filter=True
        )

    def after_login(self, response):
        if not self.detect_ads or self.product_url:
            return super(AmazonFreshProductsSpider, self).start_requests()
        return [
            request.replace(callback=self._parse_ad_links)
            for request in super(AmazonFreshProductsSpider, self).start_requests()
            ]

    def _parse_ad_links(self, response):
        pre_ad_links = response.meta.get('pre_ad_links', [])
        item_links = response.meta.get('item_links')
        response.meta.setdefault('total_matches', self._scrape_total_matches(response))
        response.meta.setdefault('next_page_link', self._scrape_next_results_page_link(response))
        if not item_links:
            item_links = list(self._get_product_links(response))
            response.meta['item_links'] = item_links
        if not item_links:
            return

        if not pre_ad_links:
            ad_details = response.xpath('//div[@data-ad-details]/@data-ad-details').extract()
            for ad in ad_details:
                try:
                    ad_json = json.loads(ad)
                    pre_ad_link = ad_json.get('src')
                    if pre_ad_link:
                        pre_ad_links.append(pre_ad_link)
                except:
                    continue

        response.meta['pre_ad_links'] = pre_ad_links[1:] if len(pre_ad_links) > 1 else None

        if pre_ad_links:
            return Request(
                url=pre_ad_links[0],
                meta=response.meta,
                callback=self._parse_ad_link
            )
        return self.parse(response)

    def _parse_ad_link(self, response):
        ad_json = re.search(r'aax_render_ad\((\{.*?\})\);', response.body)
        ads = response.meta.get('ads', [])
        try:
            ad_json = json.loads(ad_json.group(1))
            ad_html = html.fromstring(ad_json.get('html'))
            ad_link = ad_html.xpath('//a[@id="ad"]/@href')
            ad_image = None
            if not ad_link:
                ad_link = ad_html.xpath('//a/@href')
                ad_image = ad_html.xpath('//a/img/@src')
                ad_image = ad_image[0] if ad_image else None
            else:
                try:
                    image_script = ad_html.xpath('//script/text()')
                    ad_image_folder = re.search(r'\)\+"(.*?)",', image_script[0]).group(1)
                    image_name = re.search(r'\("ad"\).*?"(.*?\.jpg)",', image_script[0]).group(1)
                    ad_image = 'https://images-na.ssl-' + ad_image_folder + image_name
                except:
                    self.log('no ad_link: {}'.format(traceback.format_exc()), WARNING)

            if ad_image and 'amzn-gc' in ad_image:
                raise

            ads.append({
                'ad_url': ad_link[0],
                'ad_dest_products': [],
                'ad_image': ad_image
            })
            response.meta['ads'] = ads
            return Request(
                ad_link[0],
                meta=response.meta,
                callback=self._parse_ad_product_links
            )
        except:
            if response.meta.get('pre_ad_links', []):
                return self._parse_ad_links(response)
            return self.parse(response)

    def _parse_ad_product_links(self, response):
        ad_product_links = list(self._get_product_links(response))
        idx = response.meta.get('idx', 0)
        ads = response.meta.get('ads', [])
        ads[idx]['ad_dest_products'] += [{
            'name': i[1],
            'url': urlparse.urljoin(response.url, i[0])
        } for i in ad_product_links]
        ad_next_link = response.xpath('//a[@id="pagnNextLink"]/@href').extract()
        if ad_next_link:
            return Request(
                urlparse.urljoin(response.url, ad_next_link[0]),
                meta=response.meta,
                callback=self._parse_ad_product_links
            )

        idx += 1
        response.meta['idx'] = idx
        if response.meta.get('pre_ad_links', []):
            return self._parse_ad_links(response)
        return self.parse(response)

    def _scrape_title(self, response):
        return response.xpath('//div[@class="buying"]/h1/text()').extract()

    def parse_product(self, response):
        prod = response.meta['product']

        # check if we have a previously scraped product, and we got a 'normal' title this time
        _title = self._scrape_title(response)
        if _title and isinstance(_title, (list, tuple)):
            _title = _title[0]
            if 'Not Available in Your Area' not in _title:
                if getattr(self, 'original_na_product', None):
                    prod = self.original_na_product
                    prod['title'] = _title
                    return prod

        query_string = urlparse.parse_qs(urlparse.urlsplit(response.url).query)
        cond_set(prod, 'model', query_string.get('asin', ''))

        brand = response.xpath('//div[@class="byline"]/a/text()').extract()
        if not brand:
            brand = response.xpath('//div[@id="mbc"]/@data-brand').extract()
        if not brand:
            brand = re.search('brand=(.*?)&', response.body)
            if brand:
                brand = brand.group(1)
                prod['brand'] = brand
        else:
            cond_set(prod, 'brand', brand)

        price = response.xpath(
            '//div[@class="price"]/span[@class="value"]/text()').extract()
        if re.search('Business Price', response.body):
            price = response.xpath('//span[@id="priceblock_businessprice"]/text()').extract()
        cond_set(prod, 'price', price)
        if prod.get('price', None):
            if '$' not in prod['price']:
                self.log('Unknown currency at %s' % response.url, level=ERROR)
            else:
                prod['price'] = Price(
                    price=prod['price'].replace('$', '').replace(
                        ',', '').replace(' ', '').strip(),
                    priceCurrency='USD'
                )

        seller_all = response.xpath('//div[@class="messaging"]/p/strong/a')

        if seller_all:
            seller = seller_all.xpath('text()').extract()
            if seller:
                prod["marketplace"] = [{
                    "name": seller[0], 
                    "price": prod["price"],
                }]

        reseller_id = self._get_reseller_id(response.url)
        cond_set_value(prod, 'reseller_id', reseller_id)

        img_url = response.xpath(
            '//div[@id="mainImgWrapper"]/img/@src').extract()
        cond_set(prod, 'image_url', img_url)
        cond_set(prod, 'locale', ['en-US'])
        cond_set(
            prod,
            'title',
            response.xpath('//h1[@id="title"]/span/text()').extract(),
            string.strip
        )
        cond_set(
            prod,
            'brand',
            response.xpath('//span[@id="brand"]/text()').extract()
        )
        cond_set(
            prod,
            'price',
            response.xpath(
                '//span[@id="priceblock_ourprice"]/text()').extract(),
            self.__convert_to_price
        )

        # Parse price per volume
        price_volume = self._parse_price_per_volume(response)
        if price_volume:
            cond_set_value(prod, 'price_per_volume', price_volume[0])
            cond_set_value(prod, 'volume_measure', price_volume[1])

        save_percent_amount = self._parse_save_percent_amount(response)
        if save_percent_amount:
            cond_set_value(prod, 'save_percent', save_percent_amount[0])
            cond_set_value(prod, 'save_amount', save_percent_amount[1])

        buy_save_amount = self._parse_buy_save_amount(response)
        cond_set_value(prod, 'buy_save_amount', buy_save_amount)

        was_now = self._parse_was_now(response)
        cond_set_value(prod, 'was_now', was_now)

        promotions = any([
            price_volume,
            save_percent_amount,
            buy_save_amount,
            was_now
        ])
        cond_set_value(prod, 'promotions', promotions)

        cond_set(
            prod,
            'image_url',
            response.xpath(
                '//div[@id="imgTagWrapperId"]/img/@data-a-dynamic-image'
            ).extract(),
            self.__parse_image_url
        )
        rating = response.xpath('//span[@class="crAvgStars"]')
        cond_set(
            prod,
            'model',
            rating.xpath(
                '/span[contains(@class, "asinReviewsSummary")]/@name'
            ).extract()
        )
        reviews = self.__parse_rating(response)
        if not reviews:
            cond_set(
                prod,
                'buyer_reviews',
                ZERO_REVIEWS_VALUE
            )
        else:
            prod['buyer_reviews'] = reviews
        prod['is_out_of_stock'] = bool(response.xpath(
            '//div[@class="itemUnavailableText"]/span').extract())

        title = self._scrape_title(response)
        cond_set(prod, 'title', title)
        if 'Not Available in Your Area' in prod.get('title', ''):
            new_zip_code = str(random.choice(self.zip_codes_to_recrawl.values()))
            self.log('Product not available for ZIP %s - retrying with %s' % (
                self.zip_code, new_zip_code))
            self.zip_code = new_zip_code
            if not getattr(self, 'original_na_product', None):
                self.original_na_product = copy.deepcopy(prod)
            return Request(self.WELCOME_URL, callback=self.login_handler)

        return prod

    @staticmethod
    def _get_reseller_id(link):
        reseller_id = re.search('dp/([A-Z\d]+)', link)
        return reseller_id.group(1) if reseller_id else None

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

    @staticmethod
    def _parse_buy_save_amount(response):
        buy_save = None
        save_amount = response.xpath("//span[@class='apl_m_font']/text()").extract()
        if save_amount and 'Buy' in save_amount[0] and ', Save' in save_amount[0]:
            buy_save = re.findall(r'\d+\.?\d*', save_amount[0])

        return ', '.join(buy_save) if buy_save else None

    def _parse_was_now(self, response):
        was_now = None
        past_price = response.xpath('//span[contains(@class, "a-text-strike")]/text() | '
                                    '//td[@class="a-color-base a-align-bottom a-text-strike"]/text()')
        current_price = response.xpath('//span[@id="priceblock_ourprice"]/text()| '
                                       '//td[@class="a-color-price a-size-medium"]/text()')

        if past_price and current_price:
            past_price = past_price[0].re('\d+\.?\d*')
            current_price = current_price[0].re('\d+\.?\d*')
            if past_price and current_price:
                was_now = ', '.join([current_price[0], past_price[0]])
        return was_now

    def __convert_to_price(self, x):
        price = re.findall(r'(\d+\.?\d*)', x)
        if not price:
            self.log('Error while parse price.', ERROR)
            return None
        return Price(
            priceCurrency='USD',
            price=float(price[0])
        )

    def __parse_image_url(self, x):
        try:
            images = json.loads(x)
            return images.keys()[0]
        except Exception as e:
            self.log('Error while parse image url. ERROR: %s.' % str(e), ERROR)
            return None

    def __parse_rating(self, response):
        try:
            total_reviews = int(response.xpath(
                '//span[@data-hook="total-review-count"]/text()'
            )[0].extract().replace(',', ''))

            average_rating = response.xpath(
                '//*[@data-hook="average-star-rating"]/span/text()'
            )[0].extract()
            average_rating = float(re.search('(.*) out', average_rating).group(1))
            return BuyerReviews(
                num_of_reviews=total_reviews,
                average_rating=average_rating,
                rating_by_star={}
            )
        except:
            self.log('Error while parse rating: {}'.format(traceback.format_exc()))
            return None

    def _search_page_error(self, response):
        try:
            found1 = response.xpath(
                '//div[@class="warning"]/p/text()').extract()[0]
            found2 = response.xpath(
                '//div[@class="warning"]/p/strong/text()').extract()[0]
            found = found1 + " " + found2
            if 'did not match any products' in found:
                self.log(found, ERROR)
                return True
            return False
        except IndexError:
            return False

    def _scrape_total_matches(self, response):
        count_text = is_empty(response.xpath(
            '//*[@id="s-result-count" and (self::h1 or self::h2 or self::span)]/text()'
        ).extract())
        if not count_text:
            return 0
        count = re.findall(r'of\s([\d,]+)', count_text)
        if not count:
            count = re.findall(r'([\d,]+)\sresults', count_text)
        return int(count[0].replace(',', '')) if count else 0

    def _get_product_links(self, response):
        ul = response.xpath('//div[@id="atfResults"]//li[contains(@class, "s-result-item")] | '
                            '//div[@id="btfResults"]//li[contains(@class, "s-result-item")]')

        if not ul:
            ul = response.xpath("//li[contains(@class, 's-result-item')]")
        for li in ul:
            link = is_empty(li.xpath(
                './/a[contains(@class, "s-access-detail-page") or contains(@class, "a-link-normal")]/@href'
            ).extract())
            name = is_empty(li.xpath(
                './/a[contains(@class, "s-access-detail-page") or contains(@class, "a-link-normal")]/@title'
            ).extract())
            if not link:
                continue
            yield link, name

    def _scrape_product_links(self, response):
        item_links = response.meta.get('item_links', [])
        if not item_links:
            item_links = list(self._get_product_links(response))

        for item in item_links:
            prod = SiteProductItem()
            ads = response.meta.get('ads', [])
            if self.detect_ads and ads:
                prod['ads'] = ads
            yield item[0], prod

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        next_req = meta.get('next_page_link')
        if not next_req:
            link = is_empty(response.xpath(
                '//a[@id="pagnNextLink"]/@href'
            ).extract())
            if not link:
                return None
            url = urlparse.urljoin(response.url, link)
            if meta.get('item_links'):
                meta['item_links'] = None
            meta['next_page_link'] = None
            next_req = Request(
                url,
                meta=meta
            )
        return next_req

    def _parse_single_product(self, response):
        return self.parse_product(response)
