__author__ = 'root'
# Bug 2277 - Write a simple script that takes 2 CSVs as input and outputs CSV with common URLs

import re
import os
import time
import csv
import random
import requests
import json

f1 = open('/home/mufasa/Documents/Misc/ticket 2277/input.csv')
csv_f1 = csv.reader(f1)
row_list1 = list(csv_f1)
row_list1.pop(0)
dictionary1 = {}

for row in row_list1:
    dictionary1[row[0]] = row[1]

f2 = open('/home/mufasa/Documents/Misc/ticket 2277/Electronics_June_Owned.csv')
csv_f2 = csv.reader(f2)
row_list2 = list(csv_f2)
row_list2.pop(0)
dictionary2 = {}

for row in row_list2:
    dictionary2[row[0]] = row[1]

url_list1 = [row[0] for row in row_list1]
url_list2 = [row[0] for row in row_list2]

url_list1 = list(set(url_list1))
url_list2 = list(set(url_list2))

common_url_list = list(set(url_list1).intersection(url_list2))

csv_file_name = "common_list.csv"

if os.path.exists("/home/mufasa/Documents/Misc/ticket 2277/" + csv_file_name):
    os.remove("/home/mufasa/Documents/Misc/ticket 2277/" + csv_file_name)

for url in common_url_list:

    if os.path.isfile("/home/mufasa/Documents/Misc/ticket 2277/" + csv_file_name):
        csv_file = open("/home/mufasa/Documents/Misc/ticket 2277/" + csv_file_name, 'a+')
    else:
        csv_file = open("/home/mufasa/Documents/Misc/ticket 2277/" + csv_file_name, 'w')

    csv_writer = csv.writer(csv_file)

    row = [url, dictionary1[url], dictionary2[url]]
    csv_writer.writerow(row)

    csv_file.close()

