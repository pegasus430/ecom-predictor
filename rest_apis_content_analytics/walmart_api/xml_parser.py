__author__ = 'root'

import os
import re

with open("/home/mufasa/Downloads/supplier test(bulk contents).xml", "rb") as upload_file:
    xml_data_by_list = upload_file.read()

upc_list = re.findall('<productId>(.*?)</productId>', xml_data_by_list, re.DOTALL)

for upc in upc_list:
    print upc

pass
