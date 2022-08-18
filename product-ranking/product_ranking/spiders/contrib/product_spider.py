import types
import urllib
import urlparse

from scrapy import Request
from scrapy.http import HtmlResponse
from scrapy.log import ERROR, DEBUG

from product_ranking.items import SiteProductItem
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, \
    cond_set_value


def option_requester(field_name):
    """Optional field request method decorator"""

    def _requester(method):
        def _wr(self, response):
            url = method(response)
            if url is None:
                response.meta['options'].remove(field_name)
                if not response.meta['options']:
                    return response.meta['product']
            elif isinstance(url, Request):
                new_meta = url.meta.copy()
                new_meta['field'] = field_name
                url.replace(meta=new_meta)
                return url
            else:
                new_meta = response.meta.copy()
                new_meta['field'] = field_name
                return Request(url,
                               callback=getattr(self, '_parse_' + field_name),
                               meta=new_meta,
                               errback=self._handle_option_error,
                               dont_filter=True)

        return _wr

    return _requester


def option_parser(method):
    """Optional field parser callback decorator.

    Returns product item when all optional fields are scraped.
    """

    def _wr(self, response):
        result = method(response)
        if result is None:
            response.meta['options'].remove(response.meta['field'])
            if not response.meta['options']:
                return response.meta['product']
        else:
            return result

    return _wr


class ProductsSpider(BaseProductsSpider):
    """Handles some common problems of product ranking spiders"""

    # Sort modes dictionary as {alias: url query value}
    SORT_MODES = {}

    # Dictionary of hardcoded SiteProductItem fields as {field: value}
    HARDCODED_FIELDS = {}

    # Optional fields that would require an additional request to be made
    # {field: boolean indicating if it should be scraped by default or not}
    OPTIONAL_REQUESTS = {}

    REQUIRE_PRODUCT_PAGE = True  # Indicates if product page must be requested

    # Compiled regular expression to search for model in a title.
    # Product title should be scraped before any optional requests.
    MODEL_REGEXP = None

    # Function to validate model.
    MODEL_VALIDATOR = lambda self, model: len(model) in range(4, 15)

    def __init__(self, order='default', *args, **kwargs):
        # Handle multiple allowed domains
        if getattr(self, 'allowed_domains', None):
            if len(self.allowed_domains) > 1 and 'site' not in kwargs:
                kwargs['site_name'] = self.allowed_domains[0]

        # Decorate optional fields request and parse methods
        # with _option_requester and _option_parser
        for key in self.OPTIONAL_REQUESTS.keys():
            method_name = '_parse_%s' % key
            old_method = getattr(self, method_name)
            new_method = types.MethodType(option_parser(old_method),
                                          self)
            setattr(self.__class__, method_name, new_method)
            method_name = '_request_%s' % key
            old_method = getattr(self, method_name)
            new_method = types.MethodType(option_requester(key)(old_method),
                                          self)
            setattr(self.__class__, method_name, new_method)

        # Creating the list of optional fields to be scraped
        self.options = [k for k, v in self.OPTIONAL_REQUESTS.iteritems() if
                        (v or kwargs.get(k, False)) and kwargs.get(k, True)]

        # Handle sort modes
        sort_mode = self.SORT_MODES.get(order, None)
        if self.SORT_MODES:
            if sort_mode is None:
                self.log('Sort mode "%s" is not defined' % order)
        self.sort_mode = sort_mode
        formatter = FormatterWithDefaults(sort_mode=sort_mode)

        super(ProductsSpider, self).__init__(formatter, *args, **kwargs)

    def parse_product(self, response):
        product = response.meta['product']
        self._populate_from_html(response, product)
        self._get_model_from_title(product)

        # Request optional fields
        if self.options:
            response.meta['options'] = set(self.options)
            for option in self.options:
                yield getattr(self, '_request_%s' % option)(response)
        else:  # No optional fields required
            yield product

    def _get_model_from_title(self, product):
        if self.MODEL_REGEXP is None:
            return
        title = product.get('title', '')
        model = self.MODEL_REGEXP.search(title)
        model = model.group(1) if model else None
        if model and self.MODEL_VALIDATOR(model):
            cond_set_value(product, 'model', model)

    def _scrape_total_matches(self, response):
        total_matches = self._total_matches_from_html(response)
        if total_matches is None:
            total_matches = self._calculate_total_matches(response)
        return total_matches

    def _total_matches_from_html(self, response):
        return None

    def _scrape_next_results_page_link(self, response):
        return None

    def _scrape_product_links(self, response):
        boxes = self._fetch_product_boxes(response)
        for box in boxes:

            # Fetch product url
            try:
                url = self._link_from_box(box)
            except IndexError:  # Most expected
                self.log('IndexError on %s' % response.url, ERROR)
                url = None
            if self.REQUIRE_PRODUCT_PAGE and url is None:
                self.log('No link found for product on %s' % response.url,
                         DEBUG)

            product = SiteProductItem()
            meta = self._populate_from_box(response, box, product)
            self._populate_hardcoded_fields(product)
            self._get_model_from_title(product)

            new_meta = response.meta.copy() if hasattr(response, 'meta') \
                else {}
            if meta and url:
                new_meta.update(meta)
            if url:
                new_meta['product'] = product
                yield Request(urlparse.urljoin(response.url, url),
                              self.parse_product, meta=new_meta,
                              errback=self._handle_product_page_error), product
            else:
                yield None, product

    def _populate_from_html(self, response, product):
        """Populate SiteProductItem from product page HTML"""
        return

    def _populate_hardcoded_fields(self, product):
        """Populate SiteProductItem with hardcoded values

        This should not be called directly, use HARDCODED_FIELDS instead.
        """
        for key, value in self.HARDCODED_FIELDS.iteritems():
            cond_set_value(product, key, value)

    def _fetch_product_boxes(self, response):
        """Fetch product boxes from search results page"""
        return

    def _link_from_box(self, box):
        """Return product link inside a box"""
        return

    def _populate_from_box(self, response, box, product):
        """Populate SiteProductItem with values scrapeable from product box on
        a search results page"""
        return

    def _get_pages(self, response):
        """Return a number of pages in search results"""
        return

    def _get_page_url(self, response, page):
        """Return url for the given page number"""
        return

    def _get_last_page_url(self, response):
        """Return url for the last page in search results"""
        return self._get_page_url(response, self._get_pages(response))

    def _calculate_total_matches(self, response):
        """Helper method to calculate total matches if scraping it failed"""
        total_pages = self._get_pages(response)
        products_here = len(list(self._scrape_product_links(response)))
        if total_pages == 1:
            return products_here
        per_page = response.meta.get('products_per_page')
        if per_page is None:
            per_page = products_here
        last_page_url = self._get_last_page_url(response)
        body = urllib.urlopen(last_page_url).read()
        lp_response = HtmlResponse(url=last_page_url, body=body,
                                   encoding=response.encoding)
        last_products = len(list(self._scrape_product_links(lp_response)))
        return (total_pages - 1) * per_page + last_products

    def _handle_option_error(self, failure):
        """Pop field name from set of processing options.

        Returns product item if no fields left to process.
        """
        self.log('Request failed: %s' % failure.request)
        failure.request.meta['options'].remove(failure.request.meta['field'])
        if not failure.request.meta['options']:
            return failure.request.meta['product']

    def _handle_product_page_error(self, failure):
        self.log('Request failed: %s' % failure.request)
        return failure.request.meta['product']
