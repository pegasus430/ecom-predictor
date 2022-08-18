# -*- coding: utf-8 -*-
import re
import traceback

from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX, FormatterWithDefaults
from product_ranking.utils import is_empty
from scrapy import Request


class FairPriceProductsSpider(BaseProductsSpider):
    name = 'fairprice_products'
    allowed_domains = ['fairprice.com.sg']

    SEARCH_URL = 'https://www.fairprice.com.sg/ProductListingView?' \
                 'top_category2=&top_category3=&facet=&searchTermScope=&top_category4=&top_category5=&' \
                 'searchType=100&filterFacet=&resultCatEntryType=&' \
                 'sType=SimpleSearch&top_category=&gridPosition=&' \
                 'ddkey=ProductListingView_6_-2011_3074457345618268103&metaData=&' \
                 'ajaxStoreImageDir=%2Fwcsstore%2FFairpriceStorefrontAssetStore%2F&advancedSearch=&' \
                 'categoryId=&categoryFacetHierarchyPath=&searchTerm={search_term}&' \
                 'emsName=Widget_CatalogEntryList_701_3074457345618268103&filterTerm=&manufacturer=&resultsPerPage=24&' \
                 'disableProductCompare=false&parent_category_rn=&catalogId=10201&langId=-1&enableSKUListView=false&storeId={store}'

    HEADERS = {
        'x-requested-with': 'XMLHttpRequest',
        'content-type': 'application/x-www-form-urlencoded'
    }

    def __init__(self, *args, **kwargs):
        self.store = kwargs.get('store', 10151)
        url_formatter = FormatterWithDefaults(store=self.store)
        super(FairPriceProductsSpider, self).__init__(
            url_formatter=url_formatter,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def start_requests(self):
        for req in super(FairPriceProductsSpider, self).start_requests():
            if not self.product_url:
                req = req.replace(
                    method='POST',
                    body=self._get_search_form(0, req.meta.get('search_term'), self.store),
                    headers=self.HEADERS
                )
            yield req

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _scrape_total_matches(self, response):
        total_matches = re.search(r'totalResultCount: (\d+)', response.body)
        return int(total_matches.group(1)) if total_matches else None

    def _scrape_next_results_page_link(self, response):
        meta = response.meta
        current_page = meta.get('current_page', 1)
        total_matches = meta.get('total_matches', 0)
        if current_page * 24 > total_matches:
            self.log('No next page')
            return
        st = meta.get('search_term', '')
        offset = current_page * 24
        current_page += 1
        meta['current_page'] = current_page
        return Request(
            response.url,
            method='POST',
            body=self._get_search_form(offset, st, self.store),
            meta=meta,
            dont_filter=True,
            headers=self.HEADERS
        )

    def _scrape_product_links(self, response):
        links = response.xpath('//div[@class="product_listing_container"]//a[contains(@id, "catalogEntry")]/@href').extract()
        if not links:
            self.log('Can not find the products on :{}'.format(response.url))
        for link in links:
            yield link, SiteProductItem()

    def parse_product(self, response):
        product = response.meta.get('product', SiteProductItem())

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        price = self._parse_price(response)
        price_currency = self._parse_currency(response)
        try:
            cond_set_value(product, 'price', Price(price=float(price.replace(',', '')), priceCurrency=price_currency))
        except:
            self.log('Error Parsing Price: {}'.format(traceback.format_exc()))

        was_now = self._parse_was_now(response)
        cond_set_value(product, 'was_now', was_now)

        buy_for = self._parse_buy_for(response)
        cond_set_value(product, 'buy_for', buy_for)

        buy_save_amount = self._parse_buy_save_amount(response)
        cond_set_value(product, 'buy_save_amount', buy_save_amount)

        cond_set_value(product, 'promotions', any([was_now, buy_for, buy_save_amount]))

        image_url = self._parse_image(response)
        cond_set_value(product, 'image_url', image_url)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        if categories:
            cond_set_value(product, 'department', categories[-1])

        store = self._parse_store(response)
        cond_set_value(product, 'store', store)

        is_out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//h1[@class="pdt_Pname"]/text()').extract()
        return title[0].strip() if title else None

    @staticmethod
    def _parse_brand(response):
        return is_empty(response.xpath('//div[@class="pdt_brand_name"]/text()').extract())

    @staticmethod
    def _parse_price(response):
        price = is_empty(response.xpath('//span[@class="pdt_C_price"]/text()').re(FLOATING_POINT_RGEX))
        return price

    @staticmethod
    def _parse_currency(response):
        price_currency = re.search(r'"commandContextCurrency": "(.*?)"', response.body)
        return price_currency.group(1) if price_currency else 'SGD'

    def _parse_was_now(self, response):
        current_price = self._parse_price(response)
        old_price = is_empty(response.xpath('//span[@class="pdt_O_price"]/text()').re(FLOATING_POINT_RGEX))
        if all([current_price, old_price]):
            return ','.join([current_price, old_price])

    @staticmethod
    def _parse_image(response):
        image_url = response.xpath('//div[@class="pdpImgWrapper"]//img[@class="zoomthumb"]/@src').extract()
        return image_url[0] if image_url else None

    @staticmethod
    def _parse_is_out_of_stock(response):
        is_out_of_stock = is_empty(response.xpath('//button[@class="cartProdNotifyBtn"]/text()').extract())
        if is_out_of_stock:
            return 'out of stock' in is_out_of_stock.lower()
        return False

    @staticmethod
    def _parse_store(response):
        store = re.search(r'storeId=(.*?)($|&)', response.url)
        return store.group(1) if store else None

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//li[@class="prodBread" and not(position()=1)]/a/text()').extract()
        return [i.strip() for i in categories]

    @staticmethod
    def _parse_buy_for(response):
        buy_for = response.xpath('//p[@class="lblgetDetails"]/text()').re('Buy .*? (\d+)')
        return buy_for[0] if buy_for else None

    @staticmethod
    def _parse_buy_save_amount(response):
        save_amount = response.xpath('//p[@class="lblgetDetails"]/text()').re('get \$([\.\d]+)')
        return save_amount[0] if save_amount else None

    def _get_products(self, response):
        for req in super(FairPriceProductsSpider, self)._get_products(response):
            yield req.replace(dont_filter=True)

    @staticmethod
    def _get_search_form(offset, search_term, store):
        return 'contentBeginIndex=0&productBeginIndex={offset}&beginIndex={offset}&orderBy=&' \
               'facetId=&pageView=grid&resultType=products&orderByContent=&' \
               'searchTerm={search_term}&facet=&facetLimit=&minPrice=&maxPrice=&' \
               'pageSize=&loadProductsList=true&promoCategory=&' \
               'storeId={store}&catalogId=10201&langId=-1&homePageURL=%2F&commandContextCurrency=SGD&' \
               'urlPrefixForHTTPS=https%3A%2F%2Fwww.fairprice.com.sg&' \
               'urlPrefixForHTTP=http%3A%2F%2Fwww.fairprice.com.sg&wcc_integration_origin=&enableSKUListView=&' \
               'widgetPrefix=6_3074457345618268103&' \
               'pgl_widgetId=3074457345618268103&objectId=_6_-2011_3074457345618268103&requesttype=ajax'.format(
            offset=offset, search_term=search_term, store=store
        )