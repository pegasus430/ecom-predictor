__author__ = 'diogo'

import re
import os
import time
import csv

with open('/home/mufasa/Documents/Misc/marketplace_and_wmt_items_ip_2015-06-17.xml') as f:

    fieldnames = ['url', 'department', 'type']

    for line in f:
        try:
            url = re.search('\<url\>(.+?)\</url\>', line).group(1)
            department = re.search('<department>(.+?)</department>', line).group(1)
            type = re.search('<type>(.+?)</type>', line).group(1)
            localDate = time.localtime()
            dateString = time.strftime("%m%d%Y", localDate)

            csv_file_name = "%s_%s_%s.csv" % (department, type, dateString)

            if os.path.isfile("/home/mufasa/Documents/Misc/Output/" + csv_file_name):
                csv_file = open("/home/mufasa/Documents/Misc/Output/" + csv_file_name, 'a+')
            else:
                csv_file = open("/home/mufasa/Documents/Misc/Output/" + csv_file_name, 'w')
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()

            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            csv_writer.writerow({'url': url, 'department': department, 'type': type})

            csv_file.close()
        except:
            continue

