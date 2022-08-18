from __future__ import division, absolute_import, unicode_literals
import re
import traceback
import urlparse
import json

from lxml import html
from scrapy.http import Request
from scrapy.log import WARNING

from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import cond_set_value
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.spiders.contrib.product_spider import ProductsSpider


class FreshDirectProductsSpider(ProductsSpider):
    name = "freshdirect_products"
    allowed_domains = ["freshdirect.com"]

    SEARCH_URL = "https://www.freshdirect.com/srch.jsp?pageType=search&" \
                 "searchParams={search_term}&pageSize=30&all=false&activePage={page}" \
                 "&sortBy=Sort_Relevancy&orderAsc=true&activeTab=product"

    STORE_PICK_URL = 'https://www.freshdirect.com/api/locationhandler.jsp?action=setZipCode&zipcode={}'

    current_page = 1
    results_per_page = 30

    def __init__(self, *args, **kwargs):
        self.zip_code = kwargs.get('zip_code', '10001')
        super(FreshDirectProductsSpider, self).__init__(*args, **kwargs)
        self.url_formatter.defaults['page'] = self.current_page

    def start_requests(self):
        headers = {
              'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                            '(KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36',
              ':authority': 'www.freshdirect.com',
              ':path': '/api/locationhandler.jsp?action=setZipCode&zipcode={}'.format(self.zip_code),
              ':scheme': 'https',
              'accept': '*/*',
              'accept-encoding': 'gzip, deflate, br',
              'accept-language': 'en-US,en;q=0.9',
              'x-requested-with': 'XMLHttpRequest'
        }

        yield Request(self.STORE_PICK_URL.format(self.zip_code),
                      callback=self._start_requests,
                      headers=headers
                      )

    def _start_requests(self, response):
        return super(FreshDirectProductsSpider, self).start_requests()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _populate_from_html(self, response, prod):
        reseller_id_regex = "[Pp]roduct[Ii][dD]=([^\&]+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(prod, 'reseller_id', reseller_id)

        title = self._parse_title(response)
        cond_set_value(prod, 'title', title)

        buyer_reviews = self.parse_buyer_reviews(response)
        cond_set_value(prod, 'buyer_reviews', buyer_reviews)

        image_url = self._parse_image(response)
        cond_set_value(prod, 'image_url', image_url)

        categories = self._parse_categories(response)
        cond_set_value(prod, 'categories', categories)

        department = self._parse_department(response)
        cond_set_value(prod, 'department', department)

        brand = self._parse_brand(response)
        cond_set_value(prod, 'brand', brand)

        cond_set_value(prod, 'is_out_of_stock', False)

        sku = self._parse_sku(response)
        cond_set_value(prod, 'sku', sku)

        price, old_price = self._parse_price(response)
        if price:
            cond_set_value(prod, 'price', Price(price=price, priceCurrency='USD'))
            if old_price and price != old_price:
                cond_set_value(prod, 'was_now', '{},{}'.format(price, old_price))
                cond_set_value(prod, 'promotions', True)

    def _parse_title(self, response):
        title = response.xpath("//span[@itemprop='name']/text()").extract()
        if not title:
            title = re.findall('"productName":"(.*?)"', response.body)
        return title[0] if title else None

    def _parse_brand(self, response):
        brand = re.findall(r'"brandName":"(.*?)"', response.body)
        if brand:
            brand = brand[0]
        else:
            title = self._parse_title(response)
            brand = guess_brand_from_first_words(title) if title else None

        return brand

    def _parse_image(self, response):
        image_url = response.xpath("//div[@class='main-image']//img/@src").extract()
        return urlparse.urljoin(response.url, image_url[0]) if image_url else None

    def _parse_sku(self, response):
        sku = response.xpath("//input[@name='skuCode']/@value").extract()
        return sku[0] if sku else None

    def _parse_price(self, response):
        json_data = re.search(r'window\.FreshDirect\.pdp\.data = ({.*?});', response.body)
        try:
            json_data = json.loads(json_data.group(1))
            price = json_data.get('price', 0)
            old_price = json_data.get('wasPrice', 0)
            return price, old_price
        except:
            self.log('Error parsing price: {}'.format(traceback.format_exc()), WARNING)
        return None, None

    def _parse_categories(self, response):
        categories = response.xpath("//ul[@class='breadcrumbs']//li//text()").extract()
        return categories if categories else None

    def _parse_department(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def parse_buyer_reviews(self, response):
        ZERO_REVIEWS_VALUE = {
            'num_of_reviews': 0,
            'average_rating': 0.0,
            'rating_by_star': {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        }
        buyer_reviews_info = {}
        average_rating = response.xpath("//ul[@class='ratings']//b[contains(@class,'expertrating')]//text()").extract()
        if average_rating:
            average_rating = re.search('Rating (\d+)/10', average_rating[0])

        if average_rating:
            buyer_reviews_info = {
                'average_rating': float(average_rating.group(1)) / 2.0
            }

        if buyer_reviews_info:
            return buyer_reviews_info
        else:
            self.log("Error while parsing reviews: {}".format(traceback.format_exc()))
            return BuyerReviews(**ZERO_REVIEWS_VALUE)

    def parse_product(self, response):
        prod = response.meta['product']
        prod['url'] = response.url

        self._populate_from_html(response, prod)
        cond_set_value(prod, 'locale', 'en-US')

        return prod

    def _scrape_total_matches(self, response):
        count = response.xpath("//p[@class='pagination-text']/text()").re('of\s*(\d+)')
        return int(count[0]) if count else 0

    def _scrape_product_links(self, response):
        products_content = None
        st = response.meta.get('search_term')
        section_content = response.xpath('//div[contains(@class, "sectionContent")]').extract()
        related_items = response.xpath('//div[contains(@class, "sectionContent")]//ul[@class="relatedItem"]').extract()
        if section_content:
            products_content = ''.join(section_content)
            for related_item in related_items:
                products_content = products_content.replace(related_item, '')

        links = []
        if products_content:
            links = html.fromstring(products_content).xpath('//ul[contains(@class, "products")]'
                                                            '/li[contains(@class, "portrait-item")]/a/@href')
        for link in links:
            link = urlparse.urljoin(response.url, link)
            prod_item = SiteProductItem()
            req = Request(
                url=link,
                callback=self.parse_product,
                meta={
                    'product': prod_item,
                    'search_term': st,
                    'remaining': self.quantity,
                },
                dont_filter=True
            )
            yield req, prod_item

    def _scrape_next_results_page_link(self, response):
        st = response.meta.get('search_term')
        if self.current_page * self.results_per_page >= self._scrape_total_matches(response):
            return
        self.current_page += 1

        next_link = self.SEARCH_URL.format(search_term=st, page=self.current_page)
        if next_link:
            return next_link

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()
