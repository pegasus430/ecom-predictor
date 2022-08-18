__author__ = 'root'

import re
import os
import time
import csv
import requests
import HTMLParser
import ast
import xml.etree.ElementTree as ET
from lxml import html, etree
import sys

f = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/categories_compare.csv')
csv_f = csv.reader(f)

category_list = list(csv_f)

category_list_a = []
category_list_b = []

for category in category_list:
    if category[0].strip():
        category_list_a.append(category[0])

    if category[1].strip():
        category_list_b.append(category[1])

print len(category_list_a)
print len(category_list_b)

different_categories = list(set(category_list_a) - set(category_list_b))

print different_categories


output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/"
output_file_name = "different_category.csv"

try:

    if os.path.isfile(output_dir_path + output_file_name):
        csv_file = open(output_dir_path + output_file_name, 'a+')
    else:
        csv_file = open(output_dir_path + output_file_name, 'w')

    csv_writer = csv.writer(csv_file)

    for category in different_categories:
        row = [category]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"

