#
# Discount coupons for pages like http://www.jcpenney.com/jsp/browse/marketing/promotion.jsp?pageId=pg40027800029#
#

import re

import scrapy
from dateutil.parser import parse as parse_date

from product_ranking.items import DiscountCoupon

is_empty = lambda x: x[0] if x else None


class JCPenneyCouponsSpider(scrapy.Spider):
    name = 'jcpenney_coupons_products'
    allowed_domains = ['jcpenney.com', 'www.jcpenney.com']
    DEFAULT_URL = 'http://www.jcpenney.com/jsp/browse/marketing/promotion.jsp?pageId=pg40027800029#'

    def __init__(self, *args, **kwargs):
        super(JCPenneyCouponsSpider, self).__init__(**kwargs)
        self.product_url = kwargs.get('product_url', self.DEFAULT_URL)
        self.user_agent = "Mozilla/5.0 (X11; Linux i686 (x86_64))" \
                          " AppleWebKit/537.36 (KHTML, like Gecko)" \
                          " Chrome/37.0.2062.120 Safari/537.36"
        self.start_urls = [self._valid_url(self.product_url)]

    def _valid_url(self, url):
        if not re.match("https?://", url):
            url = '%s%s' % ("http://", url)
        return url

    def _parse_coupons(self, response):
        return response.xpath("//div[contains(@class,'couponItem_container')]")

    def _parse_description(self, coupon):
        str_arr = coupon.xpath(".//div[@class='couponItem_valid']//text()").extract()
        str_arr += coupon.xpath(".//div[@class='couponItem_code']//text()").extract()
        str_desc = " ".join([x for x in str_arr if len(x.strip()) > 0])
        return str_desc

    def _parse_category(self, coupon):
        return is_empty(
            coupon.xpath(".//div[@class='couponItem_location']//text()").extract()
        )

    def _parse_start_date(self, coupon):
        return None

    def _parse_end_date(self, coupon):
        try:
            str_date = coupon.xpath(".//div[@class='couponItem_valid']//text()").extract()
            str_date = " ".join(str_date[0].split(" ")[2:])
            return parse_date(str_date).strftime('%Y-%m-%d')
        except:
            return None

    def _parse_discount(self, coupon):
        discounts = coupon.xpath(".//*[@class='couponItem_offers']//text()").extract()
        str_discount = " ".join([x for x in discounts if len(x.strip()) > 0])
        return str_discount

    def _parse_conditions(self, coupon):
        conditions = coupon.xpath(".//*[contains(@class, 'couponItem_offers')]//span//text()").extract()
        str_conditions = ",".join([x for x in conditions if len(x.strip()) > 0])
        return str_conditions

    def _parse_promo_code(self, coupon):
        return is_empty(
            coupon.xpath(".//div[@class='couponItem_code']/strong//text()").extract()
        )

    def parse(self, response):
        coupons = self._parse_coupons(response)

        for coupon in coupons:
            item = DiscountCoupon()
            item['category'] = self._parse_category(coupon)
            item['description'] = self._parse_description(coupon)
            item['start_date'] = self._parse_start_date(coupon)
            item['end_date'] = self._parse_end_date(coupon)
            item['discount'] = self._parse_discount(coupon)
            item['conditions'] = self._parse_conditions(coupon)
            item['promo_code'] = self._parse_promo_code(coupon)
            yield item
