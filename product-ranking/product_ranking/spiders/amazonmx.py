import re

from datetime import datetime

from scrapy.conf import settings
from scrapy.log import WARNING, ERROR

from product_ranking.utils import is_empty

from product_ranking.amazon_tests import AmazonTests
from product_ranking.amazon_base_class import AmazonBaseClass
from product_ranking.spiders import FLOATING_POINT_RGEX


class AmazonProductsSpider(AmazonTests, AmazonBaseClass):

    name = 'amazonmx_products'
    allowed_domains = ["amazon.com.mx"]

    SEARCH_URL = 'https://www.amazon.com.mx/s/ref=nb_sb_noss' \
                 '?__mk_es_MX=%C3%85M%C3%85%C5%BD%C3%95%C3%91&url=search-alias%3Daps' \
                 '&field-keywords={search_term}'

    user_agent = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:35.0) Gecko'
                  '/20100101 Firefox/35.0')

    def __init__(self, *args, **kwargs):
        super(AmazonProductsSpider, self).__init__(*args, **kwargs)

        # Price currency
        self.price_currency = 'MXN'
        self.price_currency_view = '$'

        # Locale
        self.locale = 'es_MX'

        # String from html body that means there's no results ( "no results.", for example)
        self.total_match_not_found_re = 'no ha coincidido con ningun producto.'
        # Variables for total matches method (_scrape_total_matches)
        self.total_matches_re = 'de ((?:\d+,?)+) resultados'


        self.avg_review_str = 'de 5 estrellas'
        self.num_of_reviews_re = r'Mostrando .+? de ([\d,\.]+) opiniones'
        self.all_reviews_link_xpath = '//div[@id="revSum" or @id="reviewSummary"]' \
                                      '//a[contains(text(), "Ver las")]/@href'

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'

    def _format_last_br_date(self, date):
        """
        Parses date that is gotten from HTML.
        """
        months = {'enero': 'January',
                  'febrero': 'February',
                  'marzo': 'March',
                  'abril': 'April',
                  'mayo': 'May',
                  'junio': 'June',
                  'julio': 'July',
                  'agosto': 'August',
                  'septiembre': 'September',
                  'octubre': 'October',
                  'noviembre': 'November',
                  'diciembre': 'December'
                  }

        date = is_empty(
            re.findall(
                r'el (\d+ .+ \d+)',
                date
            )
        )

        if date:
            date = date.replace('de ', '')
            for key in months.keys():
                if key in date:
                    date = date.replace(key, months[key])

            d = datetime.strptime(date, '%d %B %Y')

            return d

        return None

    def _parse_no_longer_available(self, response):
        if response.xpath('//*[contains(@id, "availability")]'
                          '//*[contains(text(), "o disponible")]'):
            return True
        if response.xpath('//*[contains(@id, "outOfStock")]'
                          '//*[contains(text(), "o disponible")]'):
            return True
        if response.xpath('//*[contains(@class, "availRed")]'
                          '[contains(text(), "o disponible")]'):
            return True

    def _parse_price(self, response, add_xpath=None):
        """
        Parses product price.
        :param add_xpath: Additional xpathes, so you don't need to change base class
        """
        xpathes = '//b[@class="priceLarge"]/text()[normalize-space()] |' \
                  '//div[contains(@data-reftag,"atv_dp_bb_est_hd_movie")]' \
                  '/button/text()[normalize-space()] |' \
                  '//span[@id="priceblock_saleprice"]/text()[normalize-space()] |' \
                  '//div[@id="mocaBBRegularPrice"]/div/text()[normalize-space()] |' \
                  '//*[@id="priceblock_ourprice"][contains(@class, "a-color-price")]' \
                  '/text()[normalize-space()] |' \
                  '//*[@id="priceBlock"]/.//span[@class="priceLarge"]' \
                  '/text()[normalize-space()] |' \
                  '//*[@id="actualPriceValue"]/*[@class="priceLarge"]' \
                  '/text()[normalize-space()] |' \
                  '//*[@id="actualPriceValue"]/text()[normalize-space()] |' \
                  '//*[@id="buyNewSection"]/.//*[contains(@class, "offer-price")]' \
                  '/text()[normalize-space()] |' \
                  '//div[contains(@class, "a-box")]/div[@class="a-row"]' \
                  '/text()[normalize-space()] |' \
                  '//span[@id="priceblock_dealprice"]/text()[normalize-space()] |' \
                  '//*[contains(@class, "price3P")]/text()[normalize-space()] |' \
                  '//span[@id="ags_price_local"]/text()[normalize-space()] |' \
                  '//div[@id="olpDivId"]/.//span[@class="price"]' \
                  '/text()[normalize-space()] |' \
                  '//div[@id="buybox"]/.//span[@class="a-color-price"]' \
                  '/text()[normalize-space()] |' \
                  '//div[@id="unqualifiedBuyBox"]/.//span[@class="a-color-price"]/text() |' \
                  '//div[@id="tmmSwatches"]/.//li[contains(@class,"selected")]/./' \
                  '/span[@class="a-color-price"] |' \
                  '//div[contains(@data-reftag,"atv_dp_bb_est_sd_movie")]/button/text() |' \
                  '//span[contains(@class, "header-price")]/text() |' \
                  '//*[contains(@class, "kindle-price")]//*[contains(@class, "a-color-price")]/text()'

        if add_xpath:
            xpathes += ' |' + add_xpath

        price_currency_view = getattr(self, 'price_currency_view', None)
        price_currency = getattr(self, 'price_currency', None)

        if not price_currency and not price_currency_view:
            self.log('Either price_currency or price_currency_view '
                     'is not defined. Or both.', ERROR)
            return None

        price_currency_view = unicode(self.price_currency_view)
        price = response.xpath(xpathes).extract()
        # extract 'used' price only if there is no 'normal' price, because order of xpathes
        # may be undefined (in document order)
        if not price:
            price = response.xpath(
                '//div[@id="usedBuySection"]//span[contains(@class, "a-color-price")]/text()'
            ).extract()
        # TODO fix properly
        if not price:
            price = response.xpath(
                './/*[contains(text(), "Used & new")]/../text()'
            ).extract()
            if price:
                price = [price[0].split('from')[-1]]
        price = self._is_empty([p for p in price if p.strip()], '')

        if price:
            if price_currency_view not in price:
                price = '0.00'
                if 'FREE' not in price:
                    self.log('Currency symbol not recognized: %s' % response.url,
                             level=WARNING)
            else:
                price = self._is_empty(
                    re.findall(
                        FLOATING_POINT_RGEX,
                        price), '0.00'
                )
        else:
            price = '0.00'

        price = self._fix_dots_commas(price)

        # Price is parsed in different format:
        # 1,235.00 --> 1235.00
        # 2,99 --> 2.99
        price = (price[:-3] + price[-3:].replace(',', '.')).replace(',', '')
        price = round(float(price), 2)

        # try to scrape the price from another place
        if price == 0.0:
            price2 = re.search('\|([\d\.]+)\|baseItem"}', response.body)
            if price2:
                price2 = price2.group(1)
                try:
                    price2 = float(price2)
                    price = price2
                except:
                    pass

        if price == 0.0:
            _price = response.css('#alohaPricingWidget .a-color-price ::text').extract()
            if _price:
                _price = ''.join([c for c in _price[0].strip() if c.isdigit() or c == '.'])
                try:
                    price = float(_price)
                except:
                    pass

        if price == 0.0:
            # "add to cart first" price?
            _price = re.search(r'asin\-metadata.{3,100}?price.{3,100}?([\d\.]+)',
                               response.body_as_unicode())
            if _price:
                _price = _price.group(1)
                try:
                    _price = float(_price)
                    price = _price
                except ValueError:
                    pass

        return price

    def _parse_price_original(self, response, add_xpath=None):
        """
        Parses product's original price.
        :param add_xpath: Additional xpathes, so you don't need to change base class
        """
        xpathes = '//*[@id="price"]/.//*[contains(@class, "a-text-strike")]' \
                  '/text() |' \
                  '//*[@id="buybox"]/.//*[contains(@class, "a-text-strike")]' \
                  '/text()'

        if add_xpath:
            xpathes += ' |' + add_xpath

        price_original = response.xpath(xpathes).re(FLOATING_POINT_RGEX)
        if price_original:
            return float(price_original[0].replace(',', ''))

    def _has_captcha(self, response):
        is_captcha = response.xpath('.//*[contains(text(), "Type the characters you see in this image")]')
        if is_captcha:
            self.log("Detected captcha, using captchabreaker", level=WARNING)
            return True

        return False

    def _scrape_results_per_page(self, response):
        num = response.xpath(
            '//*[@id="s-result-count"]/text()').re('1 a (\d+) de')
        if num:
            return int(num[0])
        else:
            num = response.xpath(
                '//*[@id="s-result-count"]/text()').re('(\d+) resultados')
            if num:
                return int(num[0])

        return None
