import re
import urlparse

from product_ranking.utils import extract_first

from .sainsburys_uk import SainsburysProductsSpider


class SainsburysMobileProductsSpider(SainsburysProductsSpider):
    name = 'sainsburys_uk_mobile_products'

    SEARCH_URL = "http://www.sainsburys.co.uk/shop/webapp/wcs/stores/servlet/AjaxApplyFilterSearchResultView?" \
                 "langId=44&storeId=10151&catalogId=10123&categoryId=&parent_category_rn=&top_category=&pageSize=36&orderBy=" \
                 "%5BLjava.lang.String%3B%404b114b11&searchTerm={search_term}&beginIndex={product_index}&categoryFacetId1=&requesttype=ajax"

    def __init__(self, *args, **kwargs):
        super(SainsburysMobileProductsSpider, self).__init__(*args, **kwargs)
        self.user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 6_0 like Mac OS X) AppleWebKit/536.26 " \
                          "(KHTML, like Gecko) Version/6.0 Mobile/10A5376e Safari/8536.25"

    def _scrape_total_matches(self, response):
        total_matches = re.search(
            'We found (\d+) products', response.body_as_unicode(), re.DOTALL
        )
        if total_matches:
            return int(total_matches.group(1))
        else:
            self.log('Can not extract total matches value')
            return 0

    def _parse_title(self, response):
        title = super(SainsburysMobileProductsSpider, self)._parse_title(response)
        if not title:
            title = extract_first(response.xpath('//div[@class="productInfo"]/h1/text()'))
        return title

    def _parse_image_url(self, response):
        image_url = super(SainsburysMobileProductsSpider, self)._parse_image_url(response)
        if not image_url:
            image_url = extract_first(response.xpath('//div[@class="productInfo"]/img/@src'))
        if image_url:
            image_url = urlparse.urljoin(response.url, image_url)
        return image_url

    def _parse_description(self, response):
        description = super(SainsburysMobileProductsSpider, self)._parse_description(response)
        if not description:
            description = extract_first(
                response.xpath('//*[@id="mainPart"]/node()[not(@class="access")][normalize-space()]')
            )
        return description
