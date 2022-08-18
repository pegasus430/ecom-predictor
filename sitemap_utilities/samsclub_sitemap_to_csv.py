__author__ = 'root'

'''
sitemap link: http://www.jcpenney.com/sitemap.xml

<sitemap>
    <loc>http://www.jcpenney.com/product.xml</loc>
    <lastmod>2015-09-10</lastmod>
</sitemap>
<sitemap>
    <loc>http://www.jcpenney.com/product2.xml</loc>
    <lastmod>2015-09-10</lastmod>
</sitemap>
'''

import re
import os
import time
import csv
import requests
import xml.etree.ElementTree as ET

snapdeal_product_sitemap_xml_links = \
    ["http://www.samsclub.com/sitemap_products_1.xml",
     "http://www.samsclub.com/sitemap_products_2.xml",
     "http://www.samsclub.com/sitemap_products_3.xml",
     "http://www.samsclub.com/sitemap_products_4.xml",
     "http://www.samsclub.com/sitemap_products_5.xml",
     "http://www.samsclub.com/sitemap_products_6.xml",
     "http://www.samsclub.com/sitemap_products_7.xml",
     "http://www.samsclub.com/sitemap_products_8.xml",
     "http://www.samsclub.com/sitemap_products_9.xml"]
product_list = []
output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Samsclub/products.csv"

for sitemap_xml_link in snapdeal_product_sitemap_xml_links:
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