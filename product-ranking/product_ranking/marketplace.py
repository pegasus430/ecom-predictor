import re
import os
from os.path import isfile, join
import urlparse

from PIL import Image
from pytesseract import image_to_string

from scrapy.http import Request
from product_ranking.spiders import FLOATING_POINT_RGEX


REPLACE_COMMA_WITH_DOT = False  # it's ok to use globals for the whole process


class Amazon_marketplace(object):
    """Scrape marketplace sellers for Amazons sites
    """

    cache = {}
    called_class = None

    currencys = {
        "amazon.ca": "CAD",
        "amazon.com": "USD",
        "amazon.co.uk": "GBP",
        "amazon.co.jp": "JPY",
        "amazon.cn": "CNY",
        "amazon.fr": "EUR",
        "amazon.de": "EUR"
    }

    IMG_FOLDER = "amazon_marketplace/"
    NEW_IMG_FOLDER = "amazon_marketplace/new/"

    def __init__(self, *args, **kwargs):
        if args:
            self.called_class = args[0]
        elif not self.called_class:
            import inspect
            stack = inspect.stack()
            self.called_class = stack[1][0].f_locals["self"].__class__()
        self.is_empty = lambda x, y=None: x[0] if x else y

    def parse_marketplace(self, response, replace_comma_with_dot=False):
        global REPLACE_COMMA_WITH_DOT

        if replace_comma_with_dot:
            REPLACE_COMMA_WITH_DOT = True

        if os.path.exists('/tmp/stop_marketplaces'):  # only for speed-up
            return response.meta['product']

        next_req = response.meta.get("next_req", None)

        if self.called_class._has_captcha(response):
            return self.called_class._handle_captcha(
                response, self.parse_marketplace)

        product = response.meta["product"]

        name_links = []

        marketplaces = response.meta.get("marketplaces", [])

        for seller in response.xpath(
            '//div[contains(@class, "a-section")]/' \
            'div[contains(@class, "a-row a-spacing-mini olpOffer")]'):

            price = self.is_empty(seller.xpath(
                'div[contains(@class, "a-column")]' \
                '/span[contains(@class, "price")]/text()'
            ).re(FLOATING_POINT_RGEX), 0)
            if replace_comma_with_dot or REPLACE_COMMA_WITH_DOT:
                price = price.replace(',', '.').strip()

            name = self.is_empty(seller.xpath(
                'div/p[contains(@class, "Name")]/span/a/text()').extract(), "")

            condition = self.is_empty(
                seller.xpath(
                    './/*[contains(@class, "Condition")]/text()').extract()
                ,
                ""
            )
            if not 'new' in condition.lower():
                if not 'neu' in condition.lower():
                    continue

            currencyKey = self.set_seller_amazon()
            priceCurrency = "USD"
            if currencyKey in self.currencys:
                priceCurrency = self.currencys[currencyKey]

            if not name.strip():
                name = self.is_empty(seller.xpath(
                    'div/p[2]/span[2]/text()').extract(), "")
                name = self.is_empty(re.findall("www.([^\)]*)", name), "")

            if not name.strip():
                name = self.is_empty(seller.xpath(
                    ".//p[contains(@class, 'Name')]/span[last()]/text()"
                ).extract(), "")
                name = self.is_empty(re.findall("\((.*)\)", name), "")

            if not name.strip():
                get_name_link, key = self.get_hash_and_link(seller)
                if get_name_link:
                    link = "link"
                    if not key:
                        link = "img_link"
                    name_links.append({
                        link: get_name_link,
                        'price': float(price.price),
                        'currency': price.priceCurrency,
                        "name": key
                    })
            else:
                marketplaces.append({
                    'price': float(price.price),
                    'currency': price.priceCurrency,
                    'name': name.strip()
                })

        next_link = self.is_empty(response.xpath(
            "//ul[contains(@class, 'a-pagination')]" \
            "/li[contains(@class, 'a-last')]/a/@href"
        ).extract())
        if next_link:
            next_link = next_link.replace("&freeShipping=1", "")

        if name_links:
            return self.get_names(
                name_links,
                marketplaces,
                (self.parse_marketplace, next_link, product, next_req)
            )

        if next_link:
            meta = {"product": product, "marketplaces": marketplaces}
            return Request(
                url=urlparse.urljoin(response.url, next_link),
                callback=self.parse_marketplace,
                meta=meta,
                dont_filter=True,
            )
        if marketplaces:
            product["marketplace"] = marketplaces
        return product

    def get_hash_and_link(self, seller, expression="/shops/(.*)/"):
        key = None
        link = self.is_empty(seller.xpath(
                    'div/p[contains(@class, "Name")]/a/@href').extract())
        if not link:
            img_link = self.is_empty(seller.xpath(
                'div/p[contains(@class, "Name")]/img/@src').extract())
            if img_link:
                return Request(url=img_link), None
        else:

            key = self.is_empty(re.findall("/shops/(.*)/", link))
        if not link:
            return None, None
        return Request(url=link), key

    def get_seller_from_title(self, title):
        regexp = ["(.*)\s@\sAmazon.", "(.*)\:\s+Amazon"]
        for i in regexp:
            name = self.is_empty(re.findall(
                i,
                title
            ))
            if name:
                break
        return unicode(name) or []

    def get_names(self, name_links, marketplaces, callback):
        cr = name_links.pop(0)

        if cr["name"] in self.cache:
            cr["name"] = self.cache[cr["name"]]
            del cr["link"]
            marketplaces.append(cr)
            if not name_links:
                return self.request_or_product(callback, marketplaces)
            return self.get_names(name_links, marketplaces, callback)

        meta = {
            "marketplaces": marketplaces,
            "name_links": name_links,
            "cr": cr,
            "callback": callback
        }

        link = cr.get("link")
        callback = self.add_to_marketplaces
        if cr.get("img_link"):
            link = cr.get("img_link")
            callback = self.img_parse
        return link.replace(callback=callback).replace(
            meta=meta).replace(dont_filter=True)

    def add_to_marketplaces(self, response):
        if self.called_class._has_captcha(response):
            return self.called_class._handle_captcha(response, self.add_to_marketplaces)

        marketplaces, name_links, callback, cr = self.get_data_from_meta(response)
        key = cr["name"]

        cr["name"] = self.is_empty(response.xpath(
            "//h2/a/img/@alt | //div[@id='aag_header']/h1/text()"
        ).extract())
        if not cr["name"]:
            title = self.is_empty(response.xpath("//title/text()").extract())
            cr[str("name")] = self.get_seller_from_title(title)
        del cr["link"]

        self.cache[key] = cr["name"]

        marketplaces.append(cr)

        if name_links:
            return self.get_names(name_links, marketplaces, callback)
        return self.request_or_product(callback, marketplaces)

    def img_parse(self, response):
        marketplaces, name_links, callback, cr = self.get_data_from_meta(response)

        file_name = self.is_empty(re.findall("([^\/]*)$", response.url))
        file_path = self.NEW_IMG_FOLDER + file_name
        self.save_file(file_path, response.body)
        files = [f for f in os.listdir(self.IMG_FOLDER) if isfile(join(self.IMG_FOLDER,f))]
        is_already_have = False
        for fl in files:
            if self.compare_images(file_path, self.IMG_FOLDER+fl):
                cr["name"] = self.set_seller_amazon()
                is_already_have = True
                break

        path_to = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        ) + '/'

        if not is_already_have:
            if "amazon" in self.get_image_text(file_path):
                cr["name"] = self.set_seller_amazon()
                os.rename(
                    self.NEW_IMG_FOLDER + file_name,
                    self.IMG_FOLDER + file_name
                )

        if isfile(path_to + self.NEW_IMG_FOLDER + file_name):
            os.remove(self.NEW_IMG_FOLDER + file_name)

        if not cr.get("name"):
            cr["name"] = []

        del cr["img_link"]
        marketplaces.append(cr)

        if name_links:
            return self.get_names(name_links, marketplaces, callback)
        return self.request_or_product(callback, marketplaces)

    def request_or_product(self, callback, marketplaces):
        function, url, product, next_req = callback
        if url:
            return Request(
                url="http://" + self.called_class.allowed_domains[0] + url,
                callback=function,
                meta={"marketplaces": marketplaces, "product": product},
                dont_filter=True
            )
        if marketplaces:
            product["marketplace"] = marketplaces
        return self.called_class.exit_point(product, next_req)

    def get_image_text(self, img):
        image = Image.open(img)
        return image_to_string(image)

    def compare_images(self, img, img2):
        h1 = Image.open(img).histogram()
        h2 = Image.open(img2).histogram()
        return h1 == h2

    def save_file(self, file_name, data):
        dir_ = os.path.dirname(file_name)
        if not os.path.exists(dir_):
            os.makedirs(dir_)
        f = open(file_name, "wb")
        f.write(data)
        f.close()

    def get_data_from_meta(self, response):
        marketplaces = response.meta["marketplaces"]
        name_links = response.meta["name_links"]
        callback = response.meta["callback"]
        cr = response.meta["cr"]

        return (marketplaces, name_links, callback, cr)

    def set_seller_amazon(self):
        return self.called_class.allowed_domains[0].replace(
                    "www.", "").replace("/", "")

    def get_price_from_main_response(self, response, product):
        seller = None
        seller = response.xpath(
            '//div[@id="kindle-av-div"]/div[@class="buying"]/b/text() |'
            '//div[@class="buying"]/b/text()'
        ).extract()

        if not seller:
            seller_all = response.xpath('//div[@class="buying"]/b/a')#tr/td/
            seller = seller_all.xpath('text()').extract()
        if not seller:
            seller = self.is_empty(response.xpath(
                '//div[@id="merchant-info"]/text()').extract())
            if seller:
                seller = re.findall("sold by\s+(.*)\s+in", seller)
        if not seller:
            seller = response.xpath(
                '//div[@id="merchant-info"]/a[1]/text()').extract()
        #seller in description as text
        if not seller:
            seller = response.xpath(
                '//li[@id="sold-by-merchant"]/text()'
            ).extract()
            seller = ''.join(seller).strip()
        #simple text seller
        if not seller:
            seller = response.xpath('//div[@id="merchant-info"]/text()').extract()
            if seller:
                seller = re.findall("sold by([^\.]*)", seller[0])
            if seller and seller[0].strip() == "Amazon":
                    seller[0] = self.set_seller_amazon()
        if not seller:
            seller_all = response.xpath('//div[@id="usedbuyBox"]/div/div/a')
            seller = seller_all.xpath('text()').extract()

        if not seller:
            seller = response.xpath("//span[contains(@id, 'soldby')]/text()").extract()

        if seller and isinstance(seller, list):
            seller = seller[0].strip()

        if seller:
            _price = product.get('price', 0)
            if _price:
                _currency = _price.priceCurrency
                _price = float(_price.price)
            else:
                _price = None
                _currency = None
            product["marketplace"] = [
                {
                    "name": seller,
                    "price": _price,
                    'currency': _currency
                }
            ]
