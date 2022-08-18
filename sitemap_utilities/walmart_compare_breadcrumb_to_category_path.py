__author__ = 'diogo'

import re
import os
import time
import csv
import random
import requests
import json
import difflib

f = open('/home/mufasa/Documents/Misc/category_taxonomy.csv')
csv_f = csv.reader(f)

category_taxonomy_list = list(csv_f)

category_taxonomy_list.pop(0)

for category_taxonomy in category_taxonomy_list:
    category_taxonomy[1] = category_taxonomy[1][category_taxonomy[1].rfind("/") + 1:]

category_taxonomy_list = sorted(category_taxonomy_list, key=lambda x: x[1])

f = open('/home/mufasa/Documents/Misc/breadcrumb.csv')
csv_f = csv.reader(f)

breadcrumb_list = list(csv_f)

breadcrumb_list = sorted(breadcrumb_list, key=lambda x: x[0])

breadcrumb_map = {}

for breadcrumb in breadcrumb_list:
    breadcrumb_map[breadcrumb[0]] = breadcrumb[1]

for category_taxonomy in category_taxonomy_list:
    taxonomy = category_taxonomy[6].lower()
    category_path = breadcrumb_map[category_taxonomy[1]].lower()
    category_path = category_path.replace(" & ", " and ")
    taxonomy_list = re.split(", ", taxonomy)
    category_path_list = re.split("/| & |, ", category_path)

    common_occurrence = 0

    for index, taxonomy in enumerate(taxonomy_list):
        if index + 1 > len(category_path_list):
            break

        if taxonomy.strip() == category_path_list[index].strip():
            common_occurrence = common_occurrence + 1

    similarity_value = 0

    if len(taxonomy_list) > 0:
        similarity_value = float(common_occurrence / float(len(taxonomy_list)))

    if similarity_value < 1:
        pass

    sm = difflib.SequenceMatcher(None, category_path_list, taxonomy_list)
    similarity_value = sm.ratio()

    csv_file_name = "compare_taxonomy_category.csv"

    if os.path.isfile("/home/mufasa/Documents/Misc/Output/" + csv_file_name):
        csv_file = open("/home/mufasa/Documents/Misc/Output/" + csv_file_name, 'a+')
    else:
        csv_file = open("/home/mufasa/Documents/Misc/Output/" + csv_file_name, 'w')

    csv_writer = csv.writer(csv_file)

    row = [category_taxonomy[1], category_taxonomy[6], breadcrumb_map[category_taxonomy[1]], similarity_value]
    csv_writer.writerow(row)

    csv_file.close()

