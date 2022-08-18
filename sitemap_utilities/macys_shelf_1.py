__author__ = 'root'

import re
import os
import time
import csv
import requests
import HTMLParser
import ast
import xml.etree.ElementTree as ET
from lxml import html, etree
import sys
import json

def _find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

macys_site_url = "http://www1.macys.com"

shelf_urls_list = ["http://www1.macys.com/catalog/index.ognc?CategoryID=89&cm_sp=c2_1111US_catsplash_men-_-row7-_-icon_pants&cm_kws_path=tasso%20elba%20quarter%20zip",
                    "http://www1.macys.com/catalog/index.ognc?CategoryID=11221&cm_sp=c2_1111US_catsplash_men-_-row7-_-icon_jeans&cm_kws_path=tasso%20elba%20quarter%20zip",
                    "http://www1.macys.com/catalog/index.ognc?CategoryID=11221&cm_sp=c2_1111US_catsplash_men-_-row7-_-icon_jeans&cm_kws_path=tasso%20elba%20quarter%20zip",
                    "http://www1.macys.com/catalog/index.ognc?CategoryID=20627&cm_sp=c2_1111US_catsplash_men-_-row7-_-icon_casual-shirts&cm_kws_path=tasso%20elba%20quarter%20zip",
                    "http://www1.macys.com/catalog/index.ognc?CategoryID=20635&cm_sp=c2_1111US_catsplash_men-_-row8-_-icon_dress-shirts&cm_kws_path=tasso%20elba%20quarter%20zip",
                    "http://www1.macys.com/catalog/index.ognc?CategoryID=4286&cm_sp=c2_1111US_catsplash_men-_-row9-_-icon_sweaters&cm_kws_path=tasso%20elba%20quarter%20zip"]
'''
    "http://www1.macys.com/shop/mens-clothing/mens-pants/Pageindex,Productsperpage/{0},40?id=89&edge=hybrid&cm_sp=c2_1111US_catsplash_men-_-row7-_-icon_pants&cm_kws_path=tasso+elba+quarter+zip",
                   "http://www1.macys.com/shop/mens-clothing/mens-jeans/Pageindex,Productsperpage/{0},40?id=11221&edge=hybrid&cm_sp=c2_1111US_catsplash_men-_-row7-_-icon_jeans&cm_kws_path=tasso+elba+quarter+zip",
                   "http://www1.macys.com/shop/mens-clothing/mens-casual-shirts/Pageindex,Productsperpage/{0},40?id=20627&edge=hybrid&cm_sp=c2_1111US_catsplash_men-_-row7-_-icon_casual-shirts&cm_kws_path=tasso+elba+quarter+zip",
                   "http://www1.macys.com/shop/mens-clothing/mens-dress-shirts/Pageindex,Productsperpage/{0},40?id=20635&edge=hybrid&cm_sp=c2_1111US_catsplash_men-_-row8-_-icon_dress-shirts&cm_kws_path=tasso+elba+quarter+zip",
                   "http://www1.macys.com/shop/mens-clothing/mens-sweaters/Pageindex,Productsperpage/{0},40?id=4286&edge=hybrid&cm_sp=c2_1111US_catsplash_men-_-row9-_-icon_sweaters&cm_kws_path=tasso+elba+quarter+zip"]
'''
url_list = []

for shelf_url in shelf_urls_list:
    try:
        print shelf_url
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)

        page_html = html.fromstring(s.get(shelf_url, headers=h, timeout=5).text)

        category_id = int(_find_between(shelf_url, "CategoryID=", "&cm_sp").strip())
        category_product_pages_count = 100000

        for page_index in range(1, category_product_pages_count):
            print "Page number:" + str(page_index)

            category_product_id_list_url = "http://www1.macys.com/catalog/category/facetedmeta?edge=hybrid&categoryId={}&facet=false&dynamicfacet=true&pageIndex={}".format(category_id, page_index)
            category_product_id_list_html = html.fromstring(requests.get(category_product_id_list_url).text)
            category_product_id_list = category_product_id_list_html.xpath("//div[@id='metaProductIds']/text()")[0]
            category_product_id_list = ast.literal_eval(category_product_id_list)
            category_id_product_id_list = [str(category_id) + "_" + str(product_id) for product_id in category_product_id_list]
            category_id_product_id_list_str = ",".join(category_id_product_id_list)
            category_products_url = "http://www1.macys.com/shop/catalog/product/thumbnail/1?edge=hybrid&limit=none&suppressColorSwatches=false&categoryId={}&ids={}".format(category_id, category_id_product_id_list_str)
            category_products_html = html.fromstring(requests.get(category_products_url).text)
            category_products_url_list = category_products_html.xpath("//div[@class='shortDescription']/a/@href")

            for index, product_url in enumerate(category_products_url_list):
                if product_url.endswith("&LinkType="):
                    category_products_url_list[index] = category_products_url_list[index][:-10]

                if not product_url.startswith(macys_site_url):
                    category_products_url_list[index] = macys_site_url + category_products_url_list[index]

            if not category_products_url_list:
                break

            url_list.extend(category_products_url_list)

        print "success"
    except:
        print "fail"

url_list = list(set(url_list))

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Macys from Shelf/"

try:
    if os.path.isfile(output_dir_path + "urls.csv"):
        csv_file = open(output_dir_path + "urls.csv", 'a+')
    else:
        csv_file = open(output_dir_path + "urls.csv", 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in url_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"


print "success"
