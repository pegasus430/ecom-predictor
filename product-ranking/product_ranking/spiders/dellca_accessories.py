import re
import string
import traceback
import urllib
import urlparse
import json

from scrapy.http import Request

from product_ranking.items import Price, SiteProductItem, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, cond_set_value, FLOATING_POINT_RGEX, FormatterWithDefaults
from product_ranking.guess_brand import guess_brand_from_first_words


class DellCaAccessoriesProductSpider(BaseProductsSpider):
    name = 'dellca_accessories_products'
    allowed_domains = ['dell.com']

    SEARCH_URL = "http://www.dell.com/csbapi/en-ca/search?categoryPath=&q={search_term}&sortby=&" \
                 "page={page}&appliedRefinements="

    REVIEW_REGEX = '\d\.?\d*'

    def __init__(self, *args, **kwargs):
        super(DellCaAccessoriesProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page=1),
            site_name=self.allowed_domains[0],
            *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse department
        department = self._parse_department(response)
        cond_set_value(product, 'department', department, conv=string.strip)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse reseller_id
        reseller_id = self._parse_reseller_id(response)
        cond_set_value(product, 'reseller_id', reseller_id, conv=string.strip)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        # Parse stock status
        out_of_stock = self._parse_is_out_of_stock(response)
        cond_set_value(product, 'is_out_of_stock', out_of_stock)

        # set locale
        cond_set_value(product, 'locale', "en-CA")

        ratings = response.xpath('//*[@id="productDetailsTopRatings"]//span/text()').re(r'(\d+) Reviews')
        average_rating = response.xpath('//*[@id="productDetailsTopRatings"]'
                                        '//ratings/@value').re(self.REVIEW_REGEX)

        ratings = int(ratings[0]) if ratings else 0
        average_rating = float(average_rating[0]) if average_rating else 0.00
        buyer_reviews = BuyerReviews(
            num_of_reviews = ratings,
            average_rating = average_rating,
            rating_by_star = None,
        )
        cond_set_value(product, 'buyer_reviews', buyer_reviews)

        return product

    def start_requests(self):
        for request in super(DellCaAccessoriesProductSpider, self).start_requests():
            if not self.product_url:
                st = request.meta.get('search_term')
                url = self.url_formatter.format(
                    self.SEARCH_URL,
                    search_term=urllib.quote(st.encode('utf-8').replace(' ', '+')),
                )
                request = request.replace(url=url)
            yield request

    def _get_products(self, response):
        for req in super(DellCaAccessoriesProductSpider, self)._get_products(response):
            if isinstance(req, Request):
                req = req.replace(dont_filter=True)
            yield req

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        total_matches = meta.get('total_matches', 0)
        results_per_page = meta.get('results_per_page')
        current_page = meta.get('current_page', 1)
        if not results_per_page:
            results_per_page = 12
        if total_matches and results_per_page and current_page * results_per_page <= total_matches:
            current_page += 1
            meta['current_page'] = current_page
            next_link = self.SEARCH_URL.format(search_term=meta['search_term'],
                                               page=current_page)
            return Request(
                url=next_link,
                meta=meta,
                dont_filter=True
            )

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            total = int(data['AnavFilterModel']['TotalResultCount'])
        except Exception:
            self.log("Exception converting total_matches to int: {}".format(traceback.format_exc()))
            total = 0
        return total

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        data = {}
        try:
            data = json.loads(response.body_as_unicode())
        except:
            self.log("Found no product links in {url}: {error}".format(url=response.url, error=traceback.format_exc()))

        for result in data.get('AnavFilterModel', {}).get('Results', {}).get('Stacks', []):
            product_obj = result.get('Stack', '')
            if 'Links' in product_obj:
                product = self._parse_product_from_json(product_obj)
                cond_set_value(product, 'url', urlparse.urljoin(response.url, product_obj.get('Links', {})
                                                                .get('ViewDetailsLink', {}).get('Url')))
                yield None, product

    @staticmethod
    def _parse_product_from_json(data):
        product = SiteProductItem()
        cond_set_value(product, 'title', data.get('Title', {}).get('InnerValue'))
        cond_set_value(product, 'brand', data.get('MicroFormat', {}).get('Brand'))
        cond_set_value(product, 'price', Price(
            price=data.get('Pricing', {}).get('MarketValue', {}).get('InnerValue'),
            priceCurrency='CAD'
        ))
        cond_set_value(product, 'image_url', data.get('ProductImage', {}).get('ImageUri'))
        cond_set_value(product, 'is_out_of_stock', data.get('ProductOutOfStock', False))
        cond_set_value(product, 'buyer_reviews', BuyerReviews(
            num_of_reviews=data.get('RatingSubStack', {}).get('RatingCount'),
            average_rating=data.get('RatingSubStack', {}).get('RatingValue'),
            rating_by_star={},
        ))
        cond_set_value(product, 'categories', [
            data.get('CategoryInfo', {}).get('TopLevelCategoryName'),
            data.get('CategoryInfo', {}).get('Name')
        ])
        cond_set_value(product, 'department', data.get('CategoryInfo', {}).get('Name'))
        return product

    @staticmethod
    def _parse_title(response):
        title = response.xpath('//*[@id="page-title"]//h1[@id="sharedPdPageProductTitle"]/text()').extract()
        return title[0] if title else None

    @staticmethod
    def _parse_brand(response):
        brand = response.xpath('//*[@data-testid="manufacturerName"]/text()').extract()
        return brand[0] if brand else None

    @staticmethod
    def _parse_categories(response):
        categories = response.xpath('//*[@class="breadcrumb"]//a[@data-testid="sharedCrumb"]/text()').extract()
        return categories[1:] if len(categories) > 1 else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_price(self, response):
        currency = 'CAD'
        dell_price = re.search('"DellPrice":({.*?}),', response.body)
        if dell_price:
            dell_price = dell_price.group(1)
            try:
                dell_price = json.loads(dell_price)
                dell_price = dell_price.get('InnerValue')
                price = Price(price=dell_price, priceCurrency=currency)
                return price
            except:
                self.log("JSON Error {}".format(traceback.format_exc()))
                pass
        price = response.xpath('//*[contains(@name, "pricing_sale_price")]'
                               '[contains(text(), "$")]//text() | '
                               '//span[@class="pull-right"]/text() | '
                               '//span[@id="starting-price"]/text()').extract()
        if price:
            price = Price(price=price[0].strip().replace('$', ''), priceCurrency=currency)
            return price

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = response.xpath('//meta[@name="ProductId"]/@content').extract()
        return reseller_id[0] if reseller_id else None

    @staticmethod
    def _parse_image_url(response):
        image_url = response.xpath('//img[@data-testid="sharedPolarisHeroPdImage"]/@data-blzsrc').extract()
        if not image_url:
            image_url = response.xpath('//img[@data-testid="sharedPolarisHeroPdImage"]/@src').extract()

        if not image_url:
            image_url = response.xpath('//div[@id="product-detail-hero-media"]'
                                       '//ul[@class="slides"]//img/@src').extract()

        if not image_url:
            image_url = response.xpath('//*[@name="og:image"]/@content').extract()

        if image_url:
            return image_url[0]

    @staticmethod
    def _parse_is_out_of_stock(response):
        is_out_of_stock = re.search(r'"ProductOutOfStock":(.*?),', response.body)
        if is_out_of_stock:
            return is_out_of_stock.group(1) == 'true'

    @staticmethod
    def _clean_text(text):
        return re.sub("[\n\t]", "", text).strip()
