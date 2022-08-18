__author__ = 'root'

'''
sitemap link: http://www.argos.co.uk/sitemap.xml

<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap>
<loc>http://www.argos.co.uk/staticpages.xml</loc>
</sitemap>
<sitemap>
<loc>http://www.argos.co.uk/catalogue.xml</loc>
</sitemap>
<sitemap>
<loc>http://www.argos.co.uk/catalogue2.xml</loc>
</sitemap>
<sitemap>
<loc>http://www.argos.co.uk/product.xml</loc>
</sitemap>
<sitemap>
<loc>http://www.argos.co.uk/product2.xml</loc>
</sitemap>
</sitemapindex>
'''

import re
import os
import time
import csv
import requests
import xml.etree.ElementTree as ET

argos_product_sitemap_xml_links = ["http://www.argos.co.uk/product.xml", "http://www.argos.co.uk/product2.xml"]
product_list = []
output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Argos/products.csv"

for sitemap_xml_link in argos_product_sitemap_xml_links:
    argos_sitemap_xml = requests.get(sitemap_xml_link).text
    product_list.extend(re.findall('<loc>(.*?)</loc>', argos_sitemap_xml, re.DOTALL))

product_list = list(set(product_list))

product_list = [url for url in product_list if not url.endswith("P.htm")]

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