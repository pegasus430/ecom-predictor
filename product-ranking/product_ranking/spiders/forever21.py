import json
import re
import string
import urllib

from scrapy import Request, Selector
from scrapy.conf import settings

from product_ranking.items import SiteProductItem, BuyerReviews, Price
from product_ranking.spiders import cond_set_value
from product_ranking.spiders.contrib.product_spider import ProductsSpider


class Forever21ProductsSpider(ProductsSpider):
    name = 'forever21_products'

    allowed_domains = ['forever21.com', 'brsrvr.com', 'powerreviews.com']

    SEARCH_URL = 'http://brm-core-0.brsrvr.com/api/v1/core/?account_id=5079&' \
                 'auth_key=d1qiei07nwrrdicq&'\
                 'domain_key=forever21_us_com&'\
                 'request_id=4921257385345&'\
                 'url=http://\www.forever21.com&'\
                 'ref_url=&'\
                 'request_type=search&'\
                 'rows=60&'\
                 'start=1&'\
                 'l={search_term}&'\
                 'q={search_term}&'\
                 'search_type=keyword'\

    NEXT_PAGE_URL = 'http://brm-core-0.brsrvr.com/api/v1/core/'\
                    '?account_id=5079&' \
                    'auth_key=d1qiei07nwrrdicq&'\
                    'domain_key=forever21_us_com&'\
                    'request_id=4921257385345&'\
                    'url=http://\www.forever21.com&'\
                    'ref_url=&'\
                    'request_type=search&'\
                    'rows=60&'\
                    'start={start}&'\
                    'l={search_term}&'\
                    'q={search_term}&'\
                    'search_type=keyword'\

    REVIEW_URL = "http://cdn.powerreviews.com/repos/14626/pr/pwr/"\
                 "content/{code}/{product_id}-en_US-meta.js"

    VARIANT_URL = "http://www.forever21.com/Ajax/Ajax_Product.aspx"\
                  "?method=CHANGEPRODUCTCOLOR&productid={product_id}"\
                  "&colorid={color_id}&colorName={color_name}"

    def __init__(self, *args, **kwargs):
        settings.overrides[
            'RETRY_HTTP_CODES'] = [500, 502, 503, 504, 400, 403, 408]

        super(Forever21ProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def _total_matches_from_html(self, response):
        json_data = json.loads(response.body)
        total = json_data.get('response', {}).get('numFound', 0)
        return total

    def _scrape_results_per_page(self, response):
        json_data = json.loads(response.body)
        products = json_data.get('response', {}).get('docs', [])
        return len(products)

    def _scrape_next_results_page_link(self, response):
        last_position_search = re.search('start=(\d+)&', response.url)
        if last_position_search:
            last_pos = last_position_search.group(1)
            next_pos = int(last_pos) + self._scrape_results_per_page(response)
            st = response.meta['search_term']
            return self.NEXT_PAGE_URL.format(
                start=next_pos,
                search_term=urllib.quote_plus(st.encode('utf-8')))

        return None

    def _scrape_product_links(self, response):
        json_data = json.loads(response.body)
        products = json_data.get('response', {}).get('docs', [])
        for product in products:
            yield product.get('url'), SiteProductItem()

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def _parse_title(self, response):
        title = response.xpath('//*[@class="item_name_p"]/text()').extract()
        return title[0] if title else None

    def _parse_brand(self, response):
        brand = response.xpath('//*[@class="brand_name_p"]/text()').extract()
        return brand[0] if brand else None

    def _parse_categories(self, response):
        categories = response.xpath(
            '//*[@id="div_breadcrumb"]//a/text()').extract()
        return categories if categories else None

    def _parse_category(self, response):
        categories = self._parse_categories(response)
        return categories[-1] if categories else None

    def _parse_price(self, response):
        price = response.xpath(
            '//*[@itemprop="price"]/text()'
            '|//*[@itemprop="price"]/*[@class="price_c sale"]'
            '/text()').re('[\d\.]+')
        currency = response.xpath(
            '//*[@itemprop="priceCurrency"]/@content').re('\w{2,3}') or ['USD']

        if not price:
            return None

        return Price(price=price[0], priceCurrency=currency[0])

    def _parse_image_url(self, response):
        image_url = response.xpath(
            '//img[@id="ctl00_MainContent_productImage"]/@src').extract()
        return image_url[0] if image_url else None

    def _parse_description(self, response):
        description = response.xpath(
            '//*[@class="description_wrapper"]/section/div/article/text()'
            '|//*[@class="description_wrapper"]/section/div/article'
            '//*[not(self::style)]').extract()

        return ''.join(description).strip() if description else None

    def parse_product(self, response):
        reqs = []
        meta = response.meta.copy()
        product = meta['product']

        # Set locale
        product['locale'] = 'en_US'

        # Parse title
        title = self._parse_title(response)
        cond_set_value(product, 'title', title, conv=string.strip)

        # Parse brand
        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand, conv=string.strip)

        # Parse categories
        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        # Parse category
        category = self._parse_category(response)
        cond_set_value(product, 'category', category)

        # Parse description
        description = self._parse_description(response)
        cond_set_value(product, 'description', description)

        reseller_id_regex = "[Pp]roduct[Ii][dD]=(\d+)"
        reseller_id = re.findall(reseller_id_regex, response.url)
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(product, 'reseller_id', reseller_id)

        # Parse price
        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse image url
        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        product_id = response.xpath(
            '//*[@class="hdProductId"]/@value').extract()
        if product_id:
            for color in response.xpath('//li[contains(@id,"colorid_")]'):
                color_id = color.xpath('@id').re('colorid_(.*)')[0]
                color_name = color.xpath('a/img/@alt').extract()[0]
                reqs.append(Request(
                    self.VARIANT_URL.format(product_id=product_id[0],
                                            color_id=color_id,
                                            color_name=color_name),
                    callback=self._parse_variants))

            response.meta['review'] = True
            code = self._get_product_code(product_id[0])
            reqs.append(Request(
                self.REVIEW_URL.format(code=code,
                                       product_id=product_id[0]),
                        errback=self._no_parse_reviews,
                        callback=self._parse_reviews))

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_variants(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs', [])
        variants = product.get('variants', [])
        json_data = json.loads(response.body)
        color_url = json_data.get('ProductDefaultImageURL')
        color_name = re.findall(
            'colorName=(.*)', response.url)[0]
        selector = Selector(text=json_data.get('ProductSizeHTML'))

        for size in selector.xpath('//li'):
            size_name = size.xpath('label/text()').extract()[0]
            in_stock = False if size.xpath('input/@disabled') else True
            vr = {}
            vr["properties"] = {}
            vr["properties"]["color"] = color_name
            vr["properties"]["size"] = size_name
            vr["properties"]["in_stock"] = in_stock
            vr["image_url"] = color_url

            variants.append(vr)

        product['variants'] = variants

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _no_parse_reviews(self, response):
        product = response.request.meta['product']
        reqs = response.request.meta.get('reqs', [])
        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        product['buyer_reviews'] = BuyerReviews(num_of_reviews=0,
                                                average_rating=0,
                                                rating_by_star=rating_by_star)
        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _parse_reviews(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs', [])

        rating_by_star = {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}
        stars = re.findall('rating:(\d+)', response.body)
        num_reviews = len(stars)
        avg_rating = sum([int(x) for x in stars]) / float(num_reviews)
        avg_rating = round(avg_rating, 1)
        for star in stars:
            rating_by_star[star] += 1

        product['buyer_reviews'] = BuyerReviews(num_of_reviews=num_reviews,
                                                average_rating=avg_rating,
                                                rating_by_star=rating_by_star)

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        new_meta = response.meta

        if reqs:
            new_meta["reqs"] = reqs

        return req.replace(meta=new_meta)

    def _get_product_code(self, product_id):
        # override js function
        cr = 0
        for i in range(0, len(product_id)):
            cp = ord(product_id[i])
            cp = cp * abs(255 - cp)
            cr += cp
        cr %= 1023
        cr = str(cr)
        ct = 4
        for i in range(0, ct - len(cr)):
            cr = '0' + cr
        cr = cr[0:2] + "/" + cr[2:4]
        return cr
