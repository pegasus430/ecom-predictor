__author__ = 'diogo'

import re
import os
import time
import csv
import requests
import HTMLParser
import ast
import json
import xml.etree.ElementTree as ET
import urllib
from lxml import html, etree
import sys

def getWords(text):
    return re.compile('\w+').findall(text)

def _find_between(self, s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

walmart_site_url = "http://www.walmart.com"
walmart_search_url = "http://www.walmart.com/search/?query="
success_results_file_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Brand & Style/walmart_product_list_by_brand_style.csv"
failure_results_file_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Brand & Style/walmart_brand_style (failed).csv"

f = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart Product From Amazon Asin/product name list.csv')
csv_f = csv.reader(f, delimiter=";")

product_name_list = list(csv_f)
search_url_list = [walmart_search_url + urllib.quote(row[1]) for row in product_name_list]

walmart_product_url_list = []

for index, search_url in enumerate(search_url_list):
    item_count = 0

    print search_url

    try:
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=10)
        b = requests.adapters.HTTPAdapter(max_retries=10)
        s.mount('http://', a)
        s.mount('https://', b)
        page_html = html.fromstring(s.get(search_url, headers=h, timeout=30).text)
    except:
        print "fail"
        continue

    try:
        item_count = int(re.findall(r'\d+', page_html.xpath("//div[@class='result-summary-container']/text()")[0].replace(",", ""))[1])
    except:
        item_count = 0

    if item_count == 0:
        continue

    search_item_list = page_html.xpath("//div[@id='tile-container']//div[@class='js-tile js-tile-landscape tile-landscape']//a[@class='js-product-title']")
    qualified_url_list = []
    is_found = False

    try:
        for n, search_item in enumerate(search_item_list):
            if n > 3:
                break

            if search_item.text_content().strip().lower() == product_name_list[index][0].strip().lower():
                walmart_product_url_list.append(walmart_site_url + search_item.xpath("./@href")[0])
                is_found = True
                break

            h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
            s = requests.Session()
            a = requests.adapters.HTTPAdapter(max_retries=10)
            b = requests.adapters.HTTPAdapter(max_retries=10)
            s.mount('http://', a)
            s.mount('https://', b)
            product_json = json.loads(s.get("http://54.85.249.210/get_data?url=" + urllib.quote(walmart_site_url + search_item.xpath("./@href")[0]), headers=h, timeout=30).text)
            amazon_product_name = product_name_list[index][0].replace("-", " ").strip().lower()
            walmart_product_name = product_json["product_info"]["product_name"].replace("-", " ").strip().lower()

            if set(getWords(amazon_product_name)) == set(getWords(walmart_product_name)):
                walmart_product_url_list.append(walmart_site_url + search_item.xpath("./@href")[0])
                is_found = True
                break

            amazon_search_url = "http://www.amazon.com/s/ref=nb_sb_noss_2?url=search-alias%3Daps&field-keywords=" + product_json["product_info"]["upc"]

            page_html = html.fromstring(s.get(amazon_search_url, headers=h, timeout=30).text)
            url_list = page_html.xpath("//ul[@id='s-results-list-atf']//a[@class='a-link-normal s-access-detail-page  a-text-normal']/@href")

            if product_name_list[index][0] in url_list[0]:
                walmart_product_url_list.append(walmart_site_url + search_item.xpath("./@href")[0])
                is_found = True
                break
    except:
        pass

    if not is_found:
        walmart_product_url_list.append("")

for url in walmart_product_url_list:
    print url
