__author__ = 'diogo'

import re
import os
import time
import csv

with open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart All products/marketplace_and_wmt_items_ip_mkt_2015-08-23.xml') as f:

    fieldnames = ['url', 'department', 'type']
    owned_home_count = marketplace_count = 0
    department_owned_marketplace_total_list = {}

    for line in f:
        try:
            url = re.search('\<url\>(.+?)\</url\>', line).group(1)
            department = re.search('<department>(.+?)</department>', line).group(1)
            type = re.search('<type>(.+?)</type>', line).group(1)
            count_list = [0, 0, 0]

            if department in department_owned_marketplace_total_list:
                count_list = department_owned_marketplace_total_list[department]

            if type == "owned":
                owned_home_count = owned_home_count + 1
                count_list[0] = count_list[0] + 1

            if type == "marketplace":
                marketplace_count = marketplace_count + 1
                count_list[1] = count_list[1] + 1

            count_list[2] = count_list[0] + count_list[1]
            department_owned_marketplace_total_list[department] = count_list

            localDate = time.localtime()
            dateString = time.strftime("%m%d%Y", localDate)

            csv_file_name = "%s_%s_%s.csv" % (department, type, dateString)

            if os.path.isfile("/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart All products/" + csv_file_name):
                csv_file = open("/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart All products/" + csv_file_name, 'a+')
            else:
                csv_file = open("/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart All products/" + csv_file_name, 'w')
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()

            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            csv_writer.writerow({'url': url, 'department': department, 'type': type})

            csv_file.close()
        except:
            continue

    print "markteplace: " + str(marketplace_count)
    print "owned home: " + str(owned_home_count)

try:
    file_name = "item_count.csv"

    if os.path.isfile('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart All products/' + file_name):
        csv_file = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart All products/' + file_name, 'a+')
    else:
        csv_file = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart All products/' + file_name, 'w')

    csv_writer = csv.writer(csv_file)

    for department in department_owned_marketplace_total_list:
        row = [department, department_owned_marketplace_total_list[department][0], department_owned_marketplace_total_list[department][1], department_owned_marketplace_total_list[department][2]]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"
