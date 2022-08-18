__author__ = 'diogo'

import re
import os
import time
import csv
import random
import requests
import json
import difflib

f = open('/home/mufasa/Documents/Misc/remove duplication/compare_taxonomy_category.csv')
csv_f = csv.reader(f)

category_taxonomy_list = list(csv_f)

category_taxonomy_list = sorted(category_taxonomy_list, key=lambda x: x[2])
prev_element = []

for category_taxonomy in category_taxonomy_list:
    if category_taxonomy[2] in prev_element:
        continue

    csv_file_name = "compare_taxonomy_category_refined.csv"

    if os.path.isfile("/home/mufasa/Documents/Misc/remove duplication/" + csv_file_name):
        csv_file = open("/home/mufasa/Documents/Misc/remove duplication/" + csv_file_name, 'a+')
    else:
        csv_file = open("/home/mufasa/Documents/Misc/remove duplication/" + csv_file_name, 'w')

    prev_element.append(category_taxonomy[2])

    category_taxonomy[2] = category_taxonomy[2].replace("&", "and")

    csv_writer = csv.writer(csv_file)

    csv_writer.writerow(category_taxonomy)

    csv_file.close()
