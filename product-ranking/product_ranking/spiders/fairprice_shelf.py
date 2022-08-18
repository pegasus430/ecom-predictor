# -*- coding: utf-8 -*-

from .fairprice import FairPriceProductsSpider
from scrapy.http import Request
import re


class FairPriceShelfPagesSpider(FairPriceProductsSpider):
    name = 'fairprice_shelf_urls_products'
    allowed_domains = ['fairprice.com.sg']

    CATEGORY_URL = 'https://www.fairprice.com.sg/ProductListingView?top_category2=&top_category3=&' \
                   'facet=&searchTermScope=&top_category4=&top_category5=&' \
                   'searchType=&filterFacet=&' \
                   'resultCatEntryType=&' \
                   'sType=SimpleSearch&' \
                   'top_category=&gridPosition=&' \
                   'ddkey=ProductListingView_6_-2011_3074457345618269512&metaData=&' \
                   'ajaxStoreImageDir=%2Fwcsstore%2FFairpriceStorefrontAssetStore%2F&' \
                   'advancedSearch=&categoryId={category_id}&categoryFacetHierarchyPath=&' \
                   'searchTerm=&emsName=Widget_CatalogEntryList_701_3074457345618269512&' \
                   'filterTerm=&manufacturer=&resultsPerPage=24&' \
                   'disableProductCompare=false&parent_category_rn=&' \
                   'catalogId=10201&langId=-1&enableSKUListView=false&storeId={store}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(FairPriceShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        yield Request(
            self.product_url,
            meta={'search_term': "", 'remaining': self.quantity}
        )

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        if current_page >= self.num_pages:
            return
        url = re.search("SearchBasedNavigationDisplayJS\.init\('.*?','(https://www\.fairprice\.com\.sg/.*?)',", response.body)
        request = super(FairPriceShelfPagesSpider, self)._scrape_next_results_page_link(response)
        if request and url:
            return request.replace(url=url.group(1))
