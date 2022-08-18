from __future__ import division, absolute_import, unicode_literals
import json
import re

from scrapy.http import HtmlResponse

from product_ranking.items import Price, BuyerReviews
from product_ranking.spiders import cond_set, \
    cond_set_value, FLOATING_POINT_RGEX


# scrapy crawl amazoncouk_products -a searchterms_str="iPhone"


from product_ranking.spiders.contrib.product_spider import ProductsSpider


# TODO: related_products

is_empty = lambda x,y=None: x[0] if x else y

class GandermountainProductsSpider(ProductsSpider):
    name = "gandermountain_products"
    allowed_domains = ["www.gandermountain.com"]
    start_urls = []

    SEARCH_URL = "http://www.gandermountain.com/modperl/wbsrvcs" \
                 "/adobeSearch.cgi?do=json&q={search_term}&sort={sort_mode}" \
                 "&page={page}"

    SORT_MODES = {
        'default': '',
        'relevance': 'relevance',
        'new': 'dateNew',
        'price_desc': 'priceSortHigh',
        'price_asc': 'priceSortLow',
        'brand_asc': 'brand',
        'brand_desc': 'brand_r',
        'rating': 'averageReviewScore',
        'best': 'SC_Units'
    }

    HARDCODED_FIELDS = {
        'locale': 'en-US'
    }

    def __init__(self, *args, **kwargs):
        super(GandermountainProductsSpider, self).__init__(*args, **kwargs)
        self.url_formatter.defaults['page'] = 1

    def parse(self, response):
        json_data = json.loads(response.body_as_unicode())
        resp = HtmlResponse(response.url, response.status, response.headers,
                            ''.join([chunk for chunk in json_data.itervalues()
                                     if isinstance(chunk, unicode)]),
                            response.flags, response.request,
                            encoding=response.encoding)

        return list(super(GandermountainProductsSpider, self).parse(resp))

    def _parse_single_product(self, response):
        return self.parse_product(response) 

    def _scrape_next_results_page_link(self, response):
        next_link = response.css('[alt=arrow-r-blue]')
        if not next_link:
            return
        page = int(re.findall('page=(\d+)', response.url)[0]) + 1
        search_term = response.meta['search_term']
        return self.url_formatter.format(self.SEARCH_URL, page=page,
                                         search_term=search_term)

    def _total_matches_from_html(self, response):
        matches = response.xpath(
            '//p[@class="page-numbers"]/strong/text()').re('\d+')
        return int(matches[0]) if matches else 0

    def _fetch_product_boxes(self, response):
        return response.css('[id*=bItem]')

    def _link_from_box(self, box):
        return box.css('a[title]::attr(href)')[0].extract()

    def _populate_from_box(self, response, box, product):
        cond_set(product, 'title',
                 box.css('a[data-item-number]::attr(title)').extract())
        cond_set(product, 'price',
                 box.css('.price-point font::text').re('\$([\d ,.]+)'))
        cond_set(product, 'price',
                 box.css('.red-message.price-point::text').re('\$([\d ,.]+)'))
        cond_set(product, 'price',
                 box.css('.price-point::text').re('\$([\d ,.]+)'))

    def _populate_from_html(self, response, product):
        title = response.xpath(
            '//div[contains(@class, "product-title")]/h1/text()').extract()
        if isinstance(title, list):
            title = ''.join(title)
        cond_set(product, 'title', (title.strip(),))
        cond_set(product, 'price',
                 response.css('.saleprice span::text').re('\$([\d ,.]+)'))
        cond_set(product, 'price',
                 response.css('.regprice span::text').re('\$([\d ,.]+)'))
        image_url = is_empty(response.css('.jqzoom img::attr(src)').extract())
        if image_url:
            image_url = is_empty(re.findall("(.*)\?", image_url))
        if not "http" == image_url[:4]:
            image_url = "http:" + image_url
        cond_set(product, 'image_url', (image_url,))
        cond_set_value(product, 'is_out_of_stock', not (response.css(
            '.stockstatus .info::text').re('In Stock|Low Stock')))
        cond_set(product, 'brand',
                 response.css('.alignBrandImageSpec::attr(alt)').extract(),
                 lambda brand: brand.replace('_', ' '))
        xpath = '//td[@class="detailsText"]/text() | ' \
                '//div[contains(@class, "tab-info")]' \
                '/div[contains(@class, "tab-title")]' \
                '/h2[contains(text(), "details")]/../../div'
        cond_set_value(product, 'description',
                       response.xpath(xpath).extract(), u''.join)
        price = product.get('price', None)
        if price == 0:
            del product['price']
        elif price:
            product['price'] = Price(priceCurrency='USD',
                                     price=re.sub('[ ,]', '', price))

        reseller_id_regex = "i=(\d+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        model = response.xpath(
            "//div[@class='item']/text()").re(FLOATING_POINT_RGEX)
        cond_set(product, 'model', model)
        self._populate_buyer_reviews(response, product)

    def _populate_buyer_reviews(self, response, product):
        total = response.css(
            '.pr-snapshot-average-based-on-text .count::text').re('[\d ,]+')
        if not total:
            cond_set_value(product, 'buyer_reviews', 0)
            return
        total = int(re.sub('[ ,]', '', total[0]))
        avg = response.css('.pr-rating.pr-rounded.average::text')[0].extract()
        avg = float(avg)
        by_star = response.css('.pr-histogram-count span::text')
        by_star = by_star.re('\(([\d, ]+)\)')
        by_star = {i + 1: int(re.sub('[ ,]', '', c))
                   for i, c in enumerate(reversed(by_star))}

        cond_set_value(product, 'buyer_reviews',
                       BuyerReviews(num_of_reviews=total,
                                    average_rating=avg,
                                    rating_by_star=by_star))

        if not total or not avg:
            cond_set_value(product, 'buyer_reviews', 0)

    def _scrape_results_per_page(self, response):
        per_page = response.css('.per-page option[selected=true]::text')
        per_page = per_page.re('\d+')
        return int(per_page[0]) if per_page else None
