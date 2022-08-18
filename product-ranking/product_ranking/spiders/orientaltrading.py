# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, unicode_literals

import json
import re

from scrapy import Request

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.items import SiteProductItem, RelatedProduct, Price
from product_ranking.spiders import BaseProductsSpider, cond_set, \
    cond_set_value
from spiders_shared_code.orientaltrading_variants import OrientaltradingVariants

is_empty = lambda x, y=None: x[0] if x else y

# TODO: variants


class OrientaltradingProductsSpider(BaseProductsSpider):
    name = 'orientaltrading_products'
    allowed_domains = ['orientaltrading.com', "www.orientaltrading.com"]
    start_urls = []

    SEARCH_URL = "http://www.orientaltrading.com/web/search/searchMain?Ntt={search_term}"

    PAGINATE_URL = "http://www.orientaltrading.com/web/search/searchMain?Nrpp=64&No={nao}&Ntt={search_term}"

    CURRENT_NAO = 0
    PAGINATE_BY = 64  # 64 products
    TOTAL_MATCHES = None  # for pagination

    REVIEW_URL = "http://orientaltrading.ugc.bazaarvoice.com/0713-en_us/{product_id}" \
                 "/reviews.djs?format=embeddedhtml&page={index}&"

    VARIANT_PRODUCT = 'http://www.orientaltrading.com/web/browse/processProductsCatalog'

    #use_proxies = True

    def __init__(self, *args, **kwargs):
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(OrientaltradingProductsSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        meta = response.meta.copy()
        product = meta.get('product', SiteProductItem())
        reqs = []
        meta['reqs'] = reqs

        # Parse locate
        locale = 'en_US'
        cond_set_value(product, 'locale', locale)

        # Parse title
        title = self.parse_title(response)
        cond_set(product, 'title', title)

        # Parse image
        image = self.parse_image(response)
        cond_set(product, 'image_url', image)

        # Parse sku
        sku = self.parse_sku(response)
        cond_set_value(product, 'sku', sku)

        # Parse reseller_id
        cond_set_value(product, "reseller_id", sku)

        # Parse price
        price = self.parse_price(response)
        cond_set_value(product, 'price', price)

        # Parse description
        description = self.parse_description(response)
        cond_set(product, 'description', description)

        product['related_products'] = self.parse_related_product(response)

        otv = OrientaltradingVariants()
        otv.setupSC(response)
        _variants = otv._variants()
        if _variants:
            product['variants'] = _variants

        # reqs = self.parse_variants(response, reqs)

        # Parse reviews
        reqs.append(
                Request(
                    url=self.REVIEW_URL.format(product_id=product['sku'].replace('/', '_'), index=0),
                    dont_filter=True,
                    callback=self.parse_buyer_reviews,
                    meta=meta
                ))

        if reqs:
            return self.send_next_request(reqs, response)
        else:
            return product

    def clear_text(self, str_result):
        return str_result.replace("\t", "").replace("\n", "").replace("\r", "").replace(u'\xa0', ' ').strip()

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def parse_related_product(self, response):
        related_prods = []
        urls = response.xpath('//div[contains(@class, "ymal-content-wrapper")]/p/a/@href').extract()
        titles = response.xpath('//div[contains(@class, "ymal-content-wrapper")]/p/a/text()').extract()  # Title

        for title, url in zip(titles, urls):
            if url and title:
                related_prods.append(
                    RelatedProduct(
                        title=title,
                        url=url
                    )
                )

        related_products = {}
        if related_prods:
            related_products['you may also like'] = related_prods

        return related_products

    def parse_title(self, response):
        title = response.xpath('//meta[contains(@property, "og:title")]/@content').extract()
        return title

    def parse_image(self, response):
        img = response.xpath('//meta[contains(@property, "og:image")]/@content').extract()
        return img

    def parse_description(self, response):
        description = response.xpath(
            '//div[contains(@class, "pd-text-bloc")] | //p[contains(@class, "pd-text-bloc")]').extract()
        if description:
            return description
        else:
            return ''

    def parse_sku(self, response):
        sku = response.xpath('//input[contains(@id, "productsku")]/@value').extract()
        if sku:
            return sku[0]

    def parse_productid(self, response):
        model = response.xpath('//input[contains(@id, "productId")]/@value').extract()
        if model:
            return model[0]

    def parse_price(self, response):
        price = response.xpath('//p[contains(@id, "pd-price")]/text()').extract()
        if price:
            price = self.clear_text(price[0].replace('NOW', '').replace('$', ''))
            return Price(price=price, priceCurrency="USD")
        else:
            return Price(price=0.00, priceCurrency="USD")

    """
    def parse_variants(self, response, reqs):

        select_variants = response.xpath('//fieldset[contains(@class, "select-options")]/select')
        if select_variants:

            OTC_CSRFTOKEN = response.xpath('//input[contains(@name, "OTC_CSRFTOKEN")]/@value').extract()
            prefix = response.xpath('//input[contains(@id, "prefix")]/@value').extract()
            productId = response.xpath('//input[contains(@id, "productId")]/@value').extract()
            parentSku = response.xpath('//input[contains(@id, "parentSku")]/@value').extract()
            demandPrefix = response.xpath('//input[contains(@id, "demandPrefix")]/@value').extract()
            pznComponentIndex = response.xpath('//input[contains(@id, "pznComponentIndex")]/@value').extract()
            pznHiddenData = response.xpath('//input[contains(@id, "pznHiddenData")]/@value').extract()
            pznImageName = response.xpath('//input[contains(@id, "pznImageName")]/@value').extract()
            destinationDisplayJSP = response.xpath('//input[contains(@name, "destinationDisplayJSP")]/@value').extract()
            requestURI = response.xpath('//input[contains(@name, "requestURI")]/@value').extract()
            numberOfAttributes = response.xpath('//input[contains(@id, "numberOfAttributes")]/@value').extract()
            categoryId = response.xpath('//input[contains(@id, "categoryId")]/@value').extract()
            mode = response.xpath('//input[contains(@id, "mode")]/@value').extract()
            quantity = response.xpath('//input[contains(@name, "quantity")]/@value').extract()

            params = {'OTC_CSRFTOKEN': OTC_CSRFTOKEN[0],
                      'categoryId': categoryId[0],
                      'demandPrefix': demandPrefix[0],
                      'destinationDisplayJSP': destinationDisplayJSP[0],
                      'mode': mode[0],
                      'numberOfAttributes': numberOfAttributes[0],
                      'parentSku': parentSku[0],
                      'prefix': prefix[0],
                      'productId': productId[0],
                      'pznComponentIndex': pznComponentIndex[0],
                      'pznHiddenData': pznHiddenData[0],
                      'pznImageName': pznImageName[0],
                      'quantity': quantity[0],
                      'requestURI': requestURI[0],
                      'sku': '',
                      }

            for v in select_variants:
                name = v.xpath('@name').extract()
                options = v.xpath('option/@value').extract()
                for opt in options:
                    if opt:
                        # TODO: get variant sku for params['sku']
                        # url = 'http://www.orientaltrading.com/rest/ajax/'
                        # post_data = {'formData': "{\"sku\":\"%s\",\"uniqueIdentifier\":\"\",\"nameArray\":[\"%s\"],"
                        #                          "\"valueArray\":[\"%s\"],\"command\":\"AttributeSkuLookup\"}" % (sku, name[0], opt[0]),
                        #              'requestURI': "/"
                        #              }
                        # reqs.append(FormRequest(url=url, formdata=post_data, callback=self.get_sku_attribute))

                        params[name[0]] = opt
                        reqs.append(FormRequest(url=self.VARIANT_PRODUCT,
                                                formdata=params,
                                                callback=self.parse_variants_info))

        return reqs
    """

    """
    def parse_variants_info(self, response):
        meta = response.meta.copy()
        product = response.meta['product']
        reqs = meta.get('reqs', [])

        sku = self.parse_sku(response)
        price = self.parse_price(response)

        if reqs:
            return self.send_next_request(reqs, response)
        else:
            return product
    """

    def get_sku_attribute(self, response):
        meta = response.meta.copy()
        product = response.meta['product']
        reqs = meta.get('reqs', [])

        jsondata = json.loads(response.body_as_unicode())

        # {"uniqueIdentifier":"","parentSku":"13578611","attributeSku":"13582742"}
        new_sku = jsondata['attributeSku']

        if reqs:
            return self.send_next_request(reqs, response)
        else:
            return product

    def parse_buyer_reviews(self, response):

        meta = response.meta.copy()
        product = response.meta['product']
        reqs = meta.get('reqs', [])

        product['buyer_reviews'] = self.br.parse_buyer_reviews_per_page(response)

        if reqs:
            return self.send_next_request(reqs, response)
        else:
            return product

    def _scrape_total_matches(self, response):

        data = re.findall(r'site_search_results: "(.+)"', response.body_as_unicode())
        if data:
            totals = data[0]
            if totals.isdigit():
                if not self.TOTAL_MATCHES:
                    self.TOTAL_MATCHES = int(totals)
                return int(totals)
        else:
            return 0

    def _scrape_product_links(self, response):
        for link in response.xpath(
                '//div[contains(@id, "tableSearchResultsPhoto")]/a/@href'
        ).extract():
            yield link, SiteProductItem()

    # def _get_nao(self, url):
    #     nao = re.search(r'pn=(\d+)', url)
    #     if not nao:
    #         return
    #     return int(nao.group(1))
    #
    # def _replace_nao(self, url, new_nao):
    #     current_nao = self._get_nao(url)
    #     if current_nao:
    #         return re.sub(r'nao=\d+', 'pn=' + str(new_nao), url)
    #     else:
    #         return url + '&pn=' + str(new_nao)

    def _scrape_next_results_page_link(self, response):
        if self.TOTAL_MATCHES is None:
            self.log('No "next result page" link!')
            return
        if self.CURRENT_NAO > self.TOTAL_MATCHES + self.PAGINATE_BY:
            return  # it's over
        self.CURRENT_NAO += self.PAGINATE_BY
        return Request(
            self.PAGINATE_URL.format(
                search_term=response.meta['search_term'],
                nao=str(self.CURRENT_NAO)),
            callback=self.parse, meta=response.meta
        )
