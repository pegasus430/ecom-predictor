__author__ = 'diogo'

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

walmart_site_url = "http://www.walmart.com"

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/results 9 - 11/"

f = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/results 9 - 11/bargain.csv')
csv_f = csv.reader(f)

category_url_list = list(csv_f)

product_url_list_by_category = {}

for category_url in category_url_list:
    item_count = 0
    category_name = category_url[0]
    category_url = category_url[1]

    if category_name not in product_url_list_by_category:
        product_url_list_by_category[category_name] = []
        
    print category_url

    try:
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        category_html = html.fromstring(s.get(category_url, headers=h, timeout=5).text)
    except:
        print "fail"
        continue

    url_list = category_html.xpath("//div[@class='js-tile js-tile-landscape tile-landscape']//a[@class='js-product-title']/@href")

    for index, url in enumerate(url_list):
        if not url.startswith(walmart_site_url):
            url_list[index] = walmart_site_url + url

    product_url_list_by_category[category_name].extend(url_list)
    category_id = None

    try:
        item_count = int(re.findall(r'\d+', category_html.xpath("//div[@class='result-summary-container']/text()")[0].replace(",", ""))[1])
    except:
        item_count = -1

    if item_count > 1000:
        min_price = 0
        max_price = 1

        while True:
            print "price range: {0} - {1}".format(min_price, max_price)

            if "?" in category_url:
                category_id = category_url[category_url.rfind("/") + 1:category_url.rfind("?")]
            else:
                category_id = category_url[category_url.rfind("/") + 1:]

            for index in range(1, 10000):
                if "?" not in category_url:
                    url = category_url + "?page=" + str(index) + "&cat_id=" + category_id
                else:
                    url = category_url + "&page=" + str(index) + "&cat_id=" + category_id

                if max_price > 0:
                    url = url + "&min_price={0}&max_price={1}".format(min_price, max_price)
                else:
                    url = url + "&min_price={0}".format(min_price)

                h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
                s = requests.Session()
                a = requests.adapters.HTTPAdapter(max_retries=3)
                b = requests.adapters.HTTPAdapter(max_retries=3)
                s.mount('http://', a)
                s.mount('https://', b)
                category_html = html.fromstring(s.get(url, headers=h, timeout=5).text)

                try:
                    item_count = int(re.findall(r'\d+', category_html.xpath("//div[@class='result-summary-container']/text()")[0].replace(",", ""))[1])
                except:
                    item_count = -1

                print item_count

                if item_count > 1000:
                    print "Over 1000"

                try:
                    if int(category_html.xpath("//ul[@class='paginator-list']/li/a[@class='active']")[0].text_content().strip()) != index:
                        break
                except:
                    break

                url_list = category_html.xpath("//div[@class='js-tile js-tile-landscape tile-landscape']//a[@class='js-product-title']/@href")

                for index, url in enumerate(url_list):
                    if not url.startswith(walmart_site_url):
                        url_list[index] = walmart_site_url + url

                product_url_list_by_category[category_name].extend(url_list)

            if max_price < 0:
                break

            if "?" not in category_url:
                url = category_url + "?page=" + str(index) + "&cat_id=" + category_id
            else:
                url = category_url + "&page=" + str(index) + "&cat_id=" + category_id

            url = url + "&min_price={0}".format(max_price)

            h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
            s = requests.Session()
            a = requests.adapters.HTTPAdapter(max_retries=3)
            b = requests.adapters.HTTPAdapter(max_retries=3)
            s.mount('http://', a)
            s.mount('https://', b)
            category_html = html.fromstring(s.get(url, headers=h, timeout=5).text)
            item_count = int(re.findall(r'\d+', category_html.xpath("//div[@class='result-summary-container']/text()")[0].replace(",", ""))[1])

            min_price = max_price

            if item_count > 1000:
                max_price = max_price + 1
            else:
                max_price = -1
    else:
        if "?" in category_url:
            category_id = category_url[category_url.rfind("/") + 1:category_url.rfind("?")]
        else:
            category_id = category_url[category_url.rfind("/") + 1:]

        for index in range(2, 10000):
            if "?" not in category_url:
                url = category_url + "?page=" + str(index) + "&cat_id=" + category_id
            else:
                url = category_url + "&page=" + str(index) + "&cat_id=" + category_id

            h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
            s = requests.Session()
            a = requests.adapters.HTTPAdapter(max_retries=3)
            b = requests.adapters.HTTPAdapter(max_retries=3)
            s.mount('http://', a)
            s.mount('https://', b)
            category_html = html.fromstring(s.get(url, headers=h, timeout=5).text)
            url_list = category_html.xpath("//div[@class='js-tile js-tile-landscape tile-landscape']//a[@class='js-product-title']/@href")

            try:
                if int(category_html.xpath("//ul[@class='paginator-list']/li/a[@class='active']")[0].text_content().strip()) != index:
                    break
            except:
                break

            for index, url in enumerate(url_list):
                if not url.startswith(walmart_site_url):
                    url_list[index] = walmart_site_url + url

            product_url_list_by_category[category_name].extend(url_list)

all_product_list = []

for category in product_url_list_by_category:
    try:
        product_url_list_by_category[category] = list(set(product_url_list_by_category[category]))
        all_product_list.extend(product_url_list_by_category[category])

        if os.path.isfile(output_dir_path + category + ".csv"):
            csv_file = open(output_dir_path + category + ".csv", 'a+')
        else:
            csv_file = open(output_dir_path + category + ".csv", 'w')
    
        csv_writer = csv.writer(csv_file)
    
        for product_url in product_url_list_by_category[category]:
            row = [product_url]
            csv_writer.writerow(row)
    
        csv_file.close()
    except:
        print "Error occurred"


all_product_list = list(set(all_product_list))

try:
    if os.path.isfile(output_dir_path + "urls.csv"):
        csv_file = open(output_dir_path + "urls.csv", 'a+')
    else:
        csv_file = open(output_dir_path + "urls.csv", 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in all_product_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"
