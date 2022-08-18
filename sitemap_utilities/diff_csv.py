__author__ = 'root'

import csv

f1 = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/results 9 - 11/a.csv')
csv_f = csv.reader(f1)
product_list1 = list(csv_f)
product_list1 = [row[0] for row in product_list1]
product_list1 = list(set(product_list1))

f2 = open('/home/mufasa/Documents/Workspace/Content Analytics/Misc/Walmart CSV by Categories/results 9 - 11/b.csv')
csv_f = csv.reader(f2)
product_list2 = list(csv_f)
product_list2 = [row[0] for row in product_list2]
product_list2 = list(set(product_list2))

diff_list = list(set(product_list1) - set(product_list2))

for url in diff_list:
    print url

pass