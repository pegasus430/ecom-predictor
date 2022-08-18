# -*- coding: utf-8 -*-
import scrapy
from scrapy.http import Request
from urllib import splitquery
from urlparse import parse_qs
from generate_nutrition_from_text import screenshot_element
from nutrition_images.items import ScreenshotItem
import re

class WalmartGenerateImagesSpider(scrapy.Spider):
    name = "walmart_generate_images"
    allowed_domains = ["www.walmart.com"]
    start_urls = (
        'http://www.walmart.com/browse/food/976759?cat_id=976759',
    )

    # how many pages to parse
    MAX_PAGES = 1

    def parse(self, response):
        urls = map(lambda u: "http://www.walmart.com" + u, response.xpath("//a[@class='js-product-title']/@href").extract())
        screenshots = screenshot_element(urls, 
            ("//div[@class='nutrition-section']", "//div[@class='NutFactsSIPT']"), 
            "nutrition", "/home/ana/code/tmtext/nutrition_info_images/nutrition_facts_screenshots/")

        # extract the nutrition text as well
        for screenshot in screenshots:
            yield Request(url = screenshot['url'], callback=self.parse_product, meta={'screenshot' : screenshot['screenshot']})

        # parse next page
        root_url, query = splitquery(response.url)
        # if we are on first page
        parsed_q = parse_qs(query)
        if 'page' not in parsed_q:
            for page in range(2, self.MAX_PAGES+1):
                next_page = root_url + "?" + query + "&page=%s" % str(page)
                yield Request(next_page, callback = self.parse)

    def parse_product(self, response):
        screenshot_path = response.meta['screenshot']

        res=[]
        nutr=response.xpath("//div[@class='nutrition-section']//div[@class='serving']//div/text()").extract()
        for i, n in enumerate(nutr):
            nt = n
            if i == 0:
                res.append([nt[0:13].strip(),nt[13:].strip()])
            if i == 1:
                res.append([nt[0:22].strip(),nt[22:].strip()])
        nutr=response.xpath("//div[@class='nutrition-section']//table[contains(@class,'table')]//tr")
        _digits = re.compile('\d')
        for i, n in enumerate(nutr):
            pr = n.xpath(".//*[self::th or self::td]//text()").extract()[0]
            if len(pr)>0 and pr[0].find("B6") < 0:
                m = _digits.search(pr[0])
                if m != None and m.start() > 1:
                    p0 = pr[0][0:m.start()-1]
                    p1 = pr[0][m.start()-1:]
                    pr[0] = p1.strip()
                    pr.insert(0,p0.strip())
            if len(pr)==2 :
                res.append(pr)
            elif len(pr)==3 and pr[2].strip()!="":
                res.append([pr[0].strip(),{"absolute":pr[1].strip(),"relative":pr[2].strip()}])
            elif len(pr) == 3 and pr[2].strip() == "":
                res.append([pr[0].strip(),pr[1].strip()])
        if len(res) > 0:
            item = ScreenshotItem()
            item['text'] = res
            item['path'] = screenshot_path

            return item



