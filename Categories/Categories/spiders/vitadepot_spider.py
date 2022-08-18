import urlparse
import re
import datetime

from scrapy.spider import BaseSpider
from scrapy import Request
from scrapy.log import msg, WARNING
from scrapy.selector.unified import SelectorList

from Categories.items import CategoryItem, ProductItem
from spiders_utils import Utils


class VitadepotBase(object):
    """Helpers for vitadepot spiders to use"""

    EXCLUDED_DEPARTMENTS = [
        "/shop-by-brand.html",
        "/shop-by-health-concern.html",
    ]

    def __init__(self, *args, **kwargs):
        self.id_counter = 0
        super(VitadepotBase, self).__init__()

    def _is_excluded(self, url):
        """Return True if url is listed in self.EXCLUDED_DEPARTMENTS"""
        scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
        return path in self.EXCLUDED_DEPARTMENTS

    def _get_id(self):
        """Return an integer spider-wise uid"""
        self.id_counter += 1
        return self.id_counter

    def _set_value(self, item, key, value, convert=lambda val: val):
        """Set item["key"] to value if value is not None"""
        if value is not None:
            item[key] = convert(value)

    def _scrape_classifications(self, response):
        """Scrape categories listed on the page.

        Returns:
           {classification: [(url, text, nr_products), ...]}

        where:
           classification - a classification name
           url - link to the category page
           text - name of category
           nr_products - number of products in that category
        """
        names = response.css('dl#narrow-by-list dt::text').extract()
        fields = response.css('dl#narrow-by-list dd')
        result = {}
        for name, field in zip(names, fields):
            this_result = []
            result[name.strip()] = this_result
            for li in field.css('ol li'):
                link = li.css('a')
                url = link.css('::attr(href)').extract()[0]
                anchor = ''.join(link.xpath('./text()|./*/text()').extract())
                match = re.search('\d+', ''.join(li.xpath('./text()').extract()))
                if match:
                    nr_products = int(match.group())
                else:
                    msg('Not found product nr for %s on %s' % (anchor or 'UNKNOWN', response.url), WARNING)
                    nr_products = 0
                this_result.append((url, anchor, nr_products))
        return result

    def _scrape_department_links(self, response):
        """Scrape all links to departments on the page, excluding urls listed in self.EXCLUDED_DEPARTMENTS"""
        top_level_links = response.css('li.level0')
        for link in top_level_links:
            url = link.css('::attr(href)').extract()[0]
            text = link.css('::text').extract()[0]
            if self._is_excluded(url):
                continue
            yield url, text


class VitadepotSpider(BaseSpider, VitadepotBase):
    name = "vitadepot"
    allowed_domains = ["vitadepot.com"]
    start_urls = ["http://vitadepot.com/"]

    def __init__(self, *args, **kwargs):
        self.id_counter = 0
        super(VitadepotSpider, self).__init__(*args, **kwargs)

    def parse(self, response):
        for url, text in self._scrape_department_links(response):
            category = CategoryItem(text=text)
            yield Request(url, callback=self._parse_category, meta={"category": category})

    def _parse_category(self, response):
        category = response.meta['category']
        self._populate_category(response)
        classifications = self._scrape_classifications(response)
        categories = classifications.pop("Shop By Category", [])
        for url, text, nr_products in categories:
            new_category = CategoryItem(text=text, nr_products=nr_products)
            yield Request(url, self._parse_category, meta={"category": new_category, "parent": category})
        if category.get('nr_products') is None:
            category['nr_products'] = sum((item[2] for item in categories))
        category['classification'] = {key: [{'name': itm[1], 'nr_products': itm[2]} for itm in value]
                                       for key,value in classifications.iteritems()}
        yield category

    def _populate_category(self, response):
        """Set html-independent fields"""
        category = response.meta['category']
        parent = response.meta.get('parent', {})
        category['url'] = response.url
        category['level'] = parent.get('level', 0) + 1
        category['catid'] = self._get_id()
        self._set_value(category, 'parent_text', parent.get('text'))
        self._set_value(category, 'parent_url', parent.get('url'))
        self._set_value(category, 'parent_catid', parent.get('catid'))
        self._set_value(category, 'grandparent_text', parent.get('parent_text'))
        self._set_value(category, 'grandparent_url', parent.get('parent_url'))
        category['department_text'] = parent.get('department_text', category['text'])
        category['department_url'] = parent.get('department_url', category['url'])
        category['department_id'] = parent.get('department_id', category['catid'])
        self._populate_from_html(response)

    def _populate_from_html(self, response):
        """Set html-dependant fields"""
        category = response.meta['category']
        #description = response.xpath('//div[@class="category-description std"]/*[not(a[@class="viewAllCats"])]')
        description = response.xpath('//div[@class="category-description std"]/node()')
        description = SelectorList(filter(lambda itm: not len(itm.css('.viewAllCats')), description))
        description = ' '.join(description.extract()) or None
        description = description.strip(' \n\r\t')
        desc_title = (response.css('.category-title h1::text').extract() or [None])[0]
        self._set_value(category, 'description_text', description)
        self._set_value(category, 'description_title', desc_title)
        tokenized = Utils.normalize_text(description) if description else []
        category['description_wc'] = len(tokenized)
        if description and desc_title:
            category['keyword_count'], category['keyword_density'] = Utils.phrases_freq(desc_title, description)



class VitadepotBestsellerSpider(BaseSpider, VitadepotBase):
    name = "vitadepot_bestseller"
    start_urls = ["http://vitadepot.com"]

    def __init__(self, *args, **kwargs):
        super(VitadepotBestsellerSpider, self).__init__(*args, **kwargs)

    def parse(self, response):
        department = response.meta.get('department')
        for rank, (url, product) in enumerate(self._scrape_product_links(response)):
            product['department'] = department
            product['rank'] = rank
            yield Request(url, self.parse_product, meta={'product': product})
        if department is None:  # This is a starting page
            for url, text in self._scrape_department_links(response):
                yield Request(url, callback=self.parse, meta={"department": text})

    def parse_product(self, response):
        product = response.meta['product']

        # Searching for SKU
        extras = response.css('.extratributes ul li span::text').extract()
        for extra in extras:
            match = re.search('SKU (#\d+)', extra)
            if match:
                product['SKU'] = match.groups()[0]
                break

        # Fill other fields in
        product['page_title'] = response.css('title::text').extract()[0].replace('\n', ' ').strip()
        product['date'] = datetime.date.today().isoformat()
        product['product_name'] = response.css('.product-name h1::text').extract()[0]
        yield product

    def _scrape_product_links(self, response):
        parent_elts = response.css('#cat_bestSellers .item')
        for parent in parent_elts:
            product = ProductItem()
            url = parent.css('.product-name a::attr(href)').extract()[0]
            product['list_name'] = parent.css('.product-name a::text').extract()[0]
            price = parent.css('.special-price .price::text')
            listprice = parent.css('.old-price .price::text')
            price = price or parent.css('.price')[0].css('::text')
            try:
                listprice = listprice or parent.css('#old-price-')[0].css('::text')
            except IndexError:
                listprice = price
            product['price'] = ''.join(price.extract()).strip()
            product['listprice'] = ''.join(listprice.extract()).strip()
            yield url, product