from re import match
from scrapy import Spider, Request
from product_ranking.items import DiscountCoupon
from product_ranking.spiders import cond_set_value

is_empty = lambda x: x[0] if x else None


class DockersCouponsSpider(Spider):
    name = 'dockers_coupons_products'
    allowed_domains = ['dockers.com']
    user_agent = ("Mozilla/5.0 (X11; Linux i686 (x86_64)) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/37.0.2062.120 Safari/537.36")
    DEFAULT_URLS = [
        ('http://www.dockers.com/US/en_US/category/men/collections/'
         'dockers-collections-semiannualsale/_/'
         'N-2sZ1z13x74Z895Z1z13u42Z1z13x71Z1z140oj'),

        ('http://www.dockers.com/US/en_US/category/women/clothing/collections/'
         'dockers-collections-semiannualsale/_/'
         'N-2sZ1z13x74Z89mZ1z13u42Z1z13x71Z1z140oj')
    ]
    REQUEST_TIMES = 1

    def __init__(self, *args, **kwargs):
        super(DockersCouponsSpider, self).__init__(*args, **kwargs)
        product_url = kwargs.get('product_url')
        if product_url:
            self.product_urls = [product_url]
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
        return is_empty(coupon.css('#promo-shipping > h4::text').extract())

    def _parse_discount(self, coupon):
        return ', '.join(
            coupon.css('#promo-shipping > h4::text').re('\$\d+|\d+\%')
        )

    def _parse_conditions(self, coupon):
        return ' '.join(coupon.css('#promo-shipping > p ::text').extract())

    def _parse_start_date(self, coupon):
        return None

    def _parse_end_date(self, coupon):
        return None

    def _parse_category(self, coupon):
        return None

    def parse(self, response):
        coupon_links = self._parse_coupons(response)

        for link in coupon_links:
            url = '%s://www.%s%s' % ('http', self.allowed_domains[0], link)
            yield Request(url, callback=self.parse_coupon)

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
        return item