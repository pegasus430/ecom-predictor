__author__ = 'diogo'

import re
import os
import time
import csv
import requests
import ast
import xml.etree.ElementTree as ET
from lxml import html, etree
import sys


macys_site_url = "http://www1.macys.com"
macys_site_map_url = "http://www1.macys.com/cms/slp/2/Site-Index"
site_html = html.fromstring(requests.get(macys_site_map_url).text)
output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Macys CSV/"
all_product_url_list = []

for department_block in site_html.xpath("//div[@id='sitemap_wrapper']/div[@class='sitelink_container']"):
    if len(sys.argv) > 1 and not department_block.xpath("./h2/text()")[0].strip() == sys.argv[1]:
        continue

    for category_url in department_block.xpath(".//a/@href"):
        print "Category: " + category_url

        try:
            category_id = re.search('\?id=(.*)$', category_url).group(1).strip()

            if not category_id.isdigit():
                category_id = re.search('\?id=(.*)&', category_url).group(1).strip()

            if not category_id.isdigit():
                continue
        except:
            continue

        category_product_id_list_url = "http://www1.macys.com/catalog/category/facetedmeta?edge=hybrid&categoryId={}&facet=false&dynamicfacet=true&pageIndex={}".format(category_id, 1)
        category_product_id_list_html = html.fromstring(requests.get(category_product_id_list_url).text)
        product_counts_per_page = 60

        try:
            category_product_count = category_product_id_list_html.xpath("//div[@id='metaProductCount']/text()")[0]

            if not category_product_count.isdigit():
                continue

            category_product_count = int(category_product_count)
        except:
            continue

        category_product_pages_count = 100000

        try:
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

                all_product_url_list.extend(category_products_url_list)
        except:
            continue

        continue

all_product_url_list = list(set(all_product_url_list))

try:
    if len(sys.argv) > 1:
        file_name = sys.argv[1] + ".csv"
    else:
        file_name = "products.csv"

    if os.path.isfile(output_dir_path + file_name):
        csv_file = open(output_dir_path + file_name, 'a+')
    else:
        csv_file = open(output_dir_path + file_name, 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in all_product_url_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"
