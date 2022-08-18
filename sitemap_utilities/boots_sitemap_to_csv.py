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

boots_sitemap_url = "https://www.boots.com/en/Boots-Site-Map/"

h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
s = requests.Session()
a = requests.adapters.HTTPAdapter(max_retries=3)
b = requests.adapters.HTTPAdapter(max_retries=3)
s.mount('http://', a)
s.mount('https://', b)
page_html = html.fromstring(s.get(boots_sitemap_url, headers=h, timeout=10).text)
category_urls = page_html.xpath("//ul[@class='level_01']//ul[@class='level_02']//a/@href")
all_product_list = []

try:
    for category_url in category_urls:
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        category_page_html = html.fromstring(s.get(category_url, headers=h, timeout=10).text)
        sub_category_urls = category_page_html.xpath("//div[@class='narrowResults']//ul/li/a/@href")
        print category_url

        for sub_category_url in sub_category_urls:
            try:
                sub_category_page_html = html.fromstring(s.get(sub_category_url, headers=h, timeout=10).text)
                product_urls = sub_category_page_html.xpath("//div[@class='pl_productName']//a/@href")

                if not product_urls:
                    sub_category_page_html = html.fromstring(s.get(sub_category_url, headers=h, timeout=10).text)
                    sub_sub_category_urls = sub_category_page_html.xpath("//div[@class='narrowResults']//ul/li/a/@href")

                    if sub_sub_category_urls:
                        for sub_sub_category_url in sub_sub_category_urls:
                            if sub_sub_category_url.startswith("//"):
                                sub_sub_category_url = "http:" + sub_sub_category_url

                            sub_sub_category_page_html = html.fromstring(s.get(sub_sub_category_url, headers=h, timeout=10).text)
                            product_urls = sub_sub_category_page_html.xpath("//div[@class='pl_productName']//a/@href")
                            all_product_list.extend(product_urls)
                            print "    " + sub_sub_category_url

                            if sub_sub_category_page_html.xpath("//div[@class='productSearchResultsControls']//li[contains(@class, 'page')]/a/@href"):
                                page_index_url = sub_sub_category_url + sub_sub_category_page_html.xpath("//div[@class='productSearchResultsControls']//li[contains(@class, 'page')]/a/@href")[0]
                                page_index_url = page_index_url[:page_index_url.rfind("=")]

                                for page_index in range(2, 10000):
                                    product_list_page_url = page_index_url + "=" + str(page_index)
                                    sub_sub_category_page_html = html.fromstring(s.get(product_list_page_url, headers=h, timeout=10).text)
                                    product_urls = sub_sub_category_page_html.xpath("//div[@class='pl_productName']//a/@href")

                                    if not product_urls:
                                        break

                                    all_product_list.extend(product_urls)
                                    print "      " + product_list_page_url
                else:
                    all_product_list.extend(product_urls)
                    print "  " + sub_category_url

                    if sub_category_page_html.xpath("//div[@class='productSearchResultsControls']//li[contains(@class, 'page')]/a/@href"):
                        page_index_url = sub_category_url + sub_category_page_html.xpath("//div[@class='productSearchResultsControls']//li[contains(@class, 'page')]/a/@href")[0]
                        page_index_url = page_index_url[:page_index_url.rfind("=")]

                        for page_index in range(2, 10000):
                            product_list_page_url = page_index_url + "=" + str(page_index)
                            sub_category_page_html = html.fromstring(s.get(product_list_page_url, headers=h, timeout=10).text)
                            product_urls = sub_category_page_html.xpath("//div[@class='pl_productName']//a/@href")

                            if not product_urls:
                                break

                            all_product_list.extend(product_urls)
                            print "    " + product_list_page_url
            except:
                continue
    print "success"
except:
    print "fail"

all_product_list = list(set(all_product_list))

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Boots/"

try:
    if os.path.isfile(output_dir_path + "boots.csv"):
        csv_file = open(output_dir_path + "boots.csv", 'a+')
    else:
        csv_file = open(output_dir_path + "boots.csv", 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in all_product_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"


print "success"
