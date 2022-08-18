__author__ = 'diogo'

import re
import os
import time
import csv
import requests
import xml.etree.ElementTree as ET

snapdeal_sitemap_xml_link = "http://www.snapdeal.com/sitemap/sitemap.xml"
snapdeal_sitemap_xml = requests.get("http://www.snapdeal.com/sitemap/sitemap.xml").text
snapdeal_sitemap_xml = ET.fromstring(snapdeal_sitemap_xml)
output_dir_path = "/home/mufasa/Documents/Misc/snapdeal/"

for snapdeal_department in snapdeal_sitemap_xml:
    snapdeal_department_xml = requests.get(snapdeal_department[0].text.strip()).text
    snapdeal_department_xml = ET.fromstring(snapdeal_department_xml)

    file_name = snapdeal_department[0].text.strip()[len("http://www.snapdeal.com/sitemap/"):snapdeal_department[0].text.strip().rfind("/")]
    file_name = file_name.replace("/", "_") + ".csv"

    for snapdeal_product in snapdeal_department_xml:
        try:
            snapdeal_product_url = snapdeal_product[0].text.strip()

            if os.path.isfile(output_dir_path + file_name):
                csv_file = open(output_dir_path + file_name, 'a+')
            else:
                csv_file = open(output_dir_path + file_name, 'w')

            csv_writer = csv.writer(csv_file)

            row = [snapdeal_product_url]
            csv_writer.writerow(row)
            csv_file.close()
        except:
            print "Error occurred"
            continue