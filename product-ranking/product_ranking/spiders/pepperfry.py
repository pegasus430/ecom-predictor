import re

from scrapy.log import WARNING

from spiders_shared_code.pepperfry_variants import PepperfryVariants
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, \
    cond_set, cond_set_value
from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import FLOATING_POINT_RGEX


class PepperfryProductsSpider(BaseProductsSpider):
    name = 'pepperfry_products'
    allowed_domains = ['www.pepperfry.com']

    SEARCH_URL = 'https://www.pepperfry.com/site_product/search?q={search_term}&as=0&p={page_num}'

    def __init__(self, *args, **kwargs):
        super(PepperfryProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page_num=1),
            site_name=self.allowed_domains[0],
            *args, **kwargs)

    def start_requests(self):
        for request in super(PepperfryProductsSpider, self).start_requests():
            request = request.replace(dont_filter=True)
            yield request

    def _scrape_product_links(self, response):
        self.product_links = response.xpath('//div[@class="pf-col xs-12"]/*/a/@href').extract()

        for product_link in self.product_links:
            yield product_link, SiteProductItem()

    def _scrape_total_matches(self, response):
        try:
            return int(re.search('totalProductCount="(\d+)"', response.body).group(1))
        except:
            self.log("Failed to extract total matches", WARNING)
            return 0

    def _scrape_next_results_page_link(self, response):
        curr_page = response.xpath('//span[@id="current-page-no"]/text()').extract()
        total_pages = response.xpath('//span[@id="current-page-no"]/following-sibling::span/text()').extract()
        try:
            curr_page = int(curr_page[0])
            total_pages = int(total_pages[0])
            if curr_page < total_pages:
                search_term = response.meta['search_term']
                next_page_link = self.SEARCH_URL.format(search_term=search_term, page_num=curr_page + 1)
                return next_page_link
        except:
            self.log("Failed to parse pagination", WARNING)
            return

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _populate_from_html(self, response, prod):
        # title
        title = response.css('h1[itemprop=name]::text').extract()
        cond_set_value(prod, 'title', title[0] if title else None)

        # price
        currency = response.xpath("//meta[@itemprop='priceCurrency']/@content")
        price = response.xpath('//span[contains(@class, "vip-our-price-amt")]/text()').extract()
        if price:
            price = re.search('\d+', self._clean_text(price[0].replace(',', '')))
            if currency and price:
                prod['price'] = Price(currency[0].extract(), price.group(0))

        # out of stock
        cond_set_value(
            prod, 'is_out_of_stock', response.css('.out_of_stock_box'), bool)

        # image
        image = response.xpath("//img[@itemprop='image']/@data-src").extract()
        cond_set_value(prod, 'image_url', image[0] if image else None)

        # brand
        brand = response.css('input[name=brand_name] ::attr(value)')
        cond_set(prod, 'brand', brand.extract())

        # reseller_id
        regex = "-(\d+)\."
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(prod, "reseller_id", reseller_id)

        categories = self._parse_categories(response)
        cond_set_value(prod, 'categories', categories)

        category = self._category_name(response)
        cond_set_value(prod, 'category', category)

    def parse_product(self, response):
        prod = response.meta['product']
        cond_set_value(prod, 'url', response.url)
        cond_set_value(prod, 'locale', 'en-IN')
        self._populate_from_html(response, prod)
        pv = PepperfryVariants()
        pv.setupSC(response)
        variants = pv._variants()
        cond_set_value(prod, 'variants', variants)
        return prod

    def _parse_categories(self, response):
        categories = response.xpath("//span[@itemprop='title']/text()").extract()
        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t\r]", "", text).strip()
