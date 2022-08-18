from __future__ import absolute_import, division, unicode_literals

import json
import re
import urlparse
import traceback
import urllib
from future_builtins import zip

from scrapy.log import ERROR, WARNING
from scrapy.conf import settings
from scrapy import Request
from lxml import html

from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import Price, SiteProductItem
from product_ranking.spiders import (FLOATING_POINT_RGEX, BaseProductsSpider,
                                     cond_set, cond_set_value)
from product_ranking.utils import is_empty, catch_dictionary_exception, catch_json_exceptions


class TescoProductsSpider(BaseProductsSpider):
    """ tesco.com product ranking spider

    There are following caveats:

    - always add -a user_agent='android_pad',
      sample reverse calling
        scrapy crawl tesco_products -a product_url='http://www.tesco.com/groceries/product/details/?id=286394325' \
            -a user_agent='android_pad'
    """

    name = 'tesco_products'
    allowed_domains = ["tesco.com"]
    handle_httpstatus_list = [404]

    # TODO: change the currency if you're going to support different countries
    #  (only UK and GBP are supported now)
    SEARCH_URL = "https://www.tesco.com/groceries/en-GB/search?query={search_term}&count=48"

    headers = {
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36'
    }

    PRODUCT_URL = "https://www.tesco.com/groceries/en-GB/products/{}"

    ADS_URL = "https://securepubads.g.doubleclick.net/gampad/ads?gdfp_req=1&" \
              "correlator=2587207598120101&output=json_html&callback=googletag.impl.pubads.callbackProxy1&" \
              "impl=fifs&json_a=1&eid=21061193%2C108809103%2C21060875%2C21060878%2C21060713&" \
              "sc=1&sfv=1-0-13&iu_parts=8326%2Cgrocery%2Csearch&enc_prev_ius=%2F0%2F1%2F2&" \
              "prev_iu_szs=320x50%7C918x110&fluid=height&" \
              "cust_params=search%3D{search_term}%26nocid%3Dyes%26store%3D%26tppid%3D&" \
              "cookie=ID%3D97302f791401c963%3AT%3D1508787339%3AS%3DALNI_MYWMx9negb_hSB4TuTKCQ_32_NeeA&" \
              "cdm=www.tesco.com&lmt=1508416477&dt=1508861781375&ea=0&frm=23&biw=1378&bih=393&isw=924&" \
              "ish=0&oid=3&adxs=107&adys=279&adks=2105231814&gut=v2&ifi=1&ifk=436473490&u_tz=-240&" \
              "u_his=6&u_h=900&u_w=1440&u_ah=876&u_aw=1393&u_cd=24&u_nplug=4&u_nmime=5&u_sd=1&" \
              "flash=0&nhd=1&iag=3&url=https%3A%2F%2Fwww.tesco.com%2Fgroceries%2Fdfp%2Fdfp-beaa1a3b14.html&" \
              "ref=https%3A%2F%2Fwww.tesco.com%2Fgroceries%2Fen-GB%2Fsearch%3Fquery%3D{search_term}"

    def __init__(self, *args, **kwargs):
        super(TescoProductsSpider, self).__init__(*args, **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

        settings.overrides['USE_PROXIES'] = True

        RETRY_HTTP_CODES = settings.get('RETRY_HTTP_CODES')
        if 404 in RETRY_HTTP_CODES:
            RETRY_HTTP_CODES.remove(404)
        self.detect_ads = False
        detect_ads = kwargs.pop('detect_ads', False)
        if detect_ads in (1, '1', 'true', 'True', True):
            self.detect_ads = True

    def start_requests(self):
        for request in super(TescoProductsSpider, self).start_requests():
            if self.product_url:
                if 'id=' not in self.product_url:
                    url = self.PRODUCT_URL.format(self.product_url.split('/')[-1])
                    request = request.replace(url=url, headers=self.headers)
                yield request
            else:
                for st in self.searchterms:
                    if self.detect_ads:
                        url = self.ADS_URL.format(search_term=urllib.quote_plus(st.encode('utf-8')))
                        request = request.replace(url=url,
                                                  callback=self._get_ads_product)
                    yield request

    def _get_ads_product(self, response):
        meta = response.meta.copy()
        ads_html_content = None
        ads_content = self._find_between(response.body.decode('string_escape'), '"_html_":', ',"_snippet_"')
        if ads_content:
            ads_html_content = html.fromstring(ads_content)

        ads_urls = []
        image_urls = []
        if ads_html_content:
            ads_urls.extend([ad for ad in ads_html_content.xpath('//a[contains(@class, "stamp--")]/@href')])
            image_urls.extend([ad for ad in ads_html_content.xpath(
                '//a[contains(@class, "stamp--")]/span[contains(@class, "img--container")]/img[1]/@src')])
        if ads_urls:
            meta['ads_idx'] = 0
            meta['image_urls'] = image_urls
            meta['ads_urls'] = ads_urls

            return Request(
                url=ads_urls[0],
                meta=meta,
                callback=self._parse_ads_product,
                dont_filter=True,
            )
        else:
            return Request(
                url=self.SEARCH_URL.format(search_term=response.meta.get('search_term')),
                meta=meta
            )

    def _parse_ads_product(self, response):
        meta = response.meta.copy()
        ads = []
        ads_idx = meta.get('ads_idx')
        ads_urls = meta.get('ads_urls')
        image_urls = meta.get('image_urls')

        for i, url in enumerate(ads_urls):
            ad = {
                'ad_url': url,
                'ad_image': image_urls[i]
            }
            ads.append(ad)

        product_links = self._get_ads_product_links(response)
        product_names = self._get_ads_product_names(response)
        if product_links:
            products = [{
                'url': product_links[i],
                'name': product_names[i],
            } for i in range(len(product_links))]

            ads[ads_idx]['ad_dest_products'] = products
            ads[ads_idx]['brand'] = self.brand_from_title(product_names[0])
        meta['ads'] = ads

        ads_idx += 1
        if ads_idx < len(ads_urls):
            link = ads_urls[ads_idx]
            meta['ads_idx'] += 1
        else:
            return Request(
                url=self.SEARCH_URL.format(search_term=response.meta.get('search_term')),
                meta=meta
            )

        return Request(
            url=link,
            meta=response.meta,
            callback=self._parse_ads_product,
            dont_filter=True
        )

    @staticmethod
    def _get_ads_product_links(response):
        links = []
        items = response.xpath('//div[@class="product-details--content"]/a[1]/@href').extract()
        for item in items:
            links.append(urlparse.urljoin(response.url, item))
        return links

    def _get_ads_product_names(self, response):
        item_names = []
        items = response.xpath('//div[@class="product-details--content"]/a[1]/text()').extract()
        for item in items:
            item_names.append(self._clean_text(item))
        return item_names

    @staticmethod
    def brand_from_title(title):
        return guess_brand_from_first_words(title)

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse_product(self, response):
        if self.user_agent_key not in ["desktop", "default"]:
            return self.parse_product_mobile(response)

        else:
            return self.parse_product_desktop(response)

    def _scrape_total_matches(self, response):
        try:
            return int(response.xpath("//*[contains(@class, 'pagination')]/*/text()").re(r'(\d+) items')[0])
        except:
            self.log("Failed to parse total matches: {}".format(traceback.format_exc()), ERROR)

    def _scrape_total_matches_mobile(self, response):
        total = response.xpath(
            '//h1[@class="heading_button"]'
            '/span[@class="title"]/text()').re('(\d+) result')
        if total:
            return int(total[0])
        return None

    def _scrape_product_links(self, response):
        # To populate the description, fetching the product page is necessary.
        meta = response.meta.copy()

        if self.user_agent_key not in ["desktop", "default"]:
            links = response.xpath(
                '//section[contains(@class,"product_listed")]'
                '//div[contains(@class,"product_info")]//a/@href').extract()

            if not links:
                self.log("[Mobile] Found no product data on: %s" % response.url, ERROR)

            for link in links:
                yield urlparse.urljoin(response.url, link), SiteProductItem()
        else:
            url = response.url

            # This will contain everything except for the URL and description.
            product_jsons = response.xpath('//meta[@name="productdata"]/@content').extract()

            if product_jsons:
                product_links = response.css(
                    ".product > .desc > h2 > a ::attr('href')").extract()
                if not product_links:
                    self.log("Found no product links on: %s" % url, WARNING)

                for product_json, product_link in zip(product_jsons[0].split('|'), product_links):
                    prod = SiteProductItem()
                    cond_set_value(prod, 'url', urlparse.urljoin(url, product_link))

                    product_data = json.loads(product_json)

                    cond_set_value(prod, 'price', product_data.get('price'))
                    cond_set_value(prod, 'image_url', product_data.get('mediumImage'))

                    if prod.get('price', None):
                        prod['price'] = Price(
                            price=str(prod['price']).replace(',', '').strip(),
                            priceCurrency='GBP'
                        )

                    try:
                        cond_set_value(prod, 'title', product_data['name'])
                    except KeyError:
                        raise AssertionError(
                            "Did not find title or brand from JS for product: %s"
                            % product_link
                        )
                    if self.detect_ads:
                        prod['ads'] = meta.get('ads')

                    yield None, prod
            else:
                ids = response.xpath(
                    '//li[contains(@class, "product-list--list-item")]//div[@class="tile-content"]/@id').extract()
                for id in ids:
                    link = self.PRODUCT_URL.format(id)
                    prod = SiteProductItem()
                    if self.detect_ads:
                        prod['ads'] = meta.get('ads')
                    yield link, prod

    def _parse_next_page_link(self, response):
        links = response.xpath("//a[contains(@class, 'pagination--button prev-next') "
                               "and not(contains(@class, 'disabled'))]")
        if links:
            next_page = links[-1]
            if next_page.xpath('./span[contains(@class, "chevronright")]'):
                return next_page.xpath('@href').extract()[0]

    def _scrape_next_results_page_link(self, response):
        return self._scrape_next_results_page_link_mobile(response) if \
            self.user_agent_key not in ["desktop", "default"] else self._parse_next_page_link(response)

    def _scrape_next_results_page_link_mobile(self, response):
        url = response.url
        total = self._scrape_total_matches(response)
        current_page = re.findall("plpPage=(\d+)", url)

        if not current_page:
            return url + "&plpPage=2"
        else:
            curr = int(current_page[0])
            if curr < total / 20:
                curr += 1
                return re.sub("plpPage=(\d+)", "plpPage=%s" % curr, url)
            return None

    def _scrape_product_links_mobile(self, response):
        links = response.xpath(
            '//section[contains(@class,"product_listed")]'
            '//div[contains(@class,"product_info")]//a/@href').extract()

        if not links:
            self.log("Found no product data on: %s" % response.url, WARNING)

        for link in links:
            yield urlparse.urljoin(response.url, link), SiteProductItem()

    def parse_product_mobile(self, response):
        prod = response.meta['product']

        prod['url'] = response.url

        regex = "id=([A-Z0-9\-]+)"
        reseller_id = re.findall(regex, prod.get('url', ''))
        reseller_id = reseller_id[0] if reseller_id else None
        cond_set_value(prod, "reseller_id", reseller_id)

        cond_set(prod, 'locale', ['en-GB'])

        title = response.xpath(
            '//div[contains(@class,"descriptionDetails")]//h1//span[@data-title="true"]//text()'
        ).extract()
        cond_set(prod, 'title', title)

        try:
            brand = self.brand_from_title(prod['title'])
        except KeyError:
            self.log('Error Get title from parse_product_mobile: {}'.format(traceback.format_exc()), WARNING)
            return self.parse_product_desktop(response)

        img = response.xpath('//*[@id="pdp_image"]/img/@src').extract()
        cond_set(prod, 'image_url', img)

        price = response.xpath(
            '//div[contains(@class,"main_price")]'
            '/text()').re(FLOATING_POINT_RGEX)
        if price:
            prod['price'] = Price(price=price[0],
                                  priceCurrency='GBP')

        price_per_volume, volume_measure = self._parse_volume_price(response)

        cond_set_value(prod, 'price_per_volume', price_per_volume)
        cond_set_value(prod, 'volume_measure', volume_measure)

        return prod

    def _parse_volume_price(self, response):
        price = response.xpath('//span[@class="linePriceAbbr"]/text()').re(r'\((.*?)\/(.*?)\)')
        if price:
            try:
                return (float(price[0][1:].replace(',', '')), price[1]) if price[0] and price[1] else (None, None)
            except:
                self.log('Error Parsing Price Per Volume: {}'.format(traceback.format_exc()))
        return (None, None)

    def _get_product_data(self, response):
        """
        Get product json data
        :param response: General response objetc
        :return: product_json (json)
        """
        productdata = response.xpath(
            '/html/@data-props'
        ).extract()
        if productdata:
            try:
                product_json = json.loads(productdata[0])
                return product_json.get('product')
            except TypeError:
                self.log('Can\'t get product json: {}'.format(traceback.format_exc()))

    @staticmethod
    def _is_product(response):
        return bool(response.xpath('//h1[@class="product-title__h1"]/text()'))

    def parse_product_desktop(self, response):
        product = response.meta.get('product')
        if response.status == 404 and not self._is_product(response):
            self.log('Product not found')
            cond_set_value(product, 'not_found', True)
            return product

        productdata = self._get_product_data(response)

        product['promotions'] = bool(response.xpath('//div[@class="icon-offer-flash-group"]'))

        if productdata:
            cond_set_value(product, 'locale', 'en-GB')
            product["title"] = productdata.get("title")
            product["is_out_of_stock"] = not productdata.get("isForSale", False)
            product["url"] = self.PRODUCT_URL.format(str(productdata.get("id")))
            regex = "id=([A-Z0-9\-]+)"
            reseller_id = re.findall(regex, product.get('url'))
            reseller_id = reseller_id[0] if reseller_id else None
            cond_set_value(product, "reseller_id", reseller_id)

            try:
                product["price"] = Price(
                    price=productdata.get("price"),
                    priceCurrency="GBP"
                )
            except:
                pass

            product["image_url"] = productdata["mediumImage"]
            product["price_per_volume"], product["volume_measure"] = self._parse_volume_price(response)
            product["site"] = is_empty(self.allowed_domains)

        else:
            product['title'] = is_empty(response.xpath('//h1[@class="product-title__h1"]/text()').extract())
            product['image_url'] = is_empty(response.xpath('//*[@class="product-image-wrapper"]/img/@src').extract())

            cond_set_value(product, 'locale', 'en-GB')

            price = is_empty(
                response.xpath('//div[@class="price-control-wrapper"]//span[@class="value"]/text()').re(
                    FLOATING_POINT_RGEX)
            )
            product['price'] = Price(
                price=float(price),
                priceCurrency="GBP"
            ) if price else None

            brand_from_js = self.parse_brand(response)
            if brand_from_js and "Other" not in brand_from_js:
                product['brand'] = brand_from_js
            else:
                product['brand'] = guess_brand_from_first_words(product['title'])

            product["price_per_volume"], product["volume_measure"] = self._parse_volume_price(response)
            no_longer_available = response.xpath(
                '//div[@class="product-info-message with-warning-background"]/p/text()').re(
                'Sorry, this product is currently unavailable')
            product['no_longer_available'] = bool(no_longer_available)

            reseller_id = response.url.split('/')[-1]
            product['reseller_id'] = reseller_id

        return product

    @staticmethod
    def _find_between(s, first, last, offset=0):
        try:
            s = s.decode("utf-8")
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    def _clean_text(self, text):
        return re.sub("[\n\t\r]", "", text).strip()

    @catch_dictionary_exception
    @catch_json_exceptions
    def parse_brand(self, response):
        def extract_inline_json(response):
            return json.loads(response.xpath('//script[@type="application/ld+json"]//text()').extract()[0])

        return extract_inline_json(response)[2]['brand']['name']
