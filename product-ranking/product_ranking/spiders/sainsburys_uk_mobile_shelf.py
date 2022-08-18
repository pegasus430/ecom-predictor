import re
import json

from .sainsburys_uk import SainsburysProductsSpider
from scrapy.http import Request
from lxml import html
from product_ranking.items import SiteProductItem
from scrapy.log import DEBUG


class SainsburysUkMobilePagesSpider(SainsburysProductsSpider):
    name = 'sainsburys_uk_mobile_shelf_urls_products'
    allowed_domains = ['www.sainsburys.co.uk', 'sainsburysgrocery.ugc.bazaarvoice.com']
    SHELF_NEXT_URL = "http://www.sainsburys.co.uk/shop/webapp/wcs/stores/servlet/AjaxApplyFilterSearchResultView?" \
                     "langId=44&storeId=10151&catalogId=10241&categoryId={categoryId}" \
                     "&parent_category_rn={top_category}&top_category={top_category}" \
                     "&pageSize=36&orderBy={orderBy}&searchTerm=&beginIndex={product_index}&facet="

    SHELF_URL = "http://www.sainsburys.co.uk/shop/gb/groceries/dairy/AjaxApplyFilterBrowseView?" \
                "langId=44&storeId=10151&catalogId=10241&categoryId={shelf_categoryId}" \
                "&parent_category_rn={shelf_top_category}top_category={shelf_top_category}" \
                "&pageSize=36&orderBy={shelf_orderBy}&searchTerm=&beginIndex=0&requesttype=ajax"
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36'
    }


    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        super(SainsburysUkMobilePagesSpider, self).__init__(*args, **kwargs)
        self.product_index = 0
        self.product_json = None
        self.product_links_info = None
        self.categoryId = None
        self.top_category = None
        self.orderBy = None
        self.product_index_info = None

    def _setup_meta_compatibility(self):
        return {'remaining': self.quantity, 'search_term': ''}

    def start_requests(self):
        self.shelf_categoryId = re.search('categoryId=(.*?)&', self.product_url)
        if self.shelf_categoryId:
            self.shelf_categoryId = self.shelf_categoryId.group(1)

        self.shelf_top_category = re.search('top_category=(.*?)&', self.product_url)
        if self.shelf_top_category:
            self.shelf_top_category = self.shelf_top_category.group(1)

        self.shelf_orderBy = re.search('orderBy=(.*?)&', self.product_url)
        if self.shelf_orderBy:
            self.shelf_orderBy = self.shelf_orderBy.group(1)


        self.product_url = self.SHELF_URL.format(shelf_categoryId=self.shelf_categoryId, shelf_top_category=self.shelf_top_category,
                                                 shelf_orderBy=self.shelf_orderBy)
        yield Request(url=self.product_url,
                      meta=self._setup_meta_compatibility(),
                      headers=self.header)

    def _scrape_total_matches(self, response):
        json_res = json.loads(response.body_as_unicode())

        try:
            total_matches = re.search('(\d+)', json_res[0].get('pageHeading'), re.DOTALL).group(1)
            return int(total_matches)

        except Exception as e:
            self.log("Exception looking for total_matches, Exception Error: {}".format(e), DEBUG)
            return []

    def _scrape_product_links(self, response):
        self.product_links = []
        self.product_links = response.xpath("//div[@class='productNameAndPromotions']//h3//a/@href").extract()
        if not self.product_links:
            try:
                self.product_json = json.loads(response.body_as_unicode())
                for data in self.product_json:
                    if data.get('productLists', {}):
                        self.product_links_info = data['productLists'][0]['products']

                if self.product_links_info:
                    for link_info in self.product_links_info:
                        link_by_html = html.fromstring(link_info['result']).xpath('//li[@class="gridItem"]//h3/a/@href')
                        if link_by_html:
                            self.product_links.append(link_by_html[0])
            except Exception as e:
                self.log("Exception looking for total_matches, Exception Error: {}".format(e), DEBUG)
                self.product_json = None

        for link in self.product_links:
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        if not self.product_links:
            return

        self.categoryId = re.search('categoryId=(.*?)&', self.product_url)
        if self.categoryId:
            self.categoryId = self.categoryId.group(1)

        self.top_category = re.search('top_category=(.*?)&', self.product_url)
        if self.top_category:
            self.top_category = self.top_category.group(1)

        self.orderBy = re.search('orderBy=(.*?)&', self.product_url)
        if self.orderBy:
            self.orderBy = self.orderBy.group(1)

        self.product_index_info = re.search('pageSize=(.*)&', self.product_url)
        if self.product_index_info:
            self.product_index_info = re.search('\d+', self.product_index_info.group(1)).group()

        self.product_index += int(self.product_index_info)
        next_page_link = self.SHELF_NEXT_URL.format(categoryId=self.categoryId, top_category=self.top_category,
                                                    orderBy=self.orderBy, product_index=str(self.product_index))
        if next_page_link:
            return next_page_link

    def parse_product(self, response):
        return super(SainsburysUkMobilePagesSpider, self).parse_product(response)