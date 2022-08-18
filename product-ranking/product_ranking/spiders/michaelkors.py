import re
from urlparse import urljoin

from scrapy.contrib.linkextractors import LinkExtractor

from product_ranking.items import RelatedProduct, Price
from product_ranking.spiders import cond_set, \
    _populate_from_open_graph_product, \
    cond_set_value
from product_ranking.spiders.contrib.product_spider import ProductsSpider


class MichaelKorsProductsSpider(ProductsSpider):
    """ michaelkors.com product ranking spider.

    Spider takes `order` argument with following possible values:

    * `relevance` (default), `price_asc`, `price_desc`

    Following fields are not scraped:

    * `is_out_of_stock`, `is_in_store_only`, `buyer_reviews`, `upc`
    """

    name = 'michaelkors_products'

    allowed_domains = [
        'michaelkors.com'
    ]

    SEARCH_URL = "http://www.michaelkors.com/search/_/N-0/Ntt-{search_term}" \
                 "?Ns={sort_mode}&No={start}"

    SORT_MODES = {
        'default': '',
        'relevance': '',
        'price_desc': 'highestPriceRange|1',
        'price_asc': 'lowestPriceRange|0'
    }

    HARDCODED_FIELDS = {
        'locale': 'en-US',
        'brand': 'Michael Kors'
    }

    def __init__(self, *args, **kwargs):
        super(MichaelKorsProductsSpider, self).__init__(*args, **kwargs)
        self.url_formatter.defaults['start'] = 0

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _total_matches_from_html(self, response):
        total = response.css('#displayResultMsg span::text')
        if not total:
            total = response.css("div.search_result_msg p span::text")
        if not total:
            return 0
        total = total[0].extract()
        return int(total) if total.isdigit() else 0

    def _scrape_next_results_page_link(self, response):
        rpp = response.meta.get('results_per_page')
        prods_here = len(list(self._fetch_product_boxes(response)))
        if rpp is not None and prods_here < rpp:
            return None
        if rpp is None:
            rpp = prods_here
        start = int(re.search('\&No=(\d+)', response.url).group(1))
        search_term = response.meta['search_term']
        return self.url_formatter.format(self.SEARCH_URL,
                                         search_term=search_term,
                                         start=start + rpp)


    def _fetch_product_boxes(self, response):
        return response.css('#categoryList li') or \
            response.css('li.product_panel_medium')

    def _link_from_box(self, box):
        return box.css('a::attr(href)')[0].extract()

    def _populate_from_html(self, response, product):
        _populate_from_open_graph_product(response, product)
        cont = '#productDetailsLeftSidebar .inner-container '
        cond_set(product, 'title', response.css(cont + 'h1::text').extract(),
                 unicode.strip)
        if not product.get("title"):
            title = response.xpath(
                "//h1[contains(@class, 'prod_name')]/text()").extract()
            if title:
                cond_set(product, 'title', title, unicode.strip)

        regex = "\/_\/([^?$\s]+)"
        reseller_id = re.findall(regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, "reseller_id", reseller_id)

        price = response.xpath(
            '//div[@id="productPrice"]' \
            '/div[contains(@class, "display_price")]/input/@value |'
            '//div[@id="productPrice"]/span[last()]/text()'
        ).extract()
        if price:
            price = price[0].replace("$", "").strip()
            product["price"] = Price(priceCurrency='USD', price=price)

        model = response.css('#storeStyleNumber::text').extract()
        if model:
            model = re.search(r'Store Style #:\xa0(.+)', model[0])
            cond_set_value(product, 'model', model,
                           lambda model: model.group(1))
        self._populate_related_products(response, product)

        self._populate_hardcoded_fields(product)

    def _populate_related_products(self, response, product):
        xpath = '//ul[contains(@class, "might_like")]/li/' \
            'div[contains(@class, "product_description")]/a'
        extractor = LinkExtractor(restrict_xpaths=xpath)
        products = [RelatedProduct(url=urljoin(response.url, link.url),
                                   title=link.text.strip()) for link in
                    extractor.extract_links(response)]
        cond_set_value(product, 'related_products', {'You might also like':
                                                         products})
