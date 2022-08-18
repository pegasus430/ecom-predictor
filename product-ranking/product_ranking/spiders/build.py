from __future__ import absolute_import, division, unicode_literals

import json
import re
import traceback
from urlparse import urljoin

from scrapy import Request, FormRequest
from scrapy.conf import settings

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import BaseProductsSpider, cond_set_value
from product_ranking.validation import BaseValidator


class BuildProductsSpider(BaseValidator, BaseProductsSpider):
    name = 'build_products'
    allowed_domains = ["www.build.com"]
    SEARCH_URL = "https://www.build.com/search?term={search_term}"
    REVIEWS_URL = "https://api.bazaarvoice.com/data/" \
                 "reviews.json?passkey=6s5v8vtfa857rmritww93llyn&apiversion=5.5" \
                 "&filter=productid%3Aeq%3Acp-{product_id}&filter=contentlocale%3Aeq%3Aen_US" \
                 "&stats=reviews&filteredstats=reviews&include=products"

    CAPTCHA_URL = '{referer}/px/captcha/?pxCaptcha={solution}'

    handle_httpstatus_list = [405]

    def __init__(self, *args, **kwargs):
        settings.overrides['USE_PROXIES'] = False
        self.br = BuyerReviewsBazaarApi(called_class=self)
        super(BuildProductsSpider, self).__init__(
            *args, **kwargs)
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)' \
                          'Chrome/66.0.3359.139 Safari/537.36'
        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.middlewares.twocaptcha.TwoCaptchaMiddleware'] = 500
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
        settings.overrides['CAPTCHA_SOLVER'] = 'product_ranking.middlewares.captcha.solvers.multicaptcha.MultiCaptchaSolver'

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

    def is_recaptcha(self, response):
        return response.status == 403

    def is_captcha_page(self, response):
        captcha = response.xpath('//form[@id="distilCaptchaForm"]')
        return bool(captcha) or response.status == 403

    def get_captcha_key(self, response):
        pk = response.xpath(
            '//div[@id="funcaptcha"]/@data-pkey |'
            '//div[@class="g-recaptcha"]/@data-sitekey'
        ).extract()
        return pk[0] if pk else None

    def get_captcha_formaction(self, response):
        url = response.xpath('//form[@id="distilCaptchaForm"]/@action').extract()
        return urljoin(response.url, url[0]) if url else None

    def get_funcaptcha_form(self, url, solution, callback):
        return FormRequest(
            url,
            formdata={
                "fc-token": solution
            },
            callback=callback
        )

    def get_captcha_form(self, response, solution, referer, callback):
        uid = re.search(r'window\.px_uuid="(.*?)";', response.body)
        if uid:
            uid = uid.group(1)
        else:
            uid = ""
        vid = re.search(r'window\.px_vid="(.*?)";', response.body)
        if vid:
            vid = vid.group(1)
        else:
            vid = ""
        return Request(
            url=self.CAPTCHA_URL.format(referer=referer, solution=json.dumps({'r': solution, 'v': vid, 'u': uid})),
            callback=callback,
            meta=response.meta
        )

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        product = response.meta['product']
        product_id = None

        json_data = self._extract_json_data(response)
        if json_data:
            product_id = json_data.get('productCompositeId')
            product_data = json_data.get('selectedFinish')
            if product_data and isinstance(product_data, dict):
                sku = product_data.get('sku')
                cond_set_value(product, 'sku', sku)

                upc = product_data.get('upc')
                cond_set_value(product, 'upc', upc)

                is_out_of_stock = product_data.get('isOutOfStock')
                cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

                reseller_id = product_data.get('uniqueId')
                cond_set_value(product, 'reseller_id', unicode(reseller_id))

        product['locale'] = "en-US"

        title = self._parse_title(response)
        cond_set_value(product, 'title', title)

        brand = self._parse_brand(response)
        cond_set_value(product, 'brand', brand)

        image_url = self._parse_image_url(response)
        cond_set_value(product, 'image_url', image_url)

        price = self._parse_price(response)
        cond_set_value(product, 'price', price)

        categories = self._parse_categories(response)
        cond_set_value(product, 'categories', categories)

        category = self._category_name(response)
        product['department'] = category

        if product_id:
            return Request(
                url=self.REVIEWS_URL.format(product_id=product_id),
                callback=self.parse_buyer_reviews,
                meta={"product": product, "productID": product_id,
                      'product_id': "cp-{}".format(product_id)},
                dont_filter=True,
            )

        return product

    def _parse_title(self, response):
        title = response.xpath("//meta[@property='og:title']/@content").extract()

        return title[0] if title else None

    def _parse_brand(self, response):
        title = self._parse_title(response)
        brand = None
        if title:
            brand = guess_brand_from_first_words(title)
        return brand

    def _parse_categories(self, response):
        categories = response.xpath("//div[@class='breadcrumbs']//a/text()").extract()

        return categories[1:] if categories else None

    def _category_name(self, response):
        category = self._parse_categories(response)
        return category[-1] if category else None

    def _parse_image_url(self, response):
        main_image = response.xpath("//div[contains(@class, 'gallery-image')]//img/@src").extract()

        return main_image[0] if main_image else None

    def _parse_price(self, response):
        price = response.xpath("//div[@class='text-price']//span/text()").extract()
        if price:
            price = price[0].split('-')[0]
            try:
                price = Price(
                    price=price.replace(',', '').replace('$', '').strip(),
                    priceCurrency='USD'
                )
            except:
                self.log('Can no convert price type: {}'.format(traceback.format_exc()))
            else:
                return price

    def parse_buyer_reviews(self, response):
        product = response.meta.get('product')
        product['buyer_reviews'] = BuyerReviews(**self.br.parse_buyer_reviews_single_product_json(response))
        return product

    def _scrape_total_matches(self, response):
        total_matches = response.xpath('//span[@class="total"]/span[@class="js-num-results"]/text()').re('\d{1,3}[,\d{3}]*')
        try:
            total_matches_value = int(total_matches[0].replace(',', ''))
        except:
            self.log('Can not convert total matches value into int: {}'.format(traceback.format_exc()))
            total_matches_value = 0

        return total_matches_value

    def _scrape_product_links(self, response):
        product_link_info = response.xpath(
            '//li[contains(@id, "product")]//div[contains(@class, "product-description")]'
            '/a[contains(@class, "product-link")]/@href'
        ).extract()
        if not product_link_info:
            product_link_info = response.xpath('//*[@class="product-tile"]/a/@href').extract()

        for item_url in product_link_info:
            item_url = urljoin(response.url, item_url)
            yield item_url, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        current_page = meta.get('current_page', 1)
        current_page += 1
        next_page = response.xpath('//a[@data-page="{}"]/@href'.format(current_page)).extract()
        meta['current_page'] = current_page
        if next_page:
            return Request(
                urljoin(response.url, next_page[0]),
                meta=meta,
            )

    def _extract_json_data(self, response):
        try:
            json_data = json.loads(
                response.xpath(
                    '//script[contains(text(), "var dataLayer ")]/text()'
                ).re(re.compile("var dataLayer = ({.+?});"))[0])
        except:
            self.log('Can not extract json: {}'.format(traceback.format_exc()))
        else:
            return json_data
