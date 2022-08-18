__author__ = 'root'

import re
import os
import csv
import requests

homedepot_sitemap_link = "http://www.homedepot.com/sitemap/d/PIP_sitemap.xml"
homedepot_product_sitemap_xml_links = requests.get(homedepot_sitemap_link).text
homedepot_product_sitemap_xml_links = re.findall('<loc>(.*?)</loc>', homedepot_product_sitemap_xml_links, re.DOTALL)

product_list = []
output_dir_path = "/home/goldendev/sitemap/homedepot/products.csv"

for sitemap_xml_link in homedepot_product_sitemap_xml_links:
    snapdeal_sitemap_xml = requests.get(sitemap_xml_link).text
    product_list.extend(re.findall('<loc>(.*?)</loc>', snapdeal_sitemap_xml, re.DOTALL))

product_list = list(set(product_list))

print len(product_list)

for url in product_list:
    try:
        url = url.strip()

        if os.path.isfile(output_dir_path):
            csv_file = open(output_dir_path, 'a+')
        else:
            csv_file = open(output_dir_path, 'w')

        csv_writer = csv.writer(csv_file)

        row = [url]
        csv_writer.writerow(row)
        csv_file.close()
    except:
        print url
        continue
