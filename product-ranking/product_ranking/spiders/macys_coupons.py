from scrapy import Spider
from re import match
from datetime import datetime
from product_ranking.items import DiscountCoupon
from product_ranking.spiders import cond_set_value

is_empty = lambda x: x[0] if x else None


class MacysCouponsSpider(Spider):
    name = 'macys_coupons_products'
    allowed_domains = ['www1.macys.com']
    DEFAULT_URL = 'http://www1.macys.com/shop/coupons-deals'

    def __init__(self, *args, **kwargs):
        super(MacysCouponsSpider, self).__init__(*args, **kwargs)
        self.product_url = kwargs.get('product_url', self.DEFAULT_URL)
        self.user_agent = ("Mozilla/5.0 (X11; Linux i686 (x86_64)) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/37.0.2062.120 Safari/537.36")
        self.start_urls = [self._valid_url(self.product_url)]

    def _valid_url(self, url):
        if not match("https?://", url):
            url = '%s%s' % ("http://", url)
        return url

    def _parse_coupons(self, response):
        return response.xpath('//ul[@class="offers"]/li')

    def _parse_description(self, coupon):
        return ' '.join(coupon.xpath('.//h2/text()').extract())

    def _parse_discount(self, coupon):
        percentage_discount = ', '.join(
            coupon.xpath('.//h2/text()').
            re('\d+\%')
        )
        flat_discount = coupon.xpath('.//h2/text()').re('\$\d+')
        flat_discount = ', '.join(flat_discount[0]) if flat_discount else ''

        return ', '.join([percentage_discount, flat_discount])

    def _parse_conditions(self, coupon):
        return is_empty(
            coupon.xpath('.//h4[@class="description"]/text()').extract()
        )

    def _parse_start_date(self, coupon):
        return None

    def _parse_end_date(self, coupon):
        d = coupon.xpath('.//h5[@class="ftr_txt1"]/b/text()').extract()
        if d:
            return datetime.strptime(d[0], '%m/%d/%Y').date().strftime('%Y-%m-%d')

    def _parse_category(self, coupon):
        return is_empty(
            coupon.xpath('.//div[@class="header"]/text()').extract()
        )

    def _parse_promo_code(self, coupon):
        return is_empty(
            coupon.xpath('.//*[@label="promo code: "]/b/text()').extract()
        )

    def parse(self, response):
        coupons = self._parse_coupons(response)

        for coupon in coupons:
            item = DiscountCoupon()
            cond_set_value(item, 'category', self._parse_category(coupon))
            cond_set_value(item, 'description', self._parse_description(coupon))
            cond_set_value(item, 'discount', self._parse_discount(coupon))
            cond_set_value(item, 'conditions', self._parse_conditions(coupon))
            cond_set_value(item, 'start_date', self._parse_start_date(coupon))
            cond_set_value(item, 'promo_code', self._parse_promo_code(coupon))
            cond_set_value(item, 'end_date', self._parse_end_date(coupon))
            yield item