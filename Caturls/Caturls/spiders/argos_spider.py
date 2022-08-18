import re

from scrapy.contrib.linkextractors import LinkExtractor
from scrapy import Request

from Caturls.spiders.caturls_spider import CaturlsSpider
from Caturls.items import ProductItem


class ArgosSpider(CaturlsSpider):
    name = 'argos'
    allowed_domains = ["argos.co.uk"]

    #region Selectors
    _xpath_category_links = '//ul[@id="categoryList"]/li'
    _xpath_department_links = '//ul[@id="primary"]/li'
    _xpath_product_links = '//*[contains(@class,"product")]/*[@class="title"]'
    #endregion

    def parse(self, response):
        category = response.meta.get('category')
        if category is None:
            breadcrumbs = response.css('#breadcrumb ul li::text').extract()
            if breadcrumbs:
                category = breadcrumbs[-1].strip(u'>\xa0')

        subcategories = self._scrape_subcategory_links(response)
        if subcategories:
            for link in subcategories:
                category_text = re.search('(.+?) \(\d+\)', link.text)
                category_text = category_text.groups()[0] if category_text else link.text
                yield Request(link.url, meta={'category': category_text})
        elif response.css('#breadcrumb'):
            for link in self._scrape_product_links(response):
                print ProductItem(product_url=link.url, category=category)
                yield ProductItem(product_url=link.url, category=category)
            next_link = response.xpath('//a[@rel="next"]/@href')
            if next_link:
                yield Request(next_link.extract()[0], meta={'category': category})
        else:
            for link in self._scrape_department_links(response):
                yield Request(link.url, meta={'category': link.text.strip()})

    def _scrape_department_links(self, response):
        return LinkExtractor(restrict_xpaths=self._xpath_department_links).extract_links(response)

    def _scrape_subcategory_links(self, response):
        return LinkExtractor(restrict_xpaths=self._xpath_category_links).extract_links(response)

    def _scrape_product_links(self, response):
        return LinkExtractor(restrict_xpaths=self._xpath_product_links).extract_links(response)
