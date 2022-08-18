__author__ = 'root'
import requests
import json
import re

with open("/home/mufasa/Downloads/supplier test(bulk contents).xml", "rb") as upload_file:
    xml_data_by_list = upload_file.read()

upc_list = re.findall('<productId>(.*?)</productId>', xml_data_by_list, re.DOTALL)
item_id_list = []
invalid_upc_list = []

for upc in upc_list:
#    print upc
    product_json = json.loads(requests.get("http://api.walmartlabs.com/v1/items?apiKey=9uc3dbywg8gsfc4dgpk4e45p&upc={0}".format(upc)).text)
    try:
        item_id_list.append([upc, product_json["items"][0]["itemId"]])
        print upc + "-----" + str(product_json["items"][0]["itemId"])
    except:
        invalid_upc_list.append(upc)

#print item_id_list
print "-------------------------------"
print invalid_upc_list
pass


