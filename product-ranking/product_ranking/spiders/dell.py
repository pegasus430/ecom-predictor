from __future__ import division, absolute_import, unicode_literals

import re
import json
import math
import urlparse
import socket
import traceback

from scrapy import Request
from scrapy.log import INFO, DEBUG

from product_ranking.items import SiteProductItem, Price, LimitedStock
from product_ranking.spiders import BaseProductsSpider, cond_set, FormatterWithDefaults
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.spiders import cond_set_value
from product_ranking.guess_brand import guess_brand_from_first_words
from scrapy.conf import settings


socket.setdefaulttimeout(60)


class DellProductSpider(BaseProductsSpider):
    name = 'dell_products'
    allowed_domains = ["dell.com", "recs.richrelevance.com"]

    handle_httpstatus_list = [404, 403, 502, 520]

    SEARCH_URL = "http://www.dell.com/csbapi/en-us/search?categoryPath=&q={search_term}&sortby=&" \
                 "page={page}&appliedRefinements="

    REVIEW_URL = "http://api.bazaarvoice.com/data/batch.json" \
                 "?passkey=cac9gq9XXSH1NKJAWmhsBXyqxBOSC8ff5BDD8kU3cz9KQ" \
                 "&apiversion=5.5" \
                 "&displaycode=17580-en_us" \
                 "&resource.q0=products" \
                 "&filter.q0=id%3Aeq%3A{product_id}" \
                 "&stats.q0=questions%2Creviews" \
                 "&filteredstats.q0=questions%2Creviews" \
                 "&filter_questions.q0=contentlocale%3Aeq%3Aen_US" \
                 "&filter_answers.q0=contentlocale%3Aeq%3Aen_US" \
                 "&filter_reviews.q0=contentlocale%3Aeq%3Aen_US" \
                 "&filter_reviewcomments.q0=contentlocale%3Aeq%3Aen_US"

    VARIANT_URL = "http://www.dell.com/csbapi/en-us/productdata/getdetails?" \
              "userContext={%22Country%22:%22us%22,%22Region%22:%22us%22,%22Language%22:%22en%22," \
              "%22Segment%22:%22bsd%22,%22CustomerSet%22:%2204%22}&isSNP=true"

    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/58.0.3029.96 Safari/537.36"}

    def __init__(self, *args, **kwargs):
        settings.overrides['DEPTH_PRIORITY'] = 1
        settings.overrides['SCHEDULER_DISK_QUEUE'] = 'scrapy.squeue.PickleFifoDiskQueue'
        settings.overrides['SCHEDULER_MEMORY_QUEUE'] = 'scrapy.squeue.FifoMemoryQueue'

        self.quantity = kwargs.get('quantity', 1000)  # default is 1000
        self.current_page = 1
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(DellProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(page=1),
            site_name=self.allowed_domains[0],
            *args, **kwargs)

    def start_requests(self):
        for request in super(DellProductSpider, self).start_requests():
            request = request.replace(dont_filter=True)
            yield request

    def _parse_single_product(self, response):
        return self.parse_product(response)

    @staticmethod
    def _parse_currency(response):
        if 'en-ca' in response.url:
            return 'CAD'
        else:
            return 'USD'

    def _parse_price(self, response):
        currency = self._parse_currency(response)
        dell_price = re.search('"DellPrice":(.*?)},', response.body)
        if dell_price:
            dell_price = dell_price.group(1) + '}'
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
    def _parse_image(response):
        img_src = response.xpath('//ul[contains(@class, "slides")]'
                                 '/li/img[@class="carImg"]/@data-blzsrc').extract()
        if not img_src:
            img_src = response.xpath('//ul[contains(@class, "slides")]/li/img[@class="carImg"]'
                                     '/@src').extract()
        if not img_src:
            img_src = response.xpath('//img[@data-testid="sharedPolarisHeroPdImage"]/@data-blzsrc').extract()
        if not img_src:
            img_src = response.xpath('//img[@data-testid="sharedPolarisHeroPdImage"]/@src').extract()
        if img_src:
            return img_src[0]

    @staticmethod
    def _parse_sku(response):
        sku = response.xpath('//meta[@name="snpsku"]/@content').extract()
        if sku:
            return sku[0]

    @staticmethod
    def _parse_brand(response, prod_title):
        brand = response.xpath('//meta[contains(@itermprop, "brand")]/@content').extract()
        if not brand:
            brand = response.xpath('//a[contains(@href, "/brand.aspx")]/img/@alt').extract()
        if brand:
            return brand[0].title()
        if prod_title:
            brand = guess_brand_from_first_words(prod_title)
            if not brand:
                prod_title = prod_title.replace('New ', '').strip()
                brand = guess_brand_from_first_words(prod_title)
            if brand:
                return brand

    @staticmethod
    def _parse_reseller_id(response):
        reseller_id = response.xpath('//meta[@name="snpsku"]/@content').extract()
        if reseller_id:
            return reseller_id[0]

    def _get_stock_status(self, response, product):
        oos_element = response.xpath(
            '//a[contains(@class, "smallBlueBodyText")]'
            '[contains(@href, "makeWin")]//text()').extract()
        if oos_element:
            oos_element = oos_element[0].lower()
            if ('temporarily out of stock' in oos_element
                    or 'pre-order' in oos_element):
                product['is_out_of_stock'] = True
                return product
            if 'limited supply available' in oos_element:
                product['is_out_of_stock'] = False
                product['limited_stock'] = LimitedStock(is_limited=True, items_left=-1)
                return product

    def _parse_variants(self, response):
        product = response.meta['product']
        variants = product.get('variants', [])
        product_id = response.meta['product_id']

        try:
            json_data = json.loads(response.body)
            for data in json_data:
                title = data.get('Title', {}).get('TitleText')
                sku = data.get('ItemIdentifier')
                image_url = data.get('MetaData', {}).get('MetaTags', [])[26].get('Content')
                price = data.get('DataModel', {}).get('Stacks', [])[0].get('Stack', {}).get('Pricing', {}) \
                    .get('DellPrice', {}).get('Value')
                pros = {'size': data.get('DataModel', {}).get('Stacks', [])[0].get('Stack', {}).get('Variance', {})
                    .get('Variants')[0].get('CurrentOptionValue')}
                variant = {
                    'title': title,
                    'sku': sku,
                    'price': price,
                    'image_url': image_url,
                    'properties': pros,
                }
                variants.append(variant)
            product['variants'] = variants

        except:
            self.log('Error Parsing Variants: {}'.format(traceback.format_exc()))

        return Request(self.REVIEW_URL.format(product_id=product_id),
                       dont_filter=True,
                       meta=response.meta,
                       callback=self.br._parse_buyer_reviews_from_filters,
                       headers=self.HEADERS)

    @staticmethod
    def _get_product_id(response):
        prod_id = re.findall(':productdetails:([\da-zA-Z\-\.]{1,50})\",', response.body_as_unicode())
        if prod_id:
            return prod_id[0]

    @staticmethod
    def _categories(response):
        return response.xpath('//ol[contains(@class, "breadcrumb")]/li/a/text()').extract()

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta['product']

        if not response.status == 200:
            return

        product['locale'] = 'en_US'

        product['url'] = response.url

        cond_set(product, 'title', response.css('h1 ::text').extract())
        product['price'] = self._parse_price(response)
        product['image_url'] = self._parse_image(response)

        product['reseller_id'] = self._parse_reseller_id(response)
        product['sku'] = self._parse_sku(response)
        product['brand'] = self._parse_brand(response, product.get('title', ''))
        product['categories'] = self._categories(response)

        if product['categories']:
            cond_set_value(product, 'department', product['categories'][-1])

        out_of_stock = re.search('"ProductOutOfStock":(.*?),', response.body_as_unicode())
        if out_of_stock:
            product['is_out_of_stock'] = not (out_of_stock.group(1) == 'false')

        product_id = response.xpath('//meta[@name="ProductId"]/@content').extract()

        if product_id:
            var_list = response.xpath('//li[@class="product-variances-list-item"]/a/@data-sku').extract()
            for var in var_list:
                self.VARIANT_URL += '&itemIdentifiers=' + var
            meta['product_id'] = product_id[0]
            return Request(self.VARIANT_URL, meta=meta, callback=self._parse_variants)

        return product

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            total = int(data['AnavFilterModel']['TotalResultCount'])
        except Exception as e:
            self.log("Exception converting total_matches to int: {}".format(traceback.format_exc()), DEBUG)
            total = 0
        finally:
            return total

    def _scrape_product_links(self, response):
        """
        Scraping product links from search page
        """
        try:
            link_list = []
            data = json.loads(response.body_as_unicode())
            for result in data['AnavFilterModel']['Results']['Stacks']:
                if 'Links' in result['Stack']:
                    link = result['Stack']['Links']['ViewDetailsLink']['Url']
                    link_list.append(link)

            if link_list:
                for link in link_list:
                    link = urlparse.urljoin(response.url, link)
                    res_item = SiteProductItem()
                    yield link, res_item
        except:
            self.log("Found no product links in {url}".format(url=response.url), INFO)

    def _scrape_next_results_page_link(self, response):
        total_matches = self._scrape_total_matches(response)
        results_per_page = self._scrape_results_per_page(response)
        if not results_per_page:
            results_per_page = 12
        if (total_matches and results_per_page
            and self.current_page < math.ceil(total_matches / float(results_per_page))):
            self.current_page += 1

            next_link = self.SEARCH_URL.format(search_term=response.meta['search_term'],
                                               page=self.current_page, dont_filter=True)
            return next_link
