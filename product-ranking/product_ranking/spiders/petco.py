import itertools
import re
import string
import urllib
import json
import traceback

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import cond_set_value
from product_ranking.spiders.contrib.product_spider import ProductsSpider
from scrapy import Request
from logging import WARNING


def dict_product(dicts):
    products = itertools.product(*dicts.itervalues())
    return (dict(itertools.izip(dicts, x)) for x in products)


class QueryType:
    NOT_DETERMINED = 0
    SIMPLE_BEGINING = 1
    SIMPLE_IN_PROGRESS = 2
    BRAND_BEGINING = 3
    BRAND_IN_PROGRESS = 4


class PetcoProductsSpider(ProductsSpider):
    name = 'petco_products'
    allowed_domains = ['petco.com']

    SEARCH_URL = ("https://www.petco.com/shop/SearchDisplay?categoryId=&storeId"
                  "=10151&catalogId=10051&langId=-1&sType=SimpleSearch&"
                  "resultCatEntryType=2&showResultsPage=true&searchSource=Q&"
                  "pageView=&beginIndex=0&pageSize=24&fromPageValue=search"
                  "&searchTerm={search_term}")

    SEARCH_URL_2 = ("https://www.petco.com/shop/ProductListingView?searchType="
                    "12&filterTerm=&langId=-1&advancedSearch=&sType=SimpleSearch&resultCatEntryType="
                    "2&catalogId=10051&searchTerm={search_term}&resultsPerPage=24&emsName="
                    "&facet=&categoryId={category_id}&storeId=10151&beginIndex={begin_index}")

    BRAND_URL = ("https://www.petco.com/shop/ProductListingView?searchType="
                 "12&sType=SimpleSearch&brandSearch={search_term}&beginIndex="
                 "{begin_index}&resultsPerPage={results_per_page}&storeId=10151")

    REVIEW_URL = ("http://api.bazaarvoice.com/data/products.json?"
                  "passkey=dpaqzblnfzrludzy2s7v27ehz&apiversion=5.5"
                  "&filter=id:{product_id}&stats=reviews")

    PRICE_URL = "https://www.petco.com/shop/GetCatalogEntryDetailsByIDView"

    STOCK_URL = "https://www.petco.com/shop/en/petcostore/product/GetInventoryStatusByIDView"

    QUERY_TYPE = QueryType.NOT_DETERMINED

    TRACEBACK_LIMIT = 10

    def __init__(self, *args, **kwargs):
        super(PetcoProductsSpider, self).__init__(*args, **kwargs)
        self.br = BuyerReviewsBazaarApi(called_class=self)
        self.product_last_page = 0

    def start_requests(self):
        for request in super(PetcoProductsSpider, self).start_requests():
            yield request.replace(cookies={"enable-feo": "off"})

    def parse_buyer_reviews(self, response):
        meta = response.meta.copy()
        product = response.meta['product']
        reqs = meta.get('reqs', [])

        product['buyer_reviews'] = self.br.parse_buyer_reviews_products_json(
            response)

        if reqs:
            return self.send_next_request(reqs, response)
        else:
            return product

    def _total_matches_from_html(self, response):
        total = response.xpath(
            '//div[@class="results-page-total"]/span[@class="results-total"]').re('\d+')
        return int(total[0].replace(',', '')) if total else 0

    def _scrape_results_per_page(self, response):
        if self.QUERY_TYPE in (QueryType.SIMPLE_BEGINING, QueryType.BRAND_BEGINING):
            # parsing with normal search
            product_count_str_list = response.xpath(
                '//div[@class="results-page-total"]/span[@class="results-page"]').extract()
            if product_count_str_list:
                product_count_str = product_count_str_list[0]
            else:
                self.log("Can't find total results per page with xpath\n"
                         + ''.join(traceback.format_stack(limit=self.TRACEBACK_LIMIT)), WARNING)
                return 0
            product_count = re.search('(\d+) - (\d+)', product_count_str)
            if product_count:
                begin_product_count = int(product_count.group(1))
                end_product_count = int(product_count.group(2))
                return end_product_count - begin_product_count + 1
            else:
                self.log("Invalid regex to fetch total results\n"
                         + ''.join(traceback.format_stack(limit=self.TRACEBACK_LIMIT)), WARNING)
                return 0
        else:
            # parsing with internal api, xpath is different
            return len(response.xpath('//div[@class="product-info"]/div[@class="product-name"]').extract())

    def _scrape_next_results_page_link(self, response):
        # End of pagination
        if self.product_last_page == 0:
            return None
        num_poduct_page = self._scrape_results_per_page(response)
        st = response.meta['search_term']
        # Brand scraping, first page is
        if self.QUERY_TYPE == QueryType.BRAND_BEGINING:
            self.QUERY_TYPE = QueryType.BRAND_IN_PROGRESS
            url = self.url_formatter.format(self.BRAND_URL,
                                            search_term=urllib.quote_plus(
                                                st.encode('utf-8')),
                                            begin_index=num_poduct_page,
                                            results_per_page=num_poduct_page)
        # Brand scraping, other pages are of the same pattern
        elif self.QUERY_TYPE == QueryType.BRAND_IN_PROGRESS:
            match = re.search("beginIndex=(\d+)", response.url)
            if match:
                begin_index = int(match.group(1))
                results_per_page = int(re.search("resultsPerPage=(\d+)", response.url).group(1))
                url = self.url_formatter.format(self.BRAND_URL,
                                                search_term=urllib.quote_plus(
                                                    st.encode('utf-8')),
                                                begin_index=(begin_index + results_per_page),
                                                results_per_page=num_poduct_page)
            else:
                self.log("Can't construct next page link\n"
                         + ''.join(traceback.format_stack(limit=self.TRACEBACK_LIMIT)), WARNING)
                return None
        # Simple search, not brand
        else:
            if self.QUERY_TYPE == QueryType.SIMPLE_BEGINING:
                self.QUERY_TYPE = QueryType.SIMPLE_IN_PROGRESS
            match = re.search(r'beginIndex=(\d+)', response.url)
            if match:
                begin_index = int(match.group(1))
            else:
                begin_index = 0
            category_id = re.search(r'categoryId: \'(\d+)\'', response.body)
            if category_id:
                category_id = category_id.group(1)
            else:
                category_id = ''
            url = self.url_formatter.format(
                self.SEARCH_URL_2,
                search_term=urllib.quote_plus(
                    st.encode('utf-8')
                ),
                begin_index=(begin_index + num_poduct_page),
                category_id = category_id,
            )
        return url

    def _scrape_product_links(self, response):
        # determining whether it is a brand query or a simple one for later use
        if self.QUERY_TYPE == QueryType.NOT_DETERMINED:
            if re.search("petcostore/brand/", response.url):
                self.QUERY_TYPE = QueryType.BRAND_BEGINING
            else:
                self.QUERY_TYPE = QueryType.SIMPLE_BEGINING
        item_urls = response.xpath('//div[@class="product-display-grid product_listing_container"]'
                                   + '/div[@class="prod-tile"]/div[@class="product-info"]'
                                   + '/div[@class="product-name"]/a/@href').extract()
        self.product_last_page = len(item_urls)
        for item_url in item_urls:
            yield item_url, SiteProductItem()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _parse_title(self, response):
        title = response.xpath('//h1/text()').extract()
        return title[0].strip() if title else None

    def _parse_categories(self, response):
        categories = response.css('.breadcrumb a::text').extract()
        return categories if categories else None

    def _parse_category(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_image_url(self, response):
        image_url = response.xpath(
            '//*[@property="og:image"]/@content').extract()
        return image_url[0] if image_url else None

    def _parse_brand(self, response):
        brand = response.xpath(
            '//*[@itemprop="brand"]/span/text()').extract()

        return brand[0] if brand else None

    def _parse_sku(self, response):
        sku = response.xpath("//span[@itemprop='sku']/text()").extract()
        if not sku:
            sku = response.css(
                '.product-sku::text').re(u'SKU:.(\d+)')
        return sku[0] if sku else None

    def _parse_variants(self, response):
        variants = []

        try:
            variants_info = json.loads(response.xpath('//*[contains(@id,"entitledItem_")]/text()').extract()[0])
        except:
            variants_info = {}

        for attr_value in variants_info:
            attributes = {}
            variant_attribute = attr_value["Attributes"]
            if not variant_attribute:
                break
            attributes['price'] = attr_value.get("RepeatDeliveryPrice", {}).get("price")
            attributes['image_url'] = attr_value.get("ItemImage")

            # extracting item weight which is stored as json key
            # in form "Item Weight_##", where ## is a number
            weight_key = attr_value['Attributes'].keys()
            if len(weight_key) == 1:
                key_and_value = weight_key[0].split('_')
                if len(key_and_value) == 2:
                    attributes[key_and_value[0]] = key_and_value[1]

            variants.append(attributes)

        return variants if variants else None

    def _parse_shipping_included(self, response):
        pass

    def _parse_description(self, response):
        description = response.xpath(
            '//*[@id="description"]').extract()

        return ''.join(description).strip() if description else None

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """

        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def parse_product(self, response):
        reqs = []
        product = response.meta['product']

        # Set locale
        product['locale'] = 'en_US'

        #Site name
        product['site'] = self.allowed_domains[0]

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse variants
        variants = self._parse_variants(response)
        cond_set_value(product, 'variants', variants)

        # Sku
        sku = self._parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Reseller_id
        cond_set_value(product, 'reseller_id', sku)

        # Brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        product_id = response.xpath(
            '//*[@id="productPartNo"]/@value').extract()

        if product_id:
            reqs.append(
                Request(
                    url=self.REVIEW_URL.format(
                        product_id=product_id[0], index=0),
                    dont_filter=True,
                    callback=self.parse_buyer_reviews,
                    meta=response.meta
                ))

        price_id = response.xpath(
            '//*[contains(@id,"entitledItem_")]/@id').re(
            'entitledItem_(\d+)')

        cat_id = response.xpath(
            '//*[@name="firstAvailableSkuCatentryId_avl"]/@value').extract()

        if not cat_id:
            cat_id = response.xpath('//script/text()').re(
                'productDisplayJS.displayAttributeInfo\("(\d+)","(\d+)"')

        if cat_id:
            text = ("storeId=10151&langId=-1&catalogId=10051&"
                    "itemId={cat}".format(cat=cat_id[0]))
            reqs.append(
                Request(self.STOCK_URL,
                        body=text,
                        headers={
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                            'referer': response.url,
                        },
                        method='POST',
                        meta=response.meta,
                        callback=self._parse_is_out_of_stock,
                        dont_filter=True)
            )
        status = response.xpath(
            '//*[@itemprop="availability" and @content="in_stock"]')
        product['is_out_of_stock'] = not bool(status)

        if price_id and cat_id:
            text = ("storeId=10151&langId=-1&catalogId=10051&"
                    "catalogEntryId={cat}&productId={prod_id}".format(cat=cat_id[0],
                                                                      prod_id=price_id[0]))
            reqs.append(
                Request(self.PRICE_URL,
                        body=text,
                        headers={
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'X-Requested-With': 'XMLHttpRequest',
                            'referer': response.url,
                        },
                        method='POST',
                        meta=response.meta,
                        callback=self._parse_price_info,
                        dont_filter=True)
            )

        else:
            prices = map(float, response.xpath(
                '//*[@class="product-price"]//span/text()').re('\$([\d\.]+)'))
            product['price'] = Price(price=min(prices), priceCurrency="USD") if prices else None

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_is_out_of_stock(self, response):
        in_stock = True
        reqs = response.meta.get('reqs', [])
        product = response.meta['product']
        try:
            raw_information = re.findall(
                '\{.*\}', response.body, re.MULTILINE | re.DOTALL)[0]

            status = re.search('status:(.*?),', self._clean_text(raw_information))
            if status:
                status = status.group(1).replace('\"', '').strip()
                if status != 'In-Stock':
                    in_stock = False
            product['is_out_of_stock'] = not bool(in_stock)
        except:
            self.log("Can't find stock status" + ''.join(traceback.format_stack(limit=self.TRACEBACK_LIMIT)), WARNING)
        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_price_info(self, response):
        reqs = response.meta.get('reqs', [])
        product = response.meta['product']
        try:
            raw_information = re.findall(
                '\{.*\}', response.body, re.MULTILINE | re.DOTALL)[0]

            product_data = eval(raw_information)

            price = product_data["catalogEntry"]["offerPrice"].replace('$', '')
            product['price'] = Price(price=price, priceCurrency="USD")

            old_price = product_data['catalogEntry']['listPrice'].replace('$', '')
            if old_price:
                was_now = ', '.join([price, old_price])
                cond_set_value(product, 'was_now', was_now)

                cond_set_value(product, 'promotions', True)
        except:
            self.log("Can't find price" + ''.join(traceback.format_stack(limit=self.TRACEBACK_LIMIT)), WARNING)
        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
