__author__ = 'diogo'

import re
import os
import time
from lxml import html, etree
import csv
import json
import requests
import xml.etree.ElementTree as ET

walmart_search_link = "http://www.walmart.com/search/?query={}"
scraper_link = "http://52.1.156.214/get_data?url={}"
variants_url_list = []
output_dir_path = '/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart Model/'

with open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart Model/walmart model.csv', 'rb') as f:
    reader = csv.reader(f)

    for row in reader:
        model = row[0]

        print model

        search_results = html.fromstring(requests.get(walmart_search_link.format(model)).text)
        product_url_list_related_with_model = search_results.xpath("//div[@id='search-container-center']//div[@id='tile-container']//a[@class='js-product-image']/@href")

        for index, url in enumerate(product_url_list_related_with_model):
            if not url.startswith("http://www.walmart.com"):
                product_url_list_related_with_model[index] = "http://www.walmart.com" + url

        for url in product_url_list_related_with_model:
            variants_url_list.append(url)

            result = json.loads(requests.get(scraper_link.format(url)).text)

            if not result["page_attributes"]["variants"]:
                continue

            for variant in result["page_attributes"]["variants"]:
                if url != variant["url"]:
                    variants_url_list.append(variant["url"])

variants_url_list = list(set(variants_url_list))

try:
    csv_file = open(output_dir_path + "model_variants.csv", 'w')
    csv_writer = csv.writer(csv_file)

    for product_url in variants_url_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"