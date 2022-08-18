__author__ = 'diogo'

import re
import os
import time
import csv
import random
import requests
import json

f = open('/home/mufasa/Documents/nutrition_check_input.csv')
csv_f = csv.reader(f)

url_list = list(csv_f)
randomly_selected_url_list = random.sample(url_list, 500)
h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}

fieldnames = ['url', 'nutrition fact text health']

for url in randomly_selected_url_list:
    try:
        response_raw_text = requests.get("http://52.1.156.214/get_data?url=" + url[0], headers=h).text
        response_json = json.loads(response_raw_text)

        csv_file_name = "nutrition_info_list.csv"

        if os.path.isfile("/home/mufasa/Documents/Misc/Output/" + csv_file_name):
            csv_file = open("/home/mufasa/Documents/Misc/Output/" + csv_file_name, 'a+')
        else:
            csv_file = open("/home/mufasa/Documents/Misc/Output/" + csv_file_name, 'w')
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()

        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writerow({'url': url[0], 'nutrition fact text health': response_json["product_info"]["nutrition_fact_text_health"]})

        csv_file.close()
    except:
        continue

