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
from StringIO import StringIO
import gzip
import xml.etree.ElementTree as ET

target_sitemap_link = "http://sitemap.target.com/wcsstore/SiteMap/sitemap_index.xml.gz"
target_product_sitemap_xml_links = requests.get(target_sitemap_link).content
target_product_sitemap_xml_links = re.findall('<loc>(.*?)</loc>', gzip.GzipFile(fileobj=StringIO(target_product_sitemap_xml_links)).read(), re.DOTALL)

url_list = []
output_dir_path = "target_products.csv"

for sitemap_xml_link in target_product_sitemap_xml_links:
    target_sitemap_contents = gzip.GzipFile(fileobj=StringIO(requests.get(sitemap_xml_link).content)).read()
    url_list.extend(re.findall('<loc>(.*?)</loc>', target_sitemap_contents, re.DOTALL))

product_list = []

for url in url_list:
    if url.startswith("http://www.target.com/p/"):
        product_list.append(url)

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