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
walmart_categories_url = "http://www.walmart.com/cp/121828"
site_html = requests.get(walmart_categories_url).text
start_index = end_index = 0

start_index = site_html.find('html: "') + len('html: "')
end_index = site_html.find(",requires: ", start_index)
site_html = site_html[start_index:end_index]
end_index = site_html.rfind('"')
site_html = site_html[:end_index]

html_parser = HTMLParser.HTMLParser()
site_html = html_parser.unescape(site_html)
site_html = html.fromstring(site_html)

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/"
output_file_name_existing_categories = "results1_a.csv"
output_file_name_not_existing_categories = "results1_b.csv"

all_product_url_list = []
category_name_and_url_map = {}

for department_url in site_html.xpath("//div[@class='departments']//li/a/@href"):
    if not department_url.startswith("/cp/") and not department_url.startswith("/browse/"):
        continue

    if not department_url.startswith(walmart_site_url):
        department_url = walmart_site_url + department_url

    department_html = html.fromstring(requests.get(department_url).text)

    if not department_html.xpath("//div[@class='category-leftnav']"):
        continue

#    categories_left_menuitem_list = department_html.xpath("//div[@data-module='ShopByCategory']")

#    if not categories_left_menuitem_list:
#        continue

    sub_categories_list = department_html.xpath(".//ul[contains(@class, 'expander-content-inner')]/li")

    if not sub_categories_list:
        continue

    for sub_category in sub_categories_list:
        category_name = ""

        if len(sub_category) == 1:
            category_url = sub_category.xpath("./a/@href")[0]
            category_name = sub_category.xpath("./a/@data-name")[0]

            if not sub_category.xpath("./a/@href")[0].startswith(walmart_site_url):
                category_url = walmart_site_url + category_url

            if "," in category_url:
                continue

            if category_name in category_name_and_url_map:
                category_name_and_url_map[category_name].append(category_url)
            else:
                category_name_and_url_map[category_name] = [category_url]
        elif len(sub_category) > 1:
            url_list = sub_category.xpath("./div[contains(@class, 'js-lhn-menu-flyout')]//ul[@class='block-list']/li/a/@href")
            name_list = sub_category.xpath("./div[contains(@class, 'js-lhn-menu-flyout')]//ul[@class='block-list']/li/a/@data-name")

            if len(url_list) == name_list:
                for index, url in enumerate(url_list):
                    category_url = url
                    category_name = name_list[index]

                    if not sub_category.xpath("./a/@href")[0].startswith(walmart_site_url):
                        category_url = walmart_site_url + category_url

                    if "," in category_url:
                        continue

                    if category_name in category_name_and_url_map:
                        category_name_and_url_map[category_name].append(category_url)
                    else:
                        category_name_and_url_map[category_name] = [category_url]
            else:
                pass
        else:
            continue

f = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/categories.csv')
csv_f = csv.reader(f)

sub_category_name_list = list(csv_f)

if os.path.isfile(output_dir_path + output_file_name_existing_categories):
    csv_file_existing_category = open(output_dir_path + output_file_name_existing_categories, 'a+')
else:
    csv_file_existing_category = open(output_dir_path + output_file_name_existing_categories, 'w')

csv_writer_existing_category = csv.writer(csv_file_existing_category)

if os.path.isfile(output_dir_path + output_file_name_not_existing_categories):
    csv_file_not_existing_category = open(output_dir_path + output_file_name_not_existing_categories, 'a+')
else:
    csv_file_not_existing_category = open(output_dir_path + output_file_name_not_existing_categories, 'w')

csv_writer_not_existing_category = csv.writer(csv_file_not_existing_category)

for sub_category_name in sub_category_name_list:
    category_name = sub_category_name[0].split("/")[-1].strip()
    output_row = [sub_category_name[0], ""]

    if category_name in category_name_and_url_map:
        category_name_and_url_map[category_name] = list(set(category_name_and_url_map[category_name]))
        output_row[1] = "," . join(category_name_and_url_map[category_name])

        csv_writer_existing_category.writerow(output_row)
    else:
        csv_writer_not_existing_category.writerow(output_row)

csv_file_existing_category.close()
csv_file_not_existing_category.close()