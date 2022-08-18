from __future__ import division, absolute_import, unicode_literals
import re
import traceback

from scrapy.log import WARNING, INFO, DEBUG
from scrapy.http import Request

from product_ranking.items import SiteProductItem, Price, RelatedProduct
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults
from product_ranking.spiders import cond_set, cond_set_value,\
    cond_replace_value, _extract_open_graph_metadata, populate_from_open_graph


# You may add additional argument -a search_sort="price-desc"/"price-asc"
class CoachSpider(BaseProductsSpider):
    handle_httpstatus_list = [404]
    name = 'coach_products'
    allowed_domains = ["coach.com"]
    start_urls = []

    SEARCH_URL = "http://www.coach.com/search?q={search_term}"

    SEARCH_SORT = {
        'default': "",
        'price-asc': "price-low-to-high",
        'price-desc': "price-high-to-low",
    }

    def __init__(self, search_sort='default', *args, **kwargs):
        self.search_sort = self.SEARCH_SORT[search_sort]
        self.new_stile = False
        # used to store unique links
        self.links = []
        # used to store all response from new_stile site version
        # to prevent make additional requests
        self.initial_responses = []
        super(CoachSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                search_sort=self.search_sort,
            ), *args, **kwargs
        )

    def parse_product(self, response):
        if self.new_stile:
            return self.parse_product_new(response)
        else:
            return self.parse_product_old(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product_new(self, response):
        prod = response.meta['product']
        populate_from_open_graph(response, prod)

        prod['locale'] = 'en_US'

        title = response.xpath(
            '//meta[@property="og:title"]/@content'
            ).extract()
        if title:
            cond_set_value(prod, 'title', title[0].capitalize())

        price = response.xpath(
            '//div[@class="sales-price-container"]'
            '/span[contains(@class, "salesprice")]/text()'
        ).extract()
        # if no sale price was found
        if not price:
            price = response.xpath(
                '//div[@class="product-price"]/span/text()'
            ).extract()
        if price and '$' in price[0]:
            n_price = price[0].strip().replace('$', '').\
                replace(',', '').strip()
            prod['price'] = Price(priceCurrency='USD', price=n_price)

        brand = response.xpath(
            '//meta[@itemprop="brand"]/@content'
        ).extract()
        cond_set(prod, 'brand', brand)

        # we need repopulate description cause at meta data it may be false
        description = response.xpath(
            '//p[@itemprop="description"]/text()'
        ).extract()
        if description:
            cond_replace_value(prod, 'description', description[0].strip())

        only_in_online_stock = response.xpath(
            '//li[@class="product-message"]'
        ).extract()
        if only_in_online_stock:
            prod['is_in_store_only'] = True
        else:
            prod['is_in_store_only'] = False

        recommendations = []
        unique_checker = []
        related_div = response.xpath(
            '//div[@id="relatedProducts"]/div[contains(@class, '
            '"recommendations")]//div[@itemprop="isRelatedTo"]'
        )
        for div in related_div:
            link = div.xpath('.//a[@itemprop="url"]/@href').extract()
            name = div.xpath('.//meta[@itemprop="name"]/@content').extract()
            if name and link:
                # because site can recommend the same items
                if name not in unique_checker:
                    unique_checker.append(name)
                    item = RelatedProduct(title=name[0].strip().capitalize(),
                                          url=link[0].strip())
                    recommendations.append(item)
        prod['related_products'] = {'recommended': recommendations}
        return prod

    def parse_product_old(self, response):
        prod = response.meta['product']
        # populate_from_open_graph not awailable cause no type=product
        metadata = _extract_open_graph_metadata(response)
        description = response.xpath('//p[@itemprop="description"]//text()').extract()
        if description:
            cond_set_value(prod, 'description', description[0])
        else:
            cond_set_value(prod, 'description', metadata.get('description'))
        cond_set_value(prod, 'title', metadata.get('title'))
        cond_replace_value(prod, 'url', metadata.get('url'))

        img_url = metadata.get('image').rstrip('?$browse_thumbnail$')
        cond_set_value(prod, 'image_url', img_url)
        locale = response.xpath(
            '//meta[@name="gwt:property"]/@content'
        ).re(r'locale=\s*(.*)')
        if locale:
            cond_set_value(prod, 'locale', locale[0])

        re_pattern = r'(\d+,\d+|\d+)'
        price = response.xpath(
            '//span[@itemprop="price"]//span[contains(@class,"price-sales")]//text()'
        ).extract()
        if not price:
            price = response.xpath('//input[contains(@name, "ProductPrice")]/@value').extract()
        if price:
            price = re.findall(r'[\d\.]+', price[0])
            if price:
                prod['price'] = Price(priceCurrency='USD', price=price[0])

        brand = response.xpath(
            '//meta[@itemprop="brand"]/@content'
        ).extract()
        cond_set(prod, 'brand', brand)
        return prod

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class, 'product-name')]"
            "//h3//a/@href").extract()
        if links:
            for link in links:
                yield link, SiteProductItem()
        else:
            self.log("Found no product links. {}".format(traceback.format_exc()), DEBUG)

    def _scrape_next_results_page_link(self, response):
        """All links was scrapped before. Not implemented
        for BaseProductsSpider in this case"""
        return None

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//*[@id="result-count"]/@value').re('\d+')
        if total_matches:
            return int(total_matches[0])

    def scrape_next_results_page(self, response):
        links = response.xpath(
            '//div[@class="pagination"]/ul/li[@class="current-page"]'
            '/following-sibling::li/a/@href'
        ).extract()
        if links and links[0]:
            return links[0]

    def scrape_links_at_the_new_site(self, response):
        """Scrape only uniqe links with color stripped"""
        links = response.xpath(
            '//div[@itemid="#product"]/div[@class="product-info"]//h2/a/@href'
        ).extract()
        color_ext = r"\?dwvar_color=.*"
        stripped_links = [re.sub(color_ext, '', link) for link in links]
        for link in stripped_links:
            if link not in self.links:
                self.links.append(link)

    def count_products(self, response):
        self.initial_responses.append(response)
        self.scrape_links_at_the_new_site(response)
        next_link = self.scrape_next_results_page(response)
        if next_link:
            return Request(next_link, callback=self.count_products)
        else:
            for resp in self.initial_responses:
                return self.parse(resp)
