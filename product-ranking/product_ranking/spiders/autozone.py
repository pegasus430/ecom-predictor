from __future__ import division, absolute_import, unicode_literals

import re
import urlparse

from scrapy.log import WARNING
from scrapy.conf import settings
from scrapy.http import Request, FormRequest

from product_ranking.utils import is_empty
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.items import SiteProductItem, Price, BuyerReviews
from product_ranking.spiders import BaseProductsSpider, FormatterWithDefaults, \
    cond_set, cond_set_value, FLOATING_POINT_RGEX


class AutozoneProductsSpider(BaseProductsSpider):
    name = 'autozone_products'
    allowed_domains = ["autozone.com", "api.bazaarvoice.com"]
    start_urls = []

    SEARCH_URL = "http://www.autozone.com/searchresult?searchText={search_term}" \
                 "&vehicleSetFromSearch=false&keywords={search_term}"

    SEARCH_SORT = {
        'best_match': '',
        'best_selling': 'performanceRank%7c0',
        'new_to_store': 'newToStoreDate%7c1',
        'a-z': 'Brand+Line%7c0%7c%7cname%7c0%7c%7cgroupDistinction%7c0',
        'z-a': 'Brand+Line%7c1%7c%7cname%7c1%7c%7cgroupDistinction%7c1',
        'customer_rating': 'avgRating%7c1%7c%7cratingCount%7c1',
        'low_to_high_price': 'price%7c0',
        'high_to_low_price': 'price%7c1',
        'saving_dollars': 'savingsAmount%7c1',
        'saving_percent': 'savingsPercent%7c1',
    }

    REVIEW_URL = 'https://pluck.autozone.com/ver1.0/sys/jsonp?' \
                 'widget_path=pluck/reviews/rollup&' \
                 'plckReviewOnKey={product_id}&' \
                 'plckReviewOnKeyType=article&' \
                 'plckReviewShowAttributes=true&' \
                 'plckDiscoveryCategories=&' \
                 'plckArticleUrl={product_url}&' \
                 'clientUrl={product_url}'

    cookies = {
        'preferedstore': '5425',
        'NSC_bvupapof.dpn': 'ffffffffaace1a5745525d5f4f58455e445a4a423660',
    }

    handle_httpstatus_list = [405]

    def __init__(self, search_sort='best_match', *args, **kwargs):
        if "search_modes" in kwargs:
            search_sort = kwargs["search_modes"]
        super(AutozoneProductsSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                search_sort=self.SEARCH_SORT[search_sort]
            ),
            site_name="autozone.com",
            *args, **kwargs)

        middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        middlewares['product_ranking.custom_middlewares.TunnelRetryMiddleware'] = 2
        middlewares['product_ranking.middlewares.twocaptcha.TwoCaptchaMiddleware'] = 500
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'product_ranking.utils.TLSFlexibleContextFactory'
        settings.overrides['CAPTCHA_SOLVER'] = 'product_ranking.middlewares.captcha.solvers.funcaptcha.FunCaptchaSolver'

        retry_codes = settings.get('RETRY_HTTP_CODES')
        retry_codes = [c for c in retry_codes if c not in self.handle_httpstatus_list]
        settings.overrides['RETRY_HTTP_CODES'] = retry_codes

        self.user_agent = 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'

    def is_captcha_page(self, response):
        captcha = response.xpath('//form[@id="distilCaptchaForm"]')
        return bool(captcha)

    def get_captcha_key(self, response):
        pk = response.xpath('//div[@id="funcaptcha"]/@data-pkey').extract()
        if not pk:
            pk = response.xpath('//iframe/@src').extract()
            if pk:
                pk = pk[0].split("/?pkey=")
                return pk[-1] if pk else None
        return pk[0] if pk else None

    def get_captcha_formaction(self, response):
        url = response.xpath('//form[@id="distilCaptchaForm"]/@action').extract()
        return urlparse.urljoin(response.url, url[0]) if url else None

    def get_captcha_form(self, url, solution, callback):
        return FormRequest(
            url,
            formdata={
                "fc-token": solution
            },
            callback=callback
        )

    def start_requests(self):
        for request in super(AutozoneProductsSpider, self).start_requests():
            if self.searchterms:
                request = request.replace(dont_filter=True, callback=self._start_requests)
            else:
                handle_httpstatus_list = [404, 503, 500]
                meta = request.meta.copy()
                meta['handle_httpstatus_list'] = handle_httpstatus_list
                request = request.replace(meta=meta)
            yield request

    def _get_products(self, response):
        for request in super(AutozoneProductsSpider, self)._get_products(response):
            yield request.replace(cookies=self.cookies, dont_filter=True)

    def parse_redirect(self, response):
        if 'Search Results for:' in response.body_as_unicode():
            return self.parse(response)
        else:
            prod = SiteProductItem()
            prod['url'] = response.url
            prod['search_term'] = response.meta['search_term']
            prod['total_matches'] = 1
            response.meta['product'] = prod
            return self.parse_product(response)

    def _start_requests(self, response):
        items = response.xpath('//div[contains(@class, "searchResult")]')
        meta = response.meta.copy()

        category_list = meta.get('category_list', [])
        index = meta.get('index', 0)
        count = meta.get('count', 0)

        if not items:
            self.log("Found no  product links.", WARNING)

        next_page_link = response.xpath('//a[@id="next"]/@href').extract()

        meta['next_page_link'] = urlparse.urljoin(response.url, next_page_link[0]) if next_page_link else None

        for item in items:
            link = is_empty(item.xpath('.//a/@href').extract())
            category_list.append(urlparse.urljoin(response.url, link))
        meta['category_list'] = category_list

        count += len(items)
        meta['count'] = count

        if len(category_list) > index:
            return Request(category_list[index],
                           callback=self._parse_total,
                           meta=meta,
                           dont_filter=True)

    def _parse_total(self, response):
        meta = response.meta.copy()
        total = response.xpath('//div[@id="resultsFilters"]/form/div/text()').extract()
        if len(total) >= 3:
            total = re.search('(\d+)', total[2], re.DOTALL)
        else:
            total = None
        total_matches = response.meta.get('total_matches', 0)
        if total:
            total_matches += int(total.group(1))
        meta['total_matches'] = total_matches

        count = meta.get('count', 0)
        index = meta.get('index', 0)
        index += 1
        meta['index'] = index
        next_page_link = meta['next_page_link']
        category_list = meta['category_list']

        if index < count:
            return Request(category_list[index], callback=self._parse_total, meta=meta, dont_filter=True)

        if index >= count and next_page_link:
            return Request(next_page_link, callback=self._start_requests, meta=meta, dont_filter=True)

        if index >= count and not next_page_link:
            meta['index'] = 0
            return Request(category_list[0], meta=meta, dont_filter=True)

    def parse_product(self, response):
        product = response.meta['product']
        reqs = []

        if response.status == 404:
            product['not_found'] = True
            return product

        cond_set(product, 'title', response.xpath(
            "//h1[@property='name']//text()").extract(), lambda y: y.strip())

        cond_set(product, 'image_url', response.xpath(
            "//div[@class='mainImage']//img[@id='mainimage']/@src").extract())

        price = response.xpath("//td[@class='price base-price']").extract()
        if price:
            if not '$' in price[0]:
                self.log('Unknown currency at' % response.url)
            else:
                product['price'] = Price(
                    price=price[0].replace(',', '').replace(
                        '$', '').strip(),
                    priceCurrency='USD'
                )

        cond_set_value(product,
                       'description',
                       response.xpath("//div[@id='features']").extract(),
                       conv=''.join)

        brand = 'Autozone'
        cond_set_value(product, 'brand', brand)

        categories = response.xpath(
            '//ul[contains(@class, "breadcrumb")]/li/a/text()'
        ).extract()
        if categories:
            cond_set_value(product, 'categories', categories[1:])
            cond_set_value(product, 'department', categories[-1])

        is_out_of_stock = response.xpath(
            '//div[contains(@class, "in-stock")]/text()').extract()
        if is_out_of_stock:
            if 'in stock' in is_out_of_stock[0].lower():
                is_out_of_stock = False
            else:
                is_out_of_stock = True
        else:
            is_out_of_stock = True
        cond_set(product, 'is_out_of_stock', (is_out_of_stock,))

        product['locale'] = "en-US"

        # Buyer reviews
        product_id = response.xpath("//div[@id='product-data']/div[@id='SkuId']/text()").extract()
        if len(product_id) > 0:
            product_id = product_id[0].strip()
            review_url = self.REVIEW_URL.format(product_id=product_id, product_url=response.url)
            reqs.append(Request(review_url,
                                self._parse_review,
                                meta=response.meta,
                                dont_filter=True))

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def send_next_request(self, reqs, response):
        """
        Helps to handle several requests
        """
        req = reqs.pop(0)
        new_meta = response.meta.copy()
        if reqs:
            new_meta["reqs"] = reqs
        return req.replace(meta=new_meta)

    def _parse_review(self, response):
        product = response.meta['product']
        reqs = response.meta.get('reqs', [])

        arr = response.xpath(
            "//div[contains(@class,'pluck-dialog-middle')]"
            "//span[contains(@class,'pluck-review-full-attributes-name-post')]/text()"
        ).extract()
        review_list = []
        if len(arr) >= 5:
            review_list = [[5 - i, int(re.findall('\d+', mark)[0])]
                           for i, mark in enumerate(arr)]
        if review_list:
            # average score
            sum = 0
            cnt = 0
            for i, review in review_list:
                sum += review * i
                cnt += review
            if cnt > 0:
                average_rating = float(sum) / cnt
            else:
                average_rating = 0.0
            # number of reviews
            num_of_reviews = 0
            for i, review in review_list:
                num_of_reviews += review
        else:
            pass

        rating_by_star = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for i, review in review_list:
            rating_by_star[i] = review
        if average_rating and num_of_reviews:
            product["buyer_reviews"] = BuyerReviews(
                num_of_reviews=int(num_of_reviews),
                average_rating=float(average_rating),
                rating_by_star=rating_by_star,
            )
        else:
            product["buyer_reviews"] = ZERO_REVIEWS_VALUE

        if reqs:
            return self.send_next_request(reqs, response)

        return product

    def _scrape_product_links(self, response):
        items = response.xpath('//div[@class="productImageContainer"]/a[@class="prodImg"]/@href').extract()

        for item in items:
            link = urlparse.urljoin(response.url, item)
            yield link, SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        meta = response.meta.copy()
        next_link = is_empty(response.xpath('//a[@id="next"]/@href').extract())
        next_link = urlparse.urljoin(response.url, next_link) if next_link else None
        index = meta.get('index', 0)
        category_list = meta.get('category_list', [])

        if not next_link and (index + 1) < len(category_list):
            next_link = category_list[index+1]
            index += 1
            meta['index'] = index

        return Request(next_link, meta=meta, dont_filter=True) if next_link else None

    def _parse_single_product(self, response):
        return self.parse_product(response)