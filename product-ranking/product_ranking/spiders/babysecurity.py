from __future__ import division, absolute_import, unicode_literals

from scrapy.log import WARNING

from product_ranking.items import SiteProductItem, Price, RelatedProduct
from product_ranking.spiders import BaseProductsSpider, \
    FormatterWithDefaults, FLOATING_POINT_RGEX, cond_set, cond_set_value

is_empty = lambda x, y=None: x[0] if x else y

class BabySecurityProductSpider(BaseProductsSpider):
    name = 'babysecurity_products'
    allowed_domains = ["babysecurity.co.uk"]

    SEARCH_URL = "http://www.babysecurity.co.uk/catalogsearch/" \
                 "result/index/?dir={direction}&order={search_sort}" \
                 "&q={search_term}"

    SEARCH_SORT = {
        'best_sellers': 'bestsellers',
        'recommended': 'position',
        'name': 'name',
        'price': 'price',
    }

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def __init__(self, search_sort='name', direction='asc', *args, **kwargs):
        super(BabySecurityProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                search_sort=self.SEARCH_SORT[search_sort],
                direction=direction,
            ),
            *args,
            **kwargs)

    def _scrape_total_matches(self, response):
        nums = response.xpath(
            'string(//p[@class="amount"])').re('(\d+)')
        if not nums:
            st = response.meta.get('search_term')
            self.log("No products found with search_term %s" % st,
                     WARNING)
            return 0

        return int(nums[-1])

    def _scrape_product_links(self, response):
        links = response.xpath(
            '//li[@class="item"]'
            '//h2[@class="product-name"]/a/@href').extract()
        if not links:
            allert = response.xpath(
                '//p[@class="note-msg"]/text()').extract()
            if allert:
                allert_msg = "Your search returned no results"
                if allert_msg in allert[0]:
                    st = response.meta.get('search_term')
                    self.log("No products were found with search term %s. "
                             "No any links available" % st, WARNING)
        for link in links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next = response.xpath(
            '//li[@class="next"]'
            '/a[contains(@class,"next")]/@href').extract()
        if next and next[0]:
            return next[0]
        else:
            return None

    def _parse_reseller_id(self, response):
        reseller_id = is_empty(response.xpath('.//*[@class="sku" and @itemprop="sku"]/text()').extract())
        if reseller_id:
            reseller_id = reseller_id.strip()
        return reseller_id

    def parse_product(self, response):
        is_empty = lambda x: x[0] if x else ""

        prod = response.meta['product']
        prod['url'] = response.url
        prod['locale'] = 'en-GB'

        brand = response.xpath(
            '//div[contains(@class,"box-brand")]/a/img/@alt').extract()
        if brand:
            prod['brand'] = brand[0].strip()
        else:
            brand = response.xpath(
                '//div[contains(@class,"brand-name")]/text()').extract()
            cond_set(
                prod, 'brand', brand, lambda x: x.strip())

        title = response.xpath(
            'string(//h1[@itemprop="name"])').extract()
        cond_set(prod, 'title', title, lambda x: x.strip())

        img = response.xpath('//a[@id="zoom-btn"]/@href').extract()
        if img:
            prod['image_url'] = img[0]

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(prod, 'reseller_id', reseller_id)

        price = response.xpath(
            '//div[@class="product-type-data"]'
            '//span[@class="price"]/text()').re(FLOATING_POINT_RGEX)
        if price:
            if len(price) > 1:
                price = price[1]
            else:
                price = price[0]
            prod['price'] = Price(price=price,
                                  priceCurrency='GBP')

        description = response.xpath('string(//div[@class="std"])').extract()
        cond_set(prod, 'description', description, lambda x: x.strip())

        avail = response.xpath(
            '//*[@itemprop="availability"]/@content').extract()
        if avail:
            if "http://schema.org/OutOfStock" in avail[0]:
                prod['is_out_of_stock'] = True
            else:
                prod['is_out_of_stock'] = False

        recommendations = []
        for li in response.xpath('//div[@class="item"]/ul/li'):
            all_inf = li.xpath('div/h3/a')
            title = all_inf.xpath('text()').extract()
            url = all_inf.xpath('@href').extract()
            recommendations.append(
                RelatedProduct(
                    title=is_empty(title),
                    url=is_empty(url)
                    )
                )
        prod['related_products'] = {'recommended':recommendations}

        return prod
