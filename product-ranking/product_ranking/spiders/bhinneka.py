import re

from scrapy import FormRequest

from product_ranking.items import Price
from contrib.product_spider import ProductsSpider
from product_ranking.spiders import cond_set, cond_set_value
from product_ranking.spiders import cond_replace, cond_replace_value


class BhinnekaProductsSpider(ProductsSpider):
    name = 'bhinneka_products'

    allowed_domains = [
        'bhinneka.com'
    ]

    SEARCH_URL = "http://www.bhinneka.com/search.aspx?Search={search_term}"

    SORT_MODES = {
        'default': '',
        'relevance': '',
        'brand': "Brand",
        'brand_desc': "Brand desc",
        'price_asc': "Price",
        'price_desc': "Price desc",
        'rating': "Rating",
        'rating_desc': "Rating desc"
    }

    HARDCODED_FIELDS = {
        'locale': 'in_ID'  # Not sure about this
    }

    MODEL_REGEXP = re.compile('\[(.+?)\] *\Z')

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse(self, response):
        if self.sort_mode and not response.meta.get('sort_forced', False):
            formdata = {"ctl00$content$ddlProductListSort": self.sort_mode,
                        "__EVENTTARGET": "ctl00$content$ddlProductListSort"}
            self._post_set_viewstate(formdata, response)
            meta = response.meta.copy()
            meta['sort_forced'] = True
            yield FormRequest(response.url, formdata=formdata, meta=meta,
                              dont_filter=True)
        else:
            for item in super(BhinnekaProductsSpider, self).parse(response):
                yield item

    def _total_matches_from_html(self, response):
        total = response.css('#ctl00_content_h1ProductHeader::text').extract()
        if total:
            total = re.search('\d+', total[0])
        return int(total.group()) if total else 0

    def _fetch_product_boxes(self, response):
        return response.css('.prod-itm')

    def _link_from_box(self, box):
        return box.css('.prod-itm-link::attr(href)').extract()[0]

    def _populate_from_box(self, response, box, product):
        cond_set(product, 'title',
                 box.css('.prod-itm-fullname::text').extract())
        xpath = './/*[@class="prod-itm-description"]' \
                '/node()[normalize-space(/)]'
        cond_set_value(product, 'description', box.xpath(xpath).extract(),
                       ''.join)
        cond_set(product, 'price', box.css('.prod-itm-price::text').extract())
        if product.get('price', '') and not isinstance(product['price'], Price):
            if not 'Rp' in product['price']:
                self.log('Unrecognized currency at %s' % response.url)
            else:
                price = product["price"].lower().replace(
                        'rp', '').replace(',', '').strip()
                if re.match("\d+", price):
                    product['price'] = Price(
                        price=price,
                        priceCurrency='IDR'
                    )
                else:
                    product["price"] = None
        cond_set(product, 'image_url',
                 box.css('.prod-itm-link img::attr(src)').extract())

    def _populate_from_html(self, response, product):
        reseller_id = re.findall('\/sku(\d+)', response.url)
        # reseller_id = reseller_id[0] if reseller_id else None
        cond_set(product, 'reseller_id', reseller_id)
        cond_set(product, 'title',
                 response.css('[itemprop=name]::text').extract())
        cond_set(product, 'brand',
                 response.css('#ctl00_content_lnkBrand::text').extract())
        cond_set(product, 'price',
                 response.css('[itemprop=price]::text').extract())
        if product.get('price', '') and not isinstance(product['price'], Price):
            if not 'Rp' in product['price']:
                self.log('Unrecognized currency at %s' % response.url)
            else:
                product['price'] = Price(
                    price=product['price'].lower().replace(
                        'rp', '').replace(',', '').strip(),
                    priceCurrency='IDR'
                )
        cond_replace(product, 'image_url',
                     response.css('#prodMedia img::attr(src)').extract())
        specs = response.css('.spesifications').extract()
        specs = specs[0] if specs else ''
        description = product.get('description', '') + specs.strip()
        cond_replace_value(product, 'description', description)
        self._get_model_from_title(product)

    def _post_set_page(self, formdata, page):
        str_ = "ctl00$content$listViewItemsPager$pager%i$lbNumericPager" % page
        formdata['__EVENTTARGET'] = str_

    def _post_set_viewstate(self, formdata, response):
        css = "#__VIEWSTATE::attr(value)"
        formdata['__VIEWSTATE'] = response.css(css).extract()[0]

    def _post_set_sort_mode(self, formdata):
        if self.sort_mode:
            formdata["ctl00$content$ddlProductListSort"] = self.sort_mode

    def _get_current_page(self, response):
        page = response.css('.prod-result-paging-selected::text').extract()
        return int(page[0]) if page else None

    def _get_pages(self, response):
        last = response.css('#ctl00_content_listViewItemsPager_pagerLast_'
                            'lbNumericPager::text').extract()
        if last and last[0].isdigit():
            return int(last[0])
        else:
            return self._get_current_page(response)

    def _scrape_next_results_page_link(self, response):
        current = self._get_current_page(response)
        if current is None:
            return None
        is_not_last = response.css(
            '#ctl00_content_listViewItemsPager_pagerNext_lbNext')
        if is_not_last:
            formdata = {}
            self._post_set_page(formdata, current)
            self._post_set_sort_mode(formdata)
            self._post_set_viewstate(formdata, response)
            return FormRequest(response.url, formdata=formdata,
                               dont_filter=True, meta=response.meta)



