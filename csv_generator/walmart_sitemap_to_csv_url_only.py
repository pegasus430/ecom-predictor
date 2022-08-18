__author__ = 'diogo'

import re
import os
import time
import csv

input_file_path = "/home/ubuntu/Documents/Misc/ticket 2275/marketplace_and_wmt_items_ip_2015-06-28.xml"
output_dir_path = "/home/ubuntu/Documents/Misc/ticket 2275/urls/"

with open(input_file_path) as f:

    fieldnames = ['url', 'department', 'type']

    for line in f:
        try:
            url = re.search('\<url\>(.+?)\</url\>', line).group(1)
            department = re.search('<department>(.+?)</department>', line).group(1)
            type = re.search('<type>(.+?)</type>', line).group(1)
            localDate = time.localtime()
            dateString = time.strftime("%Y-%m-%d", localDate)

            csv_file_name = "%s-%s-%s.csv" % (department, type, dateString)

            if os.path.isfile(output_dir_path + csv_file_name):
                csv_file = open(output_dir_path + csv_file_name, 'a+')
            else:
                csv_file = open(output_dir_path + csv_file_name, 'w')


            csv_writer = csv.writer(csv_file)

            row = [url]
            csv_writer.writerow(row)
            csv_file.close()
        except:
            continue

