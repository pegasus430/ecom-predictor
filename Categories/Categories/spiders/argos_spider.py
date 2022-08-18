import re

from scrapy import Request
from scrapy.spider import BaseSpider
from scrapy.contrib.linkextractors import LinkExtractor

from Categories.items import CategoryItem
from spiders_utils import Utils


#region Helper functions
def first(iterable):
    return next(iter(iterable), None)


def re_find(regexp, string_, group_no=None):
    print regexp, string_
    if string_ is None:
        return None
    match = re.search(regexp, string_)
    if match:
        return match.group() if group_no is None else match.groups()[group_no]


#endregion

class ArgosSpider(BaseSpider):
    name = 'argos'
    allowed_domains = ["argos.co.uk"]
    start_urls = ["http://www.argos.co.uk/static/Home.htm"]

    #region Selectors
    _xpath_category_links = '//ul[@id="categoryList"]/li'
    _xpath_department_links = '//ul[@id="primary"]/li'
    _xpath_description_text = '//meta[@name="description"]/@content'
    _css_product_numbers_text = '.productNumbers::text'
    _xpath_keywords = '//meta[@name="keywords"]/@content'
    #endregion

    def __init__(self, *args, **kwargs):
        super(ArgosSpider, self).__init__(*args, **kwargs)
        self._catid = 0

    def _get_catid(self):
        self._catid += 1
        return self._catid

    def parse(self, response):
        dpt_links = LinkExtractor(restrict_xpaths=self._xpath_department_links)
        for link in dpt_links.extract_links(response):
            category = CategoryItem(text=link.text.strip(' \t\n'))
            yield Request(link.url, callback=self._parse_category, meta={'category': category, 'department': category})

    def _parse_category(self, response):
        category = response.meta['category']
        parent = response.meta.get('parent', {})
        category['catid'] = self._get_catid()
        category['url'] = response.url
        category['parent_text'] = parent.get('text')
        category['parent_url'] = parent.get('url')
        category['parent_catid'] = parent.get('catid')
        category['grandparent_text'] = parent.get('parent_text')
        category['grandparent_url'] = parent.get('parent_url')
        category['level'] = parent.get('level', 0) + 1
        category['department_text'] = response.meta['department']['text']
        category['department_url'] = response.meta['department']['url']
        category['department_id'] = response.meta['department']['catid']
        #category['description_text'] = self._description_text.first(response)
        description_text = first(response.xpath(self._xpath_description_text).extract())
        if description_text:
            category['description_wc'] = len(Utils.normalize_text(description_text))
        keywords = first(response.xpath(self._xpath_keywords).extract())
        if description_text:
            category['description_text'] = description_text
        if description_text and keywords:
            (category['keyword_count'], category['keyword_density']) = Utils.phrases_freq(keywords, description_text)
        if category.get('nr_products') is None:
            nr_products = re_find('\d+', first(response.css(self._css_product_numbers_text).extract()))
            category['nr_products'] = int(nr_products) if nr_products is not None else None
        subcategory_links = LinkExtractor(restrict_xpaths=self._xpath_category_links)
        for link in subcategory_links.extract_links(response):
            text, nr_products = re.search('(.+?) \((\d+)\) *', link.text).groups()
            nr_products = int(nr_products)
            child = CategoryItem(text=text, nr_products=nr_products)
            meta = {'category': child, 'department': response.meta['department'], 'parent': category}
            yield Request(link.url, callback=self._parse_category, meta=meta)
        yield category