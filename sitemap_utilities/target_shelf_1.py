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
import json

shelf_urls_list = ["http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&response_group=Items%2CVariationSummary&category=5xu2f&isLeaf=false&page_type=ShopByPage&faceted_value=55oacZ4yjyd&zone=PLP",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=d_iac%3AShirts%7Cd_style_all%3Abasic+tee&category=3675&view_type=medium&page=2&offset=60&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=d_iac%3AShirts%7Cd_style_all%3Abasic+tee&category=3675&view_type=medium&page=3&offset=120&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=d_iac%3AShirts%7Cd_style_all%3Abasic+tee&category=3675&view_type=medium&page=4&offset=180&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&response_group=Items%2CVariationSummary&category=5xu2b&isLeaf=false&facets=&zone=PLP",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=30&zone=PLP&facets=&category=3677&view_type=large&page=2&offset=30&stateData=%22d_pant_leg_type_all%22%3A%22show%22%2C%22d_size_abn%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=30&zone=PLP&facets=&category=3677&view_type=large&page=3&offset=60&stateData=%22d_pant_leg_type_all%22%3A%22show%22%2C%22d_size_abn%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=30&zone=PLP&facets=&category=3677&view_type=large&page=4&offset=90&stateData=%22d_pant_leg_type_all%22%3A%22show%22%2C%22d_size_abn%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&response_group=Items%2CVariationSummary&category=55cxf&isLeaf=true&facets=&zone=PLP",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=30&zone=PLP&facets=&category=834003&view_type=large&page=2&offset=30&stateData=%22d_garment_fit%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=true",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&response_group=Items%2CVariationSummary&category=5xu2e&isLeaf=false&facets=&zone=PLP",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=&category=3676&view_type=medium&page=2&offset=60&stateData=%22d_item_type_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=&category=3676&view_type=medium&page=3&offset=120&stateData=%22d_item_type_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&response_group=Items%2CVariationSummary&category=5xu26&isLeaf=false&facets=&zone=PLP",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=30&zone=PLP&facets=&category=3682&view_type=large&page=2&offset=30&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_size_abn%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=30&zone=PLP&facets=&category=3682&view_type=large&page=3&offset=60&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_size_abn%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=30&zone=PLP&facets=&category=3682&view_type=large&page=4&offset=90&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_size_abn%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&response_group=Items%2CVariationSummary&category=5xu2f&isLeaf=false&page_type=ShopByPage&faceted_value=55oamZ55oaa&zone=PLP",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=d_iac%3AUnderwear%7Cd_iac%3AUndershirts&category=3675&view_type=medium&page=2&offset=60&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=d_iac%3AUnderwear%7Cd_iac%3AUndershirts&category=3675&view_type=medium&page=3&offset=120&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=d_iac%3AUnderwear%7Cd_iac%3AUndershirts&category=3675&view_type=medium&page=4&offset=180&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=d_iac%3AUnderwear%7Cd_iac%3AUndershirts&category=3675&view_type=medium&page=5&offset=240&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=d_iac%3AUnderwear%7Cd_iac%3AUndershirts&category=3675&view_type=medium&page=6&offset=300&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&response_group=Items%2CVariationSummary&category=5xu21&isLeaf=true&facets=&zone=PLP",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=&category=3683&view_type=medium&page=2&offset=60&stateData=%22d_style_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C%22d_pricerange%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=true",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=&category=3683&view_type=medium&page=3&offset=120&stateData=%22d_style_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C%22d_pricerange%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=true",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=&category=3683&view_type=medium&page=4&offset=180&stateData=%22d_style_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C%22d_pricerange%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=true",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=newest&pageCount=60&zone=PLP&facets=&category=3683&view_type=medium&page=5&offset=240&stateData=%22d_style_all%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C%22d_pricerange%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=true",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&response_group=Items%2CVariationSummary&category=5xu29&isLeaf=false&facets=&zone=PLP",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=bestselling&pageCount=60&zone=PLP&facets=&category=3679&view_type=medium&page=2&offset=60&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_size_all%22%3A%22show%22%2C%22d_garment_fit%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=bestselling&pageCount=60&zone=PLP&facets=&category=3679&view_type=medium&page=3&offset=120&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_size_all%22%3A%22show%22%2C%22d_garment_fit%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false",
              "http://tws.target.com/searchservice/item/search_results/v2/by_keyword?callback=getPlpResponse&sort_by=bestselling&pageCount=60&zone=PLP&facets=&category=3679&view_type=medium&page=4&offset=180&stateData=%22d_item_type_all%22%3A%22show%22%2C%22d_size_all%22%3A%22show%22%2C%22d_garment_fit%22%3A%22show%22%2C%22d_brand_all%22%3A%22show%22%2C%22d_deals%22%3A%22show%22%2C&response_group=Items%2CVariationSummary&isLeaf=false"]

url_list = []

for shelf_url in shelf_urls_list:
    try:
        print shelf_url
        h = {"User-Agent" : "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36"}
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=3)
        b = requests.adapters.HTTPAdapter(max_retries=3)
        s.mount('http://', a)
        s.mount('https://', b)
        response_json = json.loads(s.get(shelf_url, headers=h, timeout=5).text[len("getPlpResponse("):-1])
        print len(response_json["searchResponse"]["items"]["Item"])
        for item in response_json["searchResponse"]["items"]["Item"]:
            url_list.append("http://www.target.com/" + item["productDetailPageURL"])
        print "success"
    except:
        print "fail"

url_list = list(set(url_list))

output_dir_path = "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Target from Shelf/"

try:
    if os.path.isfile(output_dir_path + "urls.csv"):
        csv_file = open(output_dir_path + "urls.csv", 'a+')
    else:
        csv_file = open(output_dir_path + "urls.csv", 'w')

    csv_writer = csv.writer(csv_file)

    for product_url in url_list:
        row = [product_url]
        csv_writer.writerow(row)

    csv_file.close()
except:
    print "Error occurred"


print "success"
