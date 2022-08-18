from re import match
from scrapy import Spider, Request
from product_ranking.items import DiscountCoupon
from product_ranking.spiders import cond_set_value
from datetime import datetime
import re

is_empty = lambda x: x[0] if x else None


class LeviCouponsSpider(Spider):
    name = 'levi_coupons_products'
    allowed_domains = ['levi.com']
    user_agent = ("Mozilla/5.0 (X11; Linux i686 (x86_64)) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/37.0.2062.120 Safari/537.36")
    DEFAULT_URLS = [
        # 'http://www.levi.com/US/en_US/',
        'http://www.levi.com/US/en_US/category/sale/men/all',
        'http://www.levi.com/US/en_US/category/sale/women/all',
        'http://www.levi.com/US/en_US/category/sale/kids/all'
    ]
    REQUEST_TIMES = 1

    def __init__(self, *args, **kwargs):
        super(LeviCouponsSpider, self).__init__(*args, **kwargs)
        product_url = kwargs.get('product_url')
        if product_url and not product_url == 'http://www.levi.com/US/en_US/':
            self.product_urls = product_url.split('|||')
        else:
            self.product_urls = self.DEFAULT_URLS * self.REQUEST_TIMES

    def start_requests(self):
        return [
            Request(url, callback=self.parse, dont_filter=True)
            for url in self.product_urls
        ]

    def _valid_url(self, url):
        if not match("https?://", url):
            url = '%s%s' % ("http://", url)
        return url

    def _parse_coupons(self, response):
        return response.css('.latest-deal-details > .latest-deal-subsales > '
                            '.subsale a::attr(href)').extract()

    def _parse_description(self, coupon):
        desc = is_empty(coupon.css('#promo-shipping > h4::text').extract())
        desc = desc.strip() if desc else None
        return desc

    def _parse_discount(self, coupon):
        return ', '.join(
            coupon.css('#promo-shipping > h4::text').re('\$\d+|\d+\%')
        )

    def _parse_conditions(self, coupon):
        cond = ' '.join(coupon.css('#promo-shipping > p ::text').extract())
        cond = cond.strip() if cond else None
        return cond

    def _parse_start_date(self, coupon):
        return None

    def _parse_end_date(self, coupon):
        cond = ' '.join(coupon.css('#promo-shipping > p ::text').re("\d+\/\d+\/\d+"))
        try:
            date = datetime.strptime(cond, '%m/%d/%y').date().strftime('%Y-%m-%d')
        except:
            date = None
        return date

    def _parse_category(self, coupon):
        return None

    def parse(self, response):
        if not "category/" in response.url:
            # Dont need this currently
            # popup_promo = self._parse_popup_promo(response)
            # if popup_promo:
            #     yield popup_promo
            promo = self._parse_special_promo_code(response)
            if promo:
                yield promo
        else:
            coupon_links = self._parse_coupons(response)

            for link in coupon_links:
                url = '%s://www.%s%s' % ('http', self.allowed_domains[0], link)
                yield Request(url, callback=self.parse_coupon)

    def _parse_popup_promo(self, response):
        item = DiscountCoupon()
        description = response.xpath('.//*[@class="subscribe_header"]/text()').extract()
        description = description[0].strip() if description else None
        if description:
            cond_set_value(item, 'description', description)
            cond_set_value(item, 'category', None)
            cond_set_value(item, 'discount', ' '.join(response.xpath(".//*[@id='EmailSignupForm']/p[1]/text()").re('\d+\%')))
            cond_set_value(item, 'conditions', ''.join(response.xpath(".//*[@id='EmailSignupForm']/p[1]/text()").extract()))
            cond_set_value(item, 'start_date', None)
            cond_set_value(item, 'end_date', None)
            cond_set_value(item, 'promo_code', None)
            return item

    def _parse_special_promo_code(self, response):
        item = DiscountCoupon()
        description = response.xpath(".//*[@id='mdl-jc-sale-campaign']/p[1]/text()").extract()
        if description:
            cond_set_value(item, 'description', description)
            cond_set_value(item, 'category', None)
            cond_set_value(item, 'discount', response.xpath(".//*[@id='mdl-jc-sale-campaign']/h2/text()").re('\d+\%'))
            cond_set_value(item, 'conditions', response.xpath(".//*[@id='mdl-jc-sale-campaign']/h2/text()").extract())
            cond_set_value(item, 'start_date', None)
            cond_set_value(item, 'end_date', None)
            promo_code = response.xpath(".//*[@id='mdl-jc-sale-campaign']/*[contains(text(), 'code ')]/text()").extract()
            promo_code = ''.join(promo_code).split(' ')
            promo_code = promo_code[-1] if promo_code else None
            cond_set_value(item, 'promo_code', promo_code)
            return item

    def parse_coupon(self, response):
        item = DiscountCoupon()
        d = self._parse_description(response)
        cond_set_value(item, 'description', d)
        if not d:
            return
        cond_set_value(item, 'category', self._parse_category(response))
        cond_set_value(item, 'discount', self._parse_discount(response))
        cond_set_value(item, 'conditions', self._parse_conditions(response))
        cond_set_value(item, 'start_date', self._parse_start_date(response))
        cond_set_value(item, 'end_date', self._parse_end_date(response))
        promo_code = None
        if not item.get('promo_code'):
            promo_regex = "[Uu]sing\s?[Pp]romo\s?[Cc]ode:\s?([A-Z0-9]+)"
            promo_code = re.findall(promo_regex, item.get('conditions'))
            promo_code = promo_code[0] if promo_code else None
            if not promo_code:
                promo_code = re.findall(promo_regex, item.get('description'))
                promo_code = promo_code[0] if promo_code else None
        cond_set_value(item, 'promo_code', promo_code)
        return item