#!/usr/bin/python
#  -*- coding: utf-8 -*-

# Author: Jacek Kaca
# This is a script to get product URLs from UPC.
#
# Output like:
# CSV file which contains a Product URL per line.
#
# Arguments are as follows.
# input_csv_file, output_csv_file
# for ex:
# python sample_google_script/sku_list.csv sample_google_script/sku_list_output.csv

import sys
import urllib, urllib2
import re
import sys
import csv
import json
from lxml import html
import mechanize
import requests


def get_bestbuy_producturl_from_upc(upc):
    """
    This gets a bestbuy product URL from UPC.
    :param upc: upc of a product
    :returns: return a product URL if exists, "" if not exist
    """
    # http://www.bestbuy.com/site/searchpage.jsp?st=700362687085&_dyncharset=UTF-8&id=pcat17071&type=page&sc=Global&cp=1&nrp=&sp=&qp=&list=n&iht=y&usc=All+Categories&ks=960&keys=keys
    payload = {
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.111 Safari/537.36'}

    with requests.session() as s:
        s.headers = headers
        try:
            url = "http://www.bestbuy.com/site/searchpage.jsp?st=%s" \
                  "&_dyncharset=UTF-8&id=pcat17071&type=page" \
                  "&sc=Global&cp=1&nrp=&sp=&qp=&list=n&iht=y" \
                  "&usc=All+Categories&ks=960&keys=keys" % upc
            response = s.get(url, params=payload)

            tree = html.fromstring(response.content)
            searched_urls = tree.xpath("//div[@class='sku-title']//a/@href")
            if len(searched_urls) > 0:
                # product_url = "http://www.bestbuy.com%s" % searched_urls[0].split("?")[0]
                product_url = "http://www.bestbuy.com%s" % searched_urls[0]
                return product_url
        except:
            pass
    return ""

if __name__ == "__main__":
    if len(sys.argv) > 2:
        inputfile = sys.argv[1]
        outputfile = sys.argv[2]

        with open(outputfile, 'w') as out_csvfile:
            fieldnames = ['category', 'sku', 'product_title', 'manufacturer', 'upc', 'condition', 'URL']
            writer = csv.DictWriter(out_csvfile, fieldnames=fieldnames)
            writer.writeheader()

            with open(inputfile, 'rb') as in_csvfile:
                reader = csv.reader(in_csvfile)
                idx = 0
                for row in reader:
                    if idx == 0:
                        idx += 1
                        continue
                    upc = row[4]
                    product_url = get_bestbuy_producturl_from_upc(upc)
                    writer.writerow(
                        {
                            'category': row[0],
                            'sku': row[1],
                            'product_title': row[2],
                            'manufacturer': row[3],
                            'upc': row[4],
                            'condition': row[5],
                            'URL': product_url
                        }
                    )
                    print "%s >>>  upc - %s, URL - %s" % (idx, upc, product_url)
                    idx += 1
    else:
        print "######################################################################################################"
        print "# This is a script to get product URLs from UPC. (bestbuy.com)"
        print "Please input correct arguments.\nfor ex: python sample_google_script/sku_list.csv sample_google_script/sku_list_output.csv"
        print "Output like:"
        print "CSV file which contains a Product URL per line."
        print "######################################################################################################"
