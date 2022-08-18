from os import listdir
from os.path import isfile, join
import json
import os
import csv

path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/results 9 - 9/walmart/"

files_list = [f for f in listdir(path) if isfile(join(path, f))]
owned_list = []
bundle_list = []
fail_list = []
site_owned_only_list = []
shared_list = []
marketplace_only = []

for json_file in files_list:
    file_handler = open(path + json_file)
    file_handler.readline()
    product_json = ""

    for line in file_handler:
        product_json = product_json + line

    try:
        product_json = json.loads(product_json)
    except:
        fail_list.append(json_file)
        continue

    try:
        if product_json["sellers"]["owned"] == 1:
            owned_list.append(product_json["url"])
        else:
            pass
    except:
        pass

    try:
        if product_json["sellers"]["owned"] == 1 and product_json["sellers"]["marketplace"] == 1:
            shared_list.append(product_json["url"])
        else:
            pass
    except:
        pass

    try:
        if product_json["sellers"]["owned"] == 1 and (not product_json["sellers"]["marketplace"] or product_json["sellers"]["marketplace"] == 0):
            site_owned_only_list.append(product_json["url"])
        else:
            pass
    except:
        pass


    try:
        if product_json["sellers"]["owned"] == 0 and product_json["sellers"]["marketplace"] == 1:
            marketplace_only.append(product_json["url"])
        else:
            pass
    except:
        pass

    try:
        if product_json["failure_type"] == "Bundle":
            bundle_list.append(product_json["url"])
    except:
        pass


    continue

site_owned_only_file = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/results 9 - 9/site_owned_only.csv"

try:
    if os.path.isfile(site_owned_only_file):
        csv_file = open(site_owned_only_file, 'a+')
    else:
        csv_file = open(site_owned_only_file, 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in site_owned_only_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"

shared_list_file = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/results 9 - 9/shared_list.csv"

try:
    if os.path.isfile(shared_list_file):
        csv_file = open(shared_list_file, 'a+')
    else:
        csv_file = open(shared_list_file, 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in shared_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"