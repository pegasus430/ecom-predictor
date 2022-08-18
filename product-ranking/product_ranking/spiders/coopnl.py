# -*- coding: utf-8 -*-

import json
import traceback
import re
import urllib

from scrapy.log import WARNING
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value

from scrapy import Request


class CoopnlProductsSpider(BaseProductsSpider):
    name = 'coopnl_products'
    allowed_domains = ['www.coop.nl']
    SEARCH_URL = "https://www.coop.nl/zoeken?SearchTerm={search_term}"

    CATEGORY_NEXT_PAGE_URL = 'https://www.coop.nl/actions/ViewAjax-Start?PageNumber={page_num}&' \
                    'PageSize=12&SortingAttribute=&ViewType=&TargetPipeline=ViewStandardCatalog-ProductPaging' \
                    '&CategoryName={category_name}&SearchParameter=%26%40QueryTerm%3D*%26ContextCategoryUUID%26' \
                    'OnlineFlag%3D1&CatalogID=COOP&AjaxCall=true'
    NEXT_PAGE_URL = 'https://www.coop.nl/actions/ViewAjax-Start?PageNumber={page_num}&PageSize=12' \
                    '&SortingAttribute=&ViewType=&TargetPipeline=ViewParametricSearch-ProductPaging&SearchTerm={search_term}' \
                    '&SearchParameter=%26%40QueryTerm%3D{search_term}%26OnlineFlag%3D1&AjaxCall=true'

    current_page = 0

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        meta = response.meta
        total = response.xpath("//header[contains(@class, 'formfields')]"
                               "//div[contains(@class, 'altHead')]/text()").re('\d+')
        return int(total[0]) if total else meta.get('total_count')

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        st = meta.get('search_term')

        if not meta.get('total_count'):
            total_count = self._scrape_total_matches(response)
            meta['total_count'] = total_count
        if not meta.get('category_name'):
            category_name = response.xpath("//input[@name='CategoryName']/@value").extract()
            if category_name:
                meta['category_name'] = category_name[0]

        self.current_page += 1
        total_count = meta.get('total_count', 0)
        if self.current_page * 12 >= total_count:
            return
        category_name = meta.get('category_name')
        if category_name:
            next_link = self.CATEGORY_NEXT_PAGE_URL.format(page_num=self.current_page, category_name=category_name)
        else:
            next_link = self.NEXT_PAGE_URL.format(
                page_num=self.current_page,
                search_term=urllib.quote_plus(st.encode('utf-8'))
            )

        return Request(
            next_link,
            meta=meta
            )

    def _scrape_product_links(self, response):
        links = response.xpath("//header[@class='productHeader']//a/@href").extract()
        if not links:
            try:
                json_data = json.loads(response.body)
                links = [data.get('productDetailUrl') for data in json_data if len(data) > 0]
            except:
                self.log("Error while parsing product links".format(traceback.format_exc()), WARNING)
        for link in links:
            yield link, SiteProductItem()

    @staticmethod
    def _parse_title(response):
        title = response.xpath("//h1[@itemprop='name']/text()").extract()
        return title[0].strip() if title else None

    def _parse_price(self, response):
        euro = response.xpath('//ins[@class="price"]/text()').extract()
        cent = response.xpath('//ins[@class="price"]/span[@class="sup"]/text()').extract()
        if euro and cent:
            price = euro[0].replace(',', '') + '.' + cent[0]
        try:
            return Price(price=float(price), priceCurrency='EUR')
        except:
            self.log('Error while parsing price'.format(traceback.format_exc()), WARNING)

    def _parse_image(self, response):
        image = response.xpath("//meta[@property='og:image']//@content").extract()
        return image[0] if image else None

    def parse_product(self, response):
        product = response.meta.get('product', SiteProductItem())

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        if title:
            brand = guess_brand_from_first_words(title)
            cond_set_value(product, 'brand', brand)

        categories = self._parse_categories(response)
        if categories:
            department = categories[-1]
            cond_set_value(product, 'department', department)

        cond_set_value(product, 'categories', categories)

        reseller_id = self._parse_reseller_id(product.get("url"))
        cond_set_value(product, 'reseller_id', reseller_id)

        product['locale'] = "en-US"
        return product

    @staticmethod
    def _parse_reseller_id(url):
        if url:
            reseller_id = re.search(r"product/(\d+)", url)
            if reseller_id:
                return reseller_id.group(1)

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//div[@class="crumbs cf"]/ol/li//span[@itemprop="title"]/text()').extract()
        return categories[1:] if categories else None

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath("//div[contains(@class, 'stepper')]/@data-sku").extract()
        if not sku:
            sku = response.url.split('/')
        return sku[-1] if sku else None