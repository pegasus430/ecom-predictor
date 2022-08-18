# -*- coding: utf-8 -*-
import scrapy
from scrapy.http import Request
import json
from nutrition_images.items import NutritionImagesItem
from classify_text_images import extract_features, classifier_predict_one
from urllib import splitquery
from urlparse import parse_qs

class WalmartNutritionImagesSpider(scrapy.Spider):
    name = "walmart_nutrition_images"
    allowed_domains = ["walmart.com"]
    start_urls = (
        # 'http://www.walmart.com/browse/food/snacks-cookies-chips/976759_976787?cat_id=976759_976787',
        'http://www.walmart.com/browse/health/vitamins/976760_1005863_1001553?cat_id=976760_1005863_1001553',
    )

    # how many pages to parse
    MAX_PAGES = 50

    def parse(self, response):
        urls = map(lambda u: "http://www.walmart.com" + u, response.xpath("//a[@class='js-product-title']/@href").extract())
        for url in urls:
            yield Request(url, callback=self.parse_url)

        # parse next page
        root_url, query = splitquery(response.url)
        # if we are on first page
        parsed_q = parse_qs(query)
        if 'page' not in parsed_q:
            for page in range(2, self.MAX_PAGES+1):
                next_page = root_url + "?" + query + "&page=%s" % str(page)
                yield Request(next_page, callback = self.parse)

    def parse_url(self, response):
        # response.xpath("//title//text()").extract()
        def _fix_relative_url(relative_url):
            """Fixes relative image urls by prepending
            the domain. First checks if url is relative
            """

            if not relative_url.startswith("http"):
                return "http://www.walmart.com" + relative_url
            else:
                return relative_url

        # extract json from source
        page_raw_text = response.body
        start_index = page_raw_text.find('define("product/data",') + len('define("product/data",')
        end_index = page_raw_text.find('define("athena/analytics-data"', start_index)
        end_index = page_raw_text.rfind(");", 0, end_index) - 2
        body_dict = json.loads(page_raw_text[start_index:end_index])

        pinfo_dict = body_dict

        images_carousel = []

        for item in pinfo_dict['imageAssets']:
            images_carousel.append(item['versions']['hero'])

        for image in images_carousel:
            item = NutritionImagesItem()
            item['image'] = image
            (average_slope, median_slope, average_tilt, median_tilt, median_differences, average_differences, nr_straight_lines) = \
            extract_features(image, is_url=True)
            (item['slope_average'], item['distance_average'], item['nr_lines']) = average_slope, average_differences, nr_straight_lines

            # TODO: predict with classifier
            item['is_likely_text'] = 1 if classifier_predict_one(item['image']) else 0

            yield item

