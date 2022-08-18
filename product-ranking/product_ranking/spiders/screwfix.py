# -*- coding: utf-8 -*-#
from __future__ import division, absolute_import, unicode_literals

import urlparse
import re

from scrapy.http import Request
from scrapy.log import DEBUG
from scrapy.selector import Selector

from product_ranking.items import Price
from product_ranking.items import SiteProductItem, RelatedProduct, BuyerReviews
from product_ranking.settings import ZERO_REVIEWS_VALUE
from product_ranking.spiders import BaseProductsSpider, FLOATING_POINT_RGEX
from product_ranking.spiders import cond_set, cond_set_value, dump_url_to_file


class ScrewfixProductsSpider(BaseProductsSpider):
    """Spider for screwfix.com.

    Allowed search order:
    -'relevant'
    -'pricelh'
    -'pricehl
    -'brandaz'
    -'brandza'
    -'averagestar'

    Fields is_out_of_stock, upc, limited_stock not populated.
    Fields buyer_reviews, related_products may be missed on site
    for some products.
    """
    name = 'screwfix_products'
    allowed_domains = ["screwfix.com",
                       "screwfix.ugc.bazaarvoice.com"]
    start_urls = []
    SEARCH_URL = "http://www.screwfix.com/search?search={search_term}"

    SORT_MODES = {"relevant": None,
                  "pricehl": "&sort_by=-price",
                  "pricelh": "&sort_by=price",
                  "brandaz": "&sort_by=brand",
                  "brandza": "&sort_by=-brand",
                  "averagestar": "&sort_by=-avg_rating,-num_reviews"}

    RECOMM_BASE = "http://www.screwfix.com/presentation-web-recommendations"\
                  "/jsp/recommendations/getRecommendationsRangeSlide.jsp;"\
                  "jsessionid={jsessionid}?forceRetrieveRecommendations="\
                  "true&product={product}&orientation=horizontal&scheme="\
                  "{scheme}&maxResults=28&listSize=NaN&imageType=m&"\
                  "startPosition=1&pageSize=28"

    REVS_BASE = "http://screwfix.ugc.bazaarvoice.com/5873-en_gb/{prod_id}"\
                "/reviews.djs?format=embeddedhtml&sort=rating"

    def __init__(self, sort_mode=None, *args, **kwargs):
        self.sorting = None
        if sort_mode:
            if sort_mode not in self.SORT_MODES:
                self.log('"%s" not in SORT_MODES')
                sort_mode = 'relevance'
            self.sorting = self.SORT_MODES[sort_mode]
        super(ScrewfixProductsSpider, self).__init__(
            None,
            site_name=self.allowed_domains[0],
            *args,
            **kwargs)

    def parse(self, response):
        if hasattr(self, 'sorting') and self.sorting:
            url = response.url + self.sorting
            self.sorting = None
            return Request(
                url,
                self.parse,
                meta=response.meta.copy(),
                dont_filter=True)
        else:
            return super(ScrewfixProductsSpider, self).parse(response)

    def parse_product(self, response):
        def full_url(url):
            return urlparse.urljoin(response.url, url)

        product = response.meta['product']
        # case when we parse first response of product as usual
        if not response.meta.get('after_reviews'):

            cond_set(product, 'title', response.xpath(
                "//div[@class='description']/h1[@itemprop='name']/text()"
            ).extract())

            cond_set(product, 'brand', response.xpath(
                "//div[@class='product-media-top']/"
                "img[@id='product_brand_img']/@alt"
            ).extract())

            if not product.get('brand', None):
                dump_url_to_file(response.url)

            cond_set(product, 'image_url', response.xpath(
                "//div[@class='product-media-top']/noscript"
                "/a[@id='product_image_ref']/img/@src").extract())

            price = response.xpath(
                "//p[@id='product_price']/span[@itemprop='price']"
                "/text()").re(FLOATING_POINT_RGEX)
            if price:
                product['price'] = Price(
                    price=price[0], priceCurrency='GBP')

            cond_set(product, 'description', response.xpath(
                "//div[@id='product_details_container']"
                "/div[@class='description']"
            ).extract())

            regex = "\/([a-z\d]+)(?:$|\?)"
            reseller_id = re.findall(regex, product.get('url', ''))
            reseller_id = reseller_id[0] if reseller_id else None
            cond_set_value(product, "reseller_id", reseller_id)

            stock_status = response.xpath(
                '//link[@itemprop="availability"]/@href'
            ).extract()
            if stock_status:
                if 'OutOfStock' in stock_status[0]:
                    product['is_in_store_only'] = True
                else:
                    product['is_in_store_only'] = False

            cond_set_value(product, 'locale', "en-GB")

            # try to extract some data for additional request for
            # recommendations
            jsessionid = response.xpath(
                '//input[@id="jsessionid_value_V1_MR_rr"]/@value'
            ).extract()
            product_id = response.xpath(
                '//input[@id="product_value_v1_th_rr"]/@value'
            )
            product_id = product_id or response.css(
                '[itemprop=productID]::text'
            )
            product_id = product_id.extract()
            product_id = product_id[0] if product_id else None

            # for reviews and model(may be another than for recommendations)
            prod_id = re.findall(r"'ecomm_prodid':\s'(.*)'", response.body)
            if prod_id:
                prod_id = prod_id[0].strip()
                product['model'] = prod_id
            if prod_id or product_id:
                # populate buyer reviews
                rev_url = self.REVS_BASE.format(prod_id=prod_id or product_id)
                meta = response.meta.copy()
                meta['jsessionid'] = jsessionid
                meta['product_id'] = product_id
                return Request(rev_url, callback=self.populate_buyer_reviews,
                               meta=meta)
            else:
                self.log('Could not scrape buyer reviews '
                         '(product id could not be scraped)')

        # case when we use this function second time after populating
        # buyer reviews
        else:
            jsessionid = response.meta.get('jsessionid')
            product_id = response.meta.get('product_id')

        if jsessionid and product_id:
            scheme = 'V1_MR_rr'
            url = self.generate_related_url(jsessionid, product_id, scheme)
            return Request(url, callback=self.populate_related,
                           meta={'product': product,
                                 'jsessionid': jsessionid,
                                 'product_id': product_id},
                           dont_filter=True)
        return product

    def populate_related(self, response):
        product = response.meta['product']
        prev_related = product.get('related_products')
        related = []
        if not prev_related:
            title = "more_items_to_consider"
        else:
            title = "related_products"
        box = response.xpath('//div[@class="pad homeProduct"]')
        if box:
            for item in box:
                name = item.xpath(
                    './/div[@class="cert-product-title"]/text()'
                ).extract()
                link = item.xpath('.//a/@href').extract()
                if name and link:
                    name = name[0].strip()
                    related.append(RelatedProduct(name, link[0]))
            if related and prev_related:
                prev_related[title] = related
                product['related_products'] = prev_related
            else:
                if related:
                    product['related_products'] = {title: related}
        jsessionid = response.meta.get('jsessionid')
        product_id = response.meta.get('product_id')
        if jsessionid and product_id:
            # here we make request for additional "related products" field
            scheme = 'v1_th_rr'
            url = self.generate_related_url(jsessionid, product_id, scheme)
            return Request(url, callback=self.populate_related,
                           meta={'product': product}, dont_filter=True)
        return product

    def generate_related_url(self, jsessionid, product_id, scheme):
        related_url = self.RECOMM_BASE.format(jsessionid=jsessionid[0],
                                              product=product_id[0],
                                              scheme=scheme)
        return related_url

    def _scrape_total_matches(self, response):
        total = response.xpath(
            "//h1[contains(@class,'search')]"
            "/span[@class='title-category-itemfound']/@found").extract()
        if not total:
            total = response.xpath(
                "//div/h1[contains(@class,'listing')]"
                "/span[@class='title-category-itemfound']/@found").extract()
        if total:
            try:
                return int(total[0])
            except ValueError:
                return
        return 0

    def _scrape_product_links(self, response):
        links = response.xpath(
            "//div[contains(@class,'product-list-container')]"
            "/div[@class='line']"
            "/div/div[@class='pad']/a")
        if not links:
            self.log("Found no product links.", DEBUG)
        for link in links:
            product = SiteProductItem()
            link = link.xpath('@href').extract()[0]
            yield link, product

    def _scrape_next_results_page_link(self, response):
        next_page_links = response.xpath(
            "//div[@class='listPag']"
            "/a[@id='next_page_link']/@href").extract()
        if next_page_links:
            return next_page_links[0]

    def populate_buyer_reviews(self, response):
        h = re.findall('"BVRRSourceID":(.*)}', response.body_as_unicode())
        s = Selector(text=h[0].replace('\\', ''))
        revs = response.meta.get('revs', [])
        new_revs = s.xpath(
            '//div[@id="BVRRCustomReviewRatingsContainerID"]'
            '//div[@id="BVRRRatingOverall_Review_Display"]'
            '//div[@class="BVRRRatingNormalImage"]/img/@alt'
        ).extract()
        new_revs = [rev.replace(' out of 5', '') for rev in new_revs]
        revs.extend(new_revs)
        next_page = s.xpath(
            '//span[contains(@class, "BVRRNextPage")]'
            '/a/@data-bvjsref'
        ).extract()
        if next_page:
            meta = response.meta.copy()
            meta['revs'] = revs
            return Request(next_page[0], callback=self.populate_buyer_reviews,
                           meta=meta)
        else:
            average = re.findall('"avgRating":(\d+.\d+)', response.body)
            num_of_revs = re.findall('"numReviews":(\d+)', response.body)
            response.meta['after_reviews'] = True
            product = response.meta['product']
            if average and num_of_revs:
                average = round(float(average[0][:6]), 1)
                num_of_revs = int(num_of_revs[0])
                by_star = {}
                for i in range(1, 6):
                    by_star[i] = revs.count(str(i))
                reviews = BuyerReviews(
                    num_of_reviews=num_of_revs,
                    average_rating=average,
                    rating_by_star=by_star)
                product['buyer_reviews'] = reviews
                response.meta['after_reviews'] = True
                return self.parse_product(response)
            else:
                product['buyer_reviews'] = ZERO_REVIEWS_VALUE
            return self.parse_product(response)

    def _parse_single_product(self, response):
        return self.parse_product(response)
