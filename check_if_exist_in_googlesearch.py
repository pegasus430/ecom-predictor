#!/usr/bin/python
#  -*- coding: utf-8 -*-

# Author: Ivan G
# This is a google checker to check if a product exists in google search.
#
# sample list - Levi's Men's Macys.com Items No Longer Available List
# This is a simple script that reads a list of URLs and returns that same list with an indicator of whether the URL shows up in Google search results or not
# Output like:
# URL,1   (1 if exists in Google, 0 if not exists in Google)
#
# Arguments are as follows.
# input_csv_file, output_csv_file
# for ex:
# python sample_google_script/Macy_Report_2016_05_11.csv sample_google_script/Macy_Report_2016_05_11_output.csv

import sys
import urllib, urllib2
import re
import sys
import csv
import json
from lxml import html
import mechanize
import requests


def check_if_exists_in_googlesearch(url):
    """
    This check if a product exists in google search result pages.
    :param url: URL string of a product
    :returns: return 1 if exist, 0 if not exist
    """
    # http://www1.macys.com/shop/product/levis-mens-501-original-shrink-to-fit-jeans?ID=2514087&CategoryID=11221
    str_query = "%s %s" % (url.split("//")[-1].split("/")[0], re.search('ID=(\d+)', url).group(1))
    payload = {
        r"q": str_query,
        r"num": '20',
        r"btnG": "Search",
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.111 Safari/537.36'}

    with requests.session() as s:
        s.headers = headers
        try:
            response = s.get("https://www.google.com/search", params=payload)

            tree = html.fromstring(response.content)
            searched_urls = tree.xpath("//div[@class='g']//h3[@class='r']/a/@href")
            if url in searched_urls:
                return 1
        except:
            pass
    return 0

if __name__ == "__main__":
    if len(sys.argv) > 2:
        inputfile = sys.argv[1]
        outputfile = sys.argv[2]

        with open(outputfile, 'w') as out_csvfile:
            fieldnames = ['URL', 'Google Exist']
            writer = csv.DictWriter(out_csvfile, fieldnames=fieldnames)
            writer.writeheader()

            with open(inputfile, 'rb') as in_csvfile:
                reader = csv.reader(in_csvfile, delimiter=' ', quotechar='|')
                for row in reader:
                    a_url = ', '.join(row)
                    if a_url == "URL":
                        pass
                    else:
                        if_google_exist = check_if_exists_in_googlesearch(a_url)
                        writer.writerow({'URL': a_url, 'Google Exist': if_google_exist})
    else:
        print "######################################################################################################"
        print "This is a google checker to check if a product exists in google search."
        print "Please input correct arguments.\nfor ex: python sample_google_script/Macy_Report_2016_05_11.csv sample_google_script/Macy_Report_2016_05_11_output.csv"
        print "This is a simple script that reads a list of URLs and returns that same list with an indicator of whether the URL shows up in Google search results or not"
        print "Output like:"
        print "URL,1   (1 if exists in Google, 0 if not exists in Google)"
        print "######################################################################################################"
