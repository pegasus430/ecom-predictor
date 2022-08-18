# -*- coding: utf-8 -*-

from .publix import PublixProductsSpider
from scrapy.http import Request, FormRequest
import re


class PublixShelfPagesSpider(PublixProductsSpider):
    name = 'publix_shelf_urls_products'
    allowed_domains = ["www.publix.com"]
    CATEGORY_URL = 'http://www.publix.com/product-catalog/productlisting?{category_id}&page={page_num}'

    def __init__(self, store='1083', *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        self.category_id = None
        self.store = store
        self.is_age_check = False
        self.cookies = None
        super(PublixShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        url = self.STORE_STRING.format(store_number=self.store)
        yield Request(
            url,
            self.get_store_string
        )

    def get_store_string(self, response):
        store_string = response.xpath('//h1[@id="content_2_TitleTag"]/text()').extract()
        if store_string:
            self.store_strong = store_string[0].strip().replace(' ', '+')
            category_id = re.findall(r'\?(.*?)&', self.product_url)
            if category_id:
                category_id = category_id[0]
                url = self.CATEGORY_URL.format(category_id=category_id, page_num=1)
                self.category_id = category_id
                self.cookies = {
                    'PublixStore': self.COOKIE.format(store_number=self.store, store_string=self.store_strong)
                }
                yield Request(url=url,
                              callback=self.check_age,
                              meta={'search_term': "", 'remaining': self.quantity},
                              cookies=self.cookies)

    def check_age(self, response):
        if 'useragepage' in response.url:
            self.is_age_check = True
            return FormRequest.from_response(
                response,
                formdata={
                    'content_0$YearsList': '1986',
                    'content_0$MonthsList': '3',
                    'content_0$DaysList': '7',
                },
                dont_filter=True,
                meta={'search_term': "", 'remaining': self.quantity},
                cookies=self.cookies
            )

        return self.parse(response)

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page')
        if not current_page:
            current_page = 1
        if current_page * response.meta['scraped_results_per_page'] >= self.total_matches or \
                        current_page >= self.num_pages:
            return
        current_page += 1
        meta['current_page'] = current_page
        url = self.CATEGORY_URL.format(page_num=current_page, category_id=self.category_id)
        if self.is_age_check:
            return Request(
                url,
                meta=meta,
                dont_filter=True,
                callback=self.check_age,
                cookies=self.cookies
            )
        return Request(
            url,
            meta=meta,
            dont_filter=True,
            cookies=self.cookies
        )
