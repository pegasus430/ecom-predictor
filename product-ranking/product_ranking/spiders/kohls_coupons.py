from scrapy import Spider
from re import match
from dateutil.parser import parse as parse_date
from product_ranking.items import DiscountCoupon
from product_ranking.spiders import cond_set_value

is_empty = lambda x: x[0] if x else None


class KohlsCouponsSpider(Spider):
    name = 'kohls_coupons_products'
    allowed_domains = ['www.kohls.com']
    DEFAULT_URL = 'http://www.kohls.com/sale-event/coupons-deals.jsp'

    def __init__(self, *args, **kwargs):
        super(KohlsCouponsSpider, self).__init__(**kwargs)
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
        return response.css('.grid-box.d8x4.m8x5')

    def _parse_description(self, coupon):
        return ' '.join(coupon.css('.td-header::text, '
                                   '.td-subheader::text').extract())

    def _parse_discount(self, coupon):
        return ', '.join(
            #coupon.css('.td-header::text').re('\$?\d+(?:\.\d+)?(?:\-\d+)?%?')
            coupon.css('.td-header::text').re('\$\d+|\d+(?:\-\d+)?%')
        )

    def _parse_conditions(self, coupon):
        # return ' '.join(coupon.css('.td-copy::text').extract())
        return ' '.join(coupon.xpath('.//*[contains(@class,"td-copy")][1]'
                                     '/text()').extract())

    def _parse_start_date(self, coupon):
        return None

    def _parse_end_date(self, coupon):
        d = coupon.css('.td-date::text').re('Ends (\w+ \d+)')
        if d:
            return parse_date(d[0]).date().strftime('%Y-%m-%d')

    def _parse_category(self, coupon):
        return is_empty(coupon.css('.td-subheader::text').extract())

    def parse(self, response):
        coupons = self._parse_coupons(response)

        for coupon in coupons:
            item = DiscountCoupon()
            cond_set_value(item, 'description', self._parse_description(coupon))
            cond_set_value(item, 'category', self._parse_category(coupon))
            cond_set_value(item, 'discount', self._parse_discount(coupon))
            cond_set_value(item, 'conditions', self._parse_conditions(coupon))
            cond_set_value(item, 'start_date', self._parse_start_date(coupon))
            cond_set_value(item, 'end_date', self._parse_end_date(coupon))
            yield item
