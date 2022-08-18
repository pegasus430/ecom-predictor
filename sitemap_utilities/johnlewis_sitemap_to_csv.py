__author__ = 'root'

'''
http://www.johnlewis.com/siteindex.xml

<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap>
<loc>JLBrandSitemap0.xml</loc>
</sitemap>
<sitemap>
<loc>JLCategorySitemap.xml</loc>
</sitemap>
<sitemap>
<loc>JLCQ5Sitemap.xml</loc>
</sitemap>
<sitemap>
<loc>JLEndecaSitemap0.xml</loc>
</sitemap>
<sitemap>
<loc>JLProductSitemap2.xml</loc>
</sitemap>
<sitemap>
<loc>JLProductSitemap3.xml</loc>
</sitemap>
<sitemap>
<loc>JLProductSitemap4.xml</loc>
</sitemap>
<sitemap>
<loc>JLProductSitemap.xml</loc>
</sitemap>
<sitemap>
<loc>JLStaticSitemap.xml</loc>
</sitemap>
</sitemapindex>
'''

import re
import os
import time
import csv
import requests
import xml.etree.ElementTree as ET

johnlewis_product_sitemap_xml_links = ["http://www.johnlewis.com/JLProductSitemap2.xml",
                                       "http://www.johnlewis.com/JLProductSitemap3.xml",
                                       "http://www.johnlewis.com/JLProductSitemap4.xml",
                                       "http://www.johnlewis.com/JLProductSitemap.xml"]
product_list = []
output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Johnlewis/products.csv"

for sitemap_xml_link in johnlewis_product_sitemap_xml_links:
    johnlewis_sitemap_text = requests.get(sitemap_xml_link).text
    product_list.extend(re.findall('<loc>(.*?)</loc>', johnlewis_sitemap_text, re.DOTALL))

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