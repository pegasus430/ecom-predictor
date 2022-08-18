import xml.etree.ElementTree as ET
import requests, subprocess

c = requests.get('http://jet.com/sitemap.xml').content
e = ET.fromstring(c)

content_csv = open('content.csv', 'w')
categories_csv = open('categories.csv', 'w')
products_csv = open('products.csv', 'w')

for loc in e.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
    resource_name = loc.text
    c2 = requests.get(resource_name).content

    e2 = ET.fromstring(c2)

    for loc2 in e2.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
        url = loc2.text

        if 'content' in resource_name:
            content_csv.write(url + '\n')

        elif 'categories' in resource_name:
            categories_csv.write(url + '\n')

        else:
            products_csv.write(url + '\n')

content_csv.close()
categories_csv.close()
products_csv.close()

subprocess.Popen('zip content.zip content.csv', shell=True).communicate()
subprocess.Popen('zip categories.zip categories.csv', shell=True).communicate()
subprocess.Popen('zip products.zip products.csv', shell=True).communicate()
