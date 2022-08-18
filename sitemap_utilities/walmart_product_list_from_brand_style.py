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

walmart_site_url = "http://www.walmart.com"
walmart_search_url = "http://www.walmart.com/search/?query="
success_results_file_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Brand & Style/walmart_product_list_by_brand_style.csv"
failure_results_file_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Brand & Style/walmart_brand_style (failed).csv"

f = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Brand & Style/walmart_brand_style.csv')
csv_f = csv.reader(f)

brand_style_list = list(csv_f)
search_url_list = [[row[0], row[1], walmart_search_url + urllib.quote(row[0] + " " + row[1])] for row in brand_style_list]

product_url_list_by_category = {}

for row in search_url_list:
    item_count = 0
    brand = row[0]
    style = row[1]
    search_url = row[2]
    category_name = brand + "-----" + style

    if category_name not in product_url_list_by_category:
        product_url_list_by_category[category_name] = []
        
    print search_url

    try:
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=10)
        b = requests.adapters.HTTPAdapter(max_retries=10)
        s.mount('http://', a)
        s.mount('https://', b)
        category_html = html.fromstring(s.get(search_url, headers=h, timeout=30).text)
    except:
        print "fail"
        continue

    try:
        item_count = int(re.findall(r'\d+', category_html.xpath("//div[@class='result-summary-container']/text()")[0].replace(",", ""))[1])
    except:
        item_count = 0

    if item_count == 0:
        continue

    url_list = category_html.xpath("//div[@id='tile-container']//div[@class='js-tile js-tile-landscape tile-landscape']//a[@class='js-product-title']/@href")
    qualified_url_list = []
    is_search_failed = False

    for index, url in enumerate(url_list):
        if not url.startswith(walmart_site_url):
            url = walmart_site_url + url

        try:
            h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
            s = requests.Session()
            a = requests.adapters.HTTPAdapter(max_retries=10)
            b = requests.adapters.HTTPAdapter(max_retries=10)
            s.mount('http://', a)
            s.mount('https://', b)
            product_json = s.get("http://54.85.249.210/get_data?url=" + urllib.quote(url), headers=h, timeout=30).text

            is_qualified = False
            is_qualified = (brand.lower() in product_json.lower() and style.lower() in product_json.lower())

            if brand.lower() == "jms":
                is_qualified = (is_qualified or ("just my size" in product_json.lower() and style.lower() in product_json.lower()))

            if is_qualified:
                qualified_url_list.append(url)

                print brand + " " + style + " " + url

                product_json = json.loads(product_json)

                if product_json["page_attributes"]["related_products_urls"]:
                    qualified_url_list.extend(product_json["page_attributes"]["related_products_urls"])

                    for related_product_url in product_json["page_attributes"]["related_products_urls"]:
                        print brand + " " + style + " " + related_product_url
            else:
                is_search_failed = True
                break
        except:
            print "fail"
            continue

    if qualified_url_list:
        product_url_list_by_category[category_name].extend(qualified_url_list)
    else:
        is_search_failed = True

    if is_search_failed:
        continue

    if item_count > 1000:
        min_price = 0
        max_price = 1

        while True:
            print "price range: {0} - {1}".format(min_price, max_price)

            for index in range(1, 10000):
                if "?" not in search_url:
                    url_page_index = search_url + "?page=" + str(index)
                else:
                    url_page_index = search_url + "&page=" + str(index)

                if max_price > 0:
                    url_page_index = url + "&min_price={0}&max_price={1}".format(min_price, max_price)
                else:
                    url_page_index = url_page_index + "&min_price={0}".format(min_price)

                try:
                    h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
                    s = requests.Session()
                    a = requests.adapters.HTTPAdapter(max_retries=10)
                    b = requests.adapters.HTTPAdapter(max_retries=10)
                    s.mount('http://', a)
                    s.mount('https://', b)
                    category_html = html.fromstring(s.get(url_page_index, headers=h, timeout=30).text)
                except:
                    break

                try:
                    item_count = int(re.findall(r'\d+', category_html.xpath("//div[@class='result-summary-container']/text()")[0].replace(",", ""))[1])
                except:
                    item_count = 0

                if item_count == 0:
                    break

                try:
                    if int(category_html.xpath("//ul[@class='paginator-list']/li/a[@class='active']")[0].text_content().strip()) != index:
                        break
                except:
                    break

                url_list = category_html.xpath("//div[@id='tile-container']//div[@class='js-tile js-tile-landscape tile-landscape']//a[@class='js-product-title']/@href")
                qualified_url_list = []
                is_search_failed = False

                for index, url in enumerate(url_list):
                    if not url.startswith(walmart_site_url):
                        url = walmart_site_url + url

                    try:
                        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
                        s = requests.Session()
                        a = requests.adapters.HTTPAdapter(max_retries=10)
                        b = requests.adapters.HTTPAdapter(max_retries=10)
                        s.mount('http://', a)
                        s.mount('https://', b)
                        product_json = s.get("http://52.1.156.214/get_data?url=" + urllib.quote(url), headers=h, timeout=30).text

                        is_qualified = False
                        is_qualified = (brand.lower() in product_json.lower() and style.lower() in product_json.lower())

                        if brand.lower() == "jms":
                            is_qualified = (is_qualified or ("just my size" in product_json.lower() and style.lower() in product_json.lower()))

                        if is_qualified:
                            qualified_url_list.append(url)

                            print brand + " " + style + " " + url

                            product_json = json.loads(product_json)

                            if product_json["page_attributes"]["related_products_urls"]:
                                qualified_url_list.extend(product_json["page_attributes"]["related_products_urls"])

                                for related_product_url in product_json["page_attributes"]["related_products_urls"]:
                                    print brand + " " + style + " " + related_product_url
                        else:
                            is_search_failed = True
                            break
                    except:
                        print "fail"
                        continue

                if qualified_url_list:
                    product_url_list_by_category[category_name].extend(qualified_url_list)
                else:
                    is_search_failed = True

                if is_search_failed:
                    break

            if max_price < 0:
                break

            if "?" not in search_url:
                url_page_index = search_url + "?page=" + str(index)
            else:
                url_page_index = search_url + "&page=" + str(index)

            url_page_index = url_page_index + "&min_price={0}".format(max_price)

            h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
            s = requests.Session()
            a = requests.adapters.HTTPAdapter(max_retries=10)
            b = requests.adapters.HTTPAdapter(max_retries=10)
            s.mount('http://', a)
            s.mount('https://', b)
            category_html = html.fromstring(s.get(url_page_index, headers=h, timeout=30).text)
            item_count = int(re.findall(r'\d+', category_html.xpath("//div[@class='result-summary-container']/text()")[0].replace(",", ""))[1])

            min_price = max_price

            if item_count > 1000:
                max_price = max_price + 1
            else:
                max_price = -1
    else:
        for index in range(2, 10000):
            if "?" not in search_url:
                url_page_index = search_url + "?page=" + str(index)
            else:
                url_page_index = search_url + "&page=" + str(index)

            try:
                h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
                s = requests.Session()
                a = requests.adapters.HTTPAdapter(max_retries=10)
                b = requests.adapters.HTTPAdapter(max_retries=10)
                s.mount('http://', a)
                s.mount('https://', b)
                category_html = html.fromstring(s.get(url_page_index, headers=h, timeout=30).text)
                url_list = category_html.xpath("//div[@id='tile-container']//div[@class='js-tile js-tile-landscape tile-landscape']//a[@class='js-product-title']/@href")
            except:
                break

            if not url_list:
                break

            try:
                if int(category_html.xpath("//ul[@class='paginator-list']/li/a[@class='active']")[0].text_content().strip()) != index:
                    break
            except:
                break

            qualified_url_list = []
            is_search_failed = False

            for index, url in enumerate(url_list):
                if not url.startswith(walmart_site_url):
                    url = walmart_site_url + url

                try:
                    h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
                    s = requests.Session()
                    a = requests.adapters.HTTPAdapter(max_retries=10)
                    b = requests.adapters.HTTPAdapter(max_retries=10)
                    s.mount('http://', a)
                    s.mount('https://', b)
                    product_json = s.get("http://52.1.156.214/get_data?url=" + urllib.quote(url), headers=h, timeout=30).text

                    is_qualified = False
                    is_qualified = (brand.lower() in product_json.lower() and style.lower() in product_json.lower())

                    if brand.lower() == "jms":
                        is_qualified = (is_qualified or ("just my size" in product_json.lower() and style.lower() in product_json.lower()))

                    if is_qualified:
                        qualified_url_list.append(url)

                        print brand + " " + style + " " + url

                        product_json = json.loads(product_json)

                        if product_json["page_attributes"]["related_products_urls"]:
                            qualified_url_list.extend(product_json["page_attributes"]["related_products_urls"])

                            for related_product_url in product_json["page_attributes"]["related_products_urls"]:
                                print brand + " " + style + " " + related_product_url
                    else:
                        is_search_failed = True
                        break
                except:
                    print "fail"
                    continue

            if qualified_url_list:
                product_url_list_by_category[category_name].extend(qualified_url_list)
            else:
                is_search_failed = True

            if is_search_failed:
                break

if os.path.isfile(success_results_file_path):
    csv_file1 = open(success_results_file_path, 'a+')
else:
    csv_file1 = open(success_results_file_path, 'w')

if os.path.isfile(failure_results_file_path):
    csv_file2 = open(failure_results_file_path, 'a+')
else:
    csv_file2 = open(failure_results_file_path, 'w')

csv_writer1 = csv.writer(csv_file1)
csv_writer2 = csv.writer(csv_file2)

for category in product_url_list_by_category:
    try:
        product_url_list_by_category[category] = list(set(product_url_list_by_category[category]))

        brand = category.split("-----")[0]
        style = category.split("-----")[1]

        if (len(product_url_list_by_category[category]) == 0):
            row = [brand, style]
            csv_writer2.writerow(row)

        for product_url in product_url_list_by_category[category]:
            row = [brand, style, product_url]
            csv_writer1.writerow(row)
    
    except:
        print "Error occurred"

csv_file1.close()
csv_file2.close()
