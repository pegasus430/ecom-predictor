import json
import re
import traceback
import urlparse

from scrapy import Request
from scrapy.conf import settings
from urllib import urlencode

from product_ranking.br_bazaarvoice_api_script import BuyerReviewsBazaarApi
from product_ranking.guess_brand import guess_brand_from_first_words
from product_ranking.items import BuyerReviews, Price, SiteProductItem
from product_ranking.spiders import (BaseProductsSpider, cond_set_value,
                                     FormatterWithDefaults)
from spiders_shared_code.nike_variants import NikeVariants


class NikeProductSpider(BaseProductsSpider):
    name = 'nike_products'
    allowed_domains = ["nike.com"]
    handle_httpstatus_list = [404, 410]

    SEARCH_URL = 'http://store.nike.com/html-services/gridwallData?' \
                 'country=US&lang_locale=en_US&sl={search_term}' \
                 '&pn={page_num}&sortOrder={sort_mode}'

    REVIEW_URL = "http://nike.ugc.bazaarvoice.com/9191-en_us/{product_id}" \
                 "/reviews.djs?format=embeddedhtml"

    SORT_MODES = {
        'default': '',
        'newest': 'publishdate|desc',
        'rating': 'overallrating|desc',
        'price_asc': 'finalprice|asc',
        'price_desc': 'finalprice|desc',
    }

    def __init__(self, sort_mode='default', *args, **kwargs):
        settings.overrides['USE_PROXIES'] = True
        self.br = BuyerReviewsBazaarApi(called_class=self)

        super(NikeProductSpider, self).__init__(
            url_formatter=FormatterWithDefaults(
                page_num=1, sort_mode=self.SORT_MODES[sort_mode.lower()]
            ),
            *args, **kwargs)
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                          'Chrome/64.0.3282.167 Safari/537.36'

    def _parse_single_product(self, response):
        return self.parse_product(response)

    def parse(self, response):
        try:
            data = json.loads(response.body_as_unicode())
        except:
            data = {}
        redirect = data.get('keywordRedirect')

        if redirect:
            # removing sl query param and making correct gridwallPath
            meta = dict((k, v) for k, v in response.meta.iteritems()
                if k in ['remaining', 'search_term'])
            search_hash = redirect.split('/')[-1]
            url_parts = list(urlparse.urlparse(response.url))
            query = dict(urlparse.parse_qsl(url_parts[4]))
            search_term = query.get('sl')
            if search_term:
                del query['sl']
                query['gridwallPath'] = search_term + '/' + search_hash
            else:
                gpath = query.get('gridwallPath', '').split('/')
                query['gridwallPath'] = gpath[0] + '/' + search_hash

            url_parts[4] = urlencode(query)
            url = urlparse.urlunparse(url_parts)
            return Request(url, meta=meta)

        return super(NikeProductSpider, self).parse(response)

    def parse_product(self, response):
        product = response.meta.get('product')

        is_new_layout = False
        try:
            json_str = response.xpath(
                    '//script[contains(@id, "product-data")]/text()|'
                    '//script[@data-name="pdpData"]/text()'
                ).extract()
            if json_str:
                data = json.loads(json_str[0])
            else:
                is_new_layout = True
                json_str = re.search('(?<=INITIAL_REDUX_STATE=)(.*)(?=;window)', response.body)
                data = json.loads(json_str.group())
        except:
            self.log('JSON not found or invalid JSON: {}'.format(traceback.format_exc()))
            product['not_found'] = True
            return product

        if is_new_layout:
            product = self._parse_new_layout(response, data, product)
        else:
            product = self._parse_old_layout(response, data, product)

        return product

    def _parse_new_layout(self, response, data, product):
        def parse_price(_product_details):
            price = _product_details.get('fullPrice')
            if price:
                return Price(_product_details.get('currency', 'USD'), price)

        def is_in_stock(_product_details):
            return _product_details.get('state') == 'IN_STOCK'

        def parse_variants():
            variants = []
            for style_id, variant in data.get('Threads', {}).get('products', {}).iteritems():
                variant_item = {}
                properties = {"color": variant.get("colorDescription")}
                variant_item["properties"] = properties
                variant_item["price"] = variant.get('fullPrice')  # Price()?
                variant_item["in_stock"] = is_in_stock(variant)
                variant_item["url"] = data.get('App', {}).get('request', {}).get('URLS', {}) \
                                          .get('withoutStyleColor', '') + '/' + style_id
                variant_item["selected"] = style_id == selected_style
                variants.append(variant_item)

        def parse_reviews():
            # TODO: calc. rating_by_star. It is NA in new layout (yet?)
            reviews = data.get('reviews', {})
            num_of_reviews = reviews.get('total')
            average_rating = reviews.get('averageRating')
            try:
                buyer_reviews = BuyerReviews(int(num_of_reviews), float(average_rating), {})
                return buyer_reviews
            except ValueError:
                self.log('Unable to parse BuyerReviews: {}'.format(traceback.format_exc()))

        selected_style = response.xpath('//*[contains(@class, "description-preview__style-color")]//text()').extract()
        if selected_style:
            selected_style = selected_style[0].split(' ')[-1]

        product_details = data.get('Threads', {}).get('products', {}).get(selected_style, {})

        cond_set_value(product, 'title', product_details.get('title'))

        cond_set_value(product, 'locale', product_details.get('langLocale', 'en_US'))

        cond_set_value(product, 'brand', product_details.get('brand'))

        cond_set_value(product, 'is_out_of_stock', not is_in_stock(product_details))

        image_url = response.xpath('/html/head/meta[@property="og:image"]//@content').extract()
        cond_set_value(product, 'image_url', image_url[0] if image_url else None)

        sku = product_details.get('selectedSku')
        cond_set_value(product, 'sku', sku)

        reseller_id = product_details.get('productId')
        cond_set_value(product, "reseller_id", reseller_id)

        cond_set_value(product, 'price', parse_price(product_details))

        cond_set_value(product, 'variants', parse_variants())

        cond_set_value(product, 'buyer_reviews', parse_reviews())

        return product

    def _parse_old_layout(self, response, data, product):
        title = data.get('productTitle')
        cond_set_value(product, 'title', title)

        locale = data.get('chat', {}).get('langVariant', 'en_US')
        cond_set_value(product, 'locale', locale)

        brand = data.get('chat', {}).get('brand')
        if not brand and title:
            brand = guess_brand_from_first_words(title)
        cond_set_value(product, 'brand', brand)

        is_out_of_stock = not data.get('inStock', True)
        cond_set_value(product, 'is_out_of_stock', is_out_of_stock)

        images = data.get('imagesHeroZoom')
        image_url = images[0] if images else None
        cond_set_value(product, 'image_url', image_url)

        sku = data.get('chat', {}).get('productId')
        cond_set_value(product, 'sku', sku)

        reseller_id = data.get('trackingData', {}).get('product', {}).get('productId')
        cond_set_value(product, "reseller_id", reseller_id)

        price = data.get('rawPrice')
        if price:
            currency = data.get('crossSellConfiguration', {}).get('currency', 'USD')
            cond_set_value(product, 'price', Price(currency, price))

        nv = NikeVariants()
        nv.setupSC(response)
        try:
            product['variants'] = nv._variants()
        except:  # "/product/" urls that are non-standard and not supported (yet)?
            pass

        pid = data.get('desktopBazaarVoiceConfiguration', {}).get('productId')
        if pid:
            return Request(
                url=self.REVIEW_URL.format(product_id=pid),
                dont_filter=True,
                callback=self.parse_buyer_reviews,
                meta={'product': product}
            )

        return product

    def parse_buyer_reviews(self, response):
        product = response.meta['product']
        buyer_reviews_per_page = self.br.parse_buyer_reviews_per_page(response)
        product['buyer_reviews'] = BuyerReviews(**buyer_reviews_per_page)
        return product

    def _scrape_total_matches(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            total_matches = data['navigation']['totalRecords']
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()))
            total_matches = 0

        return total_matches

    def _scrape_product_links(self, response):
        try:
            data = json.loads(response.body_as_unicode())
            products = data['sections'][0].get('products', [])
        except:
            self.log('Invalid JSON: {}'.format(traceback.format_exc()))
            products = []

        for product in products:
            yield product.get('pdpUrl'), SiteProductItem()

    def _scrape_next_results_page_link(self, response):
        totals = response.meta.get('total_matches')
        per_page = response.meta.get('products_per_page')
        current_page = re.search('pn=(\d+)', response.url)
        current_page = int(current_page.group(1)) if current_page else None
        if not current_page or not per_page or current_page >= totals / float(per_page):
            return None
        url = re.sub('(pn)=(\d+)', r'\1={}'.format(current_page + 1), response.url)
        return url
