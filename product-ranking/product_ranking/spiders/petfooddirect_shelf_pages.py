from __future__ import division, absolute_import, unicode_literals
from product_ranking.items import SiteProductItem
from product_ranking.pet_base_class import PetBaseProductsSpider
from scrapy.http import Request

class PetfooddirectShelfSpider(PetBaseProductsSpider):
    name = 'petfooddirect_shelf_urls_products'
    allowed_domains = ['petfooddirect.com']
    handle_httpstatus_list = [404]

    def __init__(self, *args, **kwargs):
        self.quantity = 99999
        self.current_page = 1
        self.product_url = kwargs['product_url']
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.search_term = ''
        super(PetfooddirectShelfSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        if self.product_url:
            yield Request(
                self.url_formatter.format(
                    self.product_url,
                    search_term='',
                ),
                meta={'search_term': '', 'remaining': self.quantity},
            )


    def _scrape_product_links(self, response):
        item_urls = response.css(
            '.item .sli_grid_title  > a::attr("href")').extract()
        shelf_categories = [c.strip() for c in response.xpath('.//*[@id="breadcrumbs"]//li/*[1]/text()').extract()
                            if len(c.strip()) > 1 and not "PetFoodDirect.com" in c]
        #TODO maybe remove filter for first bradcrumb with website name?
        shelf_category = shelf_categories[-1] if shelf_categories else None
        for item_url in item_urls:
            item = SiteProductItem()
            if shelf_category:
                item['shelf_name'] = shelf_category
            if shelf_categories:
                item['shelf_path'] = shelf_categories
            yield item_url, item

    def _scrape_next_results_page_link(self, response):
        if self.current_page >= int(self.num_pages):
            return None
        else:
            self.current_page += 1
            next = response.xpath('//a[@title="Next"]/@href').extract()
            return next[0] if next else None

    def _scrape_total_matches(self, response):
        shelf_categories = [c.strip() for c in response.xpath('.//*[@id="breadcrumbs"]//li/*[1]/text()').extract()
                            if len(c.strip()) > 1 and not "PetFoodDirect.com" in c]

        shelf_category = shelf_categories[-1] if shelf_categories else None
        matches_xpath = './/a[text()="{}"]/span[@class="count"]/text()'.format(shelf_category)
        total_matches = response.xpath(matches_xpath).extract()
        total_matches = int(total_matches[0].strip().strip('()')) if total_matches else 0
        return total_matches
