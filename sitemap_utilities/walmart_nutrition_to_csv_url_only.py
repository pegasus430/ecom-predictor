__author__ = 'diogo'

import re
import os
import time
import csv

with open('/home/mufasa/Documents/Misc/Nutritional facts May 6.csv') as f:

    csv_file_name = "Nutrition info url.csv"

    for line in f:
        try:
            fields = line.split(",")

            if fields[0].strip() == "ItemId":
                continue

            if os.path.isfile("/home/mufasa/Documents/Misc/Output/" + csv_file_name):
                csv_file = open("/home/mufasa/Documents/Misc/Output/" + csv_file_name, 'a+')
            else:
                csv_file = open("/home/mufasa/Documents/Misc/Output/" + csv_file_name, 'w')

            csv_writer = csv.writer(csv_file)

            row = ["http://www.walmart.com/ip/" + fields[0]]
            csv_writer.writerow(row)
            csv_file.close()
        except:
            continue

