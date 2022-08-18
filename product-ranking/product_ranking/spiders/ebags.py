from __future__ import division, absolute_import, unicode_literals

import re
import urllib
import urlparse
import json
import hjson

from scrapy import Request, Selector
from scrapy.log import DEBUG

from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    FLOATING_POINT_RGEX
from product_ranking.validation import BaseValidator
from product_ranking.validators.homedepot_validator import HomedepotValidatorSettings
from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi


is_empty = lambda x, y=None: x[0] if x else y


def is_num(s):
    try:
        int(s.strip())
        return True
    except ValueError:
        return False


class EbagsProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'ebags_products'
    allowed_domains = ["ebags.com"]
    start_urls = []

    SEARCH_URL = "http://www.ebags.com/s/{search_term}?NCNI-5"
    DETAILS_URL = "http://www.ebags.com/product/%s"
    REVIEWS_URL = "http://ebags.ugc.bazaarvoice.com/1999m/%s/" \
        "reviews.djs?format=embeddedhtml"
    # RECOMMENDED_URL = "http://www.ebags.com/produc/v2/products/" \
    #     "recommendation?type=json&key=tRXWvUBGuAwEzFHScjLw9ktZ0Bw7a335"

    product_filter = []

    def __init__(self, *args, **kwargs):
        # All this is to set the site_name since we have several
        # allowed_domains.
        self.br = BuyerReviewsBazaarApi()
        super(EbagsProductsSpider, self).__init__(
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    @staticmethod
    def _parse_no_longer_available(response):
        message = response.xpath(
            '//div[@class="error" and '
            'contains(., "The product you are trying to view is not currently available.")]')
        return bool(message)

    def parse_product(self, response):
        product = response.meta['product']
        product['_subitem'] = True

        if self._parse_no_longer_available(response):
            product['no_longer_available'] = True
            return product
        else:
            product['no_longer_available'] = False

        product_info_json = \
            response.xpath("//script[contains(text(), 'dataLayer = [{')]/text()").extract()
        product_info_json = product_info_json[0].strip() if product_info_json else ''
        start_index = product_info_json.find("dataLayer = [") + len("dataLayer = [")
        end_index = product_info_json.find("];")
        product_info_json = product_info_json[start_index:end_index].strip()
        product_info_json = json.loads(product_info_json)

        product['title'] = product_info_json["productName"]
        product['brand'] = product_info_json["masterId"]

        cond_set(
            product,
            'image_url',
            response.xpath("//img[@id='pdMainImage']/@src").extract())

        cond_set(
            product,
            'price',
            response.xpath(
                "//div[@id='divPricing']//h2[@class='alert-drk']/span[@itemprop='price']/text()").extract())

        if product.get('price', None):
            if not '$' in product['price']:
                self.log('Unknown currency at' % response.url)
            else:
                product['price'] = Price(
                    price=product['price'].replace(',', '').replace(
                        '$', '').strip(),
                    priceCurrency='USD'
                )

        try:
            product['model'] = product_info_json["masterId"]
        except IndexError:
            pass

        internet_no = response.css('#product_internet_number ::text').extract()
        if internet_no:
            internet_no = internet_no[0]

        upc = is_empty(re.findall(
            "ItemUPC=\'(\d+)\'", response.body))
        if upc:
            product["upc"] = upc

        upc = response.xpath("//upc/text()").re('\d+')
        if upc:
            product["upc"] = upc[0]

        desc = response.xpath(
            "//div[contains(@class,'productDetailsCon')]"
            "//div[@itemprop='description']/text()"
        ).extract()
        desc = " ".join(l.strip() for l in desc if len(l.strip()) > 0)
        product['description'] = desc

        product['locale'] = "en-US"

        metadata = response.xpath(
            "//script[contains(text(),'PRODUCT_METADATA_JSON')]"
            "/text()").re('var PRODUCT_METADATA_JSON = (.*);')
        skus = []
        if metadata:
            metadata = metadata[0]
            jsmeta = hjson.loads(metadata)
            try:
                skus = [jsmeta["attributeDefinition"]["defaultSku"]]
                response.meta['skus'] = skus
                metaname = jsmeta['attributeDefinition']['attributeListing'][0][
                    'label']
                response.meta['attributelabel'] = metaname
            except (KeyError, IndexError):
                self.log("Incomplete data from Javascript.", DEBUG)

        certona_payload = self._gen_payload(response)

        if certona_payload:
            new_meta = response.meta.copy()
            new_meta['product'] = product
            new_meta['handle_httpstatus_list'] = [404, 415]
            new_meta['internet_no'] = internet_no
            headers = {'Proxy-Connection':'keep-alive', 'Content-Type':'application/json'}
            # return Request(
            #     self.RECOMMENDED_URL,
            #     callback = self._parse_related_products,
            #     headers = headers,
            #     body = json.dumps(certona_payload),
            #     method = "POST",
            #     meta=new_meta,
            #     priority=1000,
            # )

        self.parse_buyer_reviews(response)

        return self._gen_variants_requests(response, product, skus, internet_no)

    def _gen_variants_requests(self, response, product, skus, internet_no):
        reqs = []

        for sku in skus:
            # if sku:
            #     sku = sku[len(sku)-1]
            new_product = product.copy()

            new_meta = response.meta.copy()
            new_meta['product'] = new_product
            new_meta['handle_httpstatus_list'] = [404]
            new_meta['internet_no'] = internet_no
            url = self.DETAILS_URL % sku
            reqs.append(Request(
                url,
                self._parse_skudetails,
                meta=new_meta,
                priority=1000))
        if not reqs:
            return product
        return reqs

    def _gen_payload(self, response):
        """Generates request body. Also maxProducts value can be changed for +\- number of values"""

        # changed version 4.2x -> 5.3x
        # appid = response.xpath("//input[@id='certona_appId']/@value").extract()
        # if not appid:
        #     print "no appid"
        #     return
        appid = 'homedepot01'
        critemid = response.xpath(
            "//input[@id='certona_critemId']/@value").extract()
        if not critemid:
            critemid = is_empty(re.findall("\"itemId\"\:\"(\d+)\"", response.body))
        if not critemid:
            return

        payload = {
            "appId": appid,
            "products": critemid,
            "maxProducts": "16",
            "certonaSchema": "PIPHorizontal1_rr",
            "sessionId": "41020192309266",
            "trackingId": "252187705102752",
            "storeId": "123",
        }
        return payload

    def _parse_related_products(self, response):
        product = response.meta['product']
        internet_no = response.meta.get('internet_no', None)

        if response.status in response.meta['handle_httpstatus_list']:
            # No further pages were found. Check the request payload.
            return product

        data=json.loads(response.body_as_unicode())
        related_prods=[]
        for prod in data['schemas'][0]['products']:
            name = prod['productName']
            href = prod['canonicalURL']
            related_prods.append(RelatedProduct(
                name, urlparse.urljoin(product['url'], href))
            )
        if related_prods:
            if 'THE HOME DEPOT RECOMMENDS' in data['schemas'][0]['title']:
                product['related_products'] = {'recommended': related_prods}
            else:
                product['related_products'] = {'buyers_also_bought': related_prods}

        skus = response.meta.get('skus', None)

        if not skus:
            if internet_no:
                return Request(
                    url=self.REVIEWS_URL % internet_no,
                    callback=self.parse_buyer_reviews,
                    meta={"product": product},
                    dont_filter=True,
                )
            return product
        return self._gen_variants_requests(response, product, skus, internet_no)

    def _parse_skudetails(self, response):
        product = response.meta['product']

        try:
            jsdata = json.loads(response.body_as_unicode())
            storeskus = jsdata['storeSkus']
            price = storeskus['storeSku']['pricing']['originalPrice']
            product['price'] = price

            desc = jsdata['info']['description']
            product['description'] = desc

            url = jsdata['canonicalURL']
            url = urlparse.urljoin(product['url'], url)
            product['url'] = url

            image = jsdata['inlinePlayerJSON']['IMAGE'][1]['mediaUrl']
            product['image_url'] = image

            attrname = response.meta.get('attributelabel', 'Color/Finish')
            colornames = jsdata['attributeGroups']['group'][0]['entries'][
                'attribute']
            colornames = [el['value'] for el in colornames
                          if el['name'] == attrname]
            if colornames:
                product['model'] = str(colornames[0])
        except (ValueError, KeyError, IndexError):
            self.log("Failed to parse SKU details.", DEBUG)

        internet_no = response.meta.get('internet_no', None)
        if internet_no:
            return Request(
                url=self.REVIEWS_URL % internet_no,
                callback=self.parse_buyer_reviews,
                meta={"product": product},
                dont_filter=True,
            )

        return product

    def parse_buyer_reviews(self, response):
        product = response.meta.get("product")

        avg = response.xpath("//div[contains(@class,'ratings-summary')]//p[@class='ratingNumber']/span/text()").extract()[0]
        total_data = response.xpath("//div[contains(@class,'ratings-summary')]//p[@itemprop='reviewCount']/text()").extract()[0]
        total = re.findall("Based on ([\d,]+) Ratings", total_data)[0].replace(",", "")

        reviews = {}
        reviews['num_of_reviews'] = total
        reviews['average_rating'] = avg
        reviews['buyer_reviews'] = {}

        cond_set(product, 'buyer_reviews', None)

        return product

    def _scrape_total_matches(self, response):
        totals = response.xpath(
            "//a[@id='all_products']/label"
            "/text()").re(r'All Products \(([\d,]+)\)')
        if totals:
            totals = totals[0]
            totals = totals.replace(",", "")
            if is_num(totals):
                return int(totals)
        no_matches = response.xpath(
            "//h1[@class='page-title']/text()").extract()
        if no_matches:
            if 'we could not find any' in no_matches[0] or \
               'we found 0 matches for' in no_matches[0]:
                return 0
        total_matches = response.xpath('//*[contains(@id, "all_products")]//text()').extract()
        if total_matches:
            total_matches = ''.join(total_matches)
            total_matches = ''.join(c for c in total_matches if c.isdigit())
            if total_matches and total_matches.isdigit():
                return int(total_matches)
        total_matches = response.xpath('//div[@id="allProdCount"]/text()').re(FLOATING_POINT_RGEX)
        if total_matches:
            total_matches = total_matches[0]
            total_matches = total_matches.replace(',', '')
            if total_matches.isdigit():
                return int(total_matches)
        return

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class,'product') "
            "and contains(@class,'plp-grid')]"
            "//descendant::a[contains(@class, 'item_description')]/@href | "
            "//div[contains(@class, 'description')]/a[@data-pod-type='pr']/@href").extract()

        if not links:
            self.log("Found no product links.", DEBUG)

        for link in links:
            if link in self.product_filter:
                continue
            self.product_filter.append(link)
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        next_page = response.xpath(
            "//div[@class='pagination-wrapper']/ul/li/span"
            "/a[@title='Next']/@href |"
            "//div[contains(@class, 'pagination')]/ul/li/span"
            "/a[@class='icon-next']/@href |"
            "//li[contains(@class, 'hd-pagination__item')]"
            "/a[contains(@class, 'pagination__link') and @title='Next']/@href"
        ).extract()
        if next_page:
            return urlparse.urljoin(response.url, next_page[0])
