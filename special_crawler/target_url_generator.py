#!/usr/bin/python
#  -*- coding: utf-8 -*-

# Author: Ivan Gloc
# This is target.com URL generator that, given a list of Target.com DPCI codes as input can convert those into Target.com TCINs or Target.com URLs as output.
# $ python target_url_generator.py <input_csv>
# for ex: python target_url_generator.py Book2.csv
# Params:
# input_csv - input csv filename
# Output:
# output csv file1 - concatenate <input_csv> and "_URLs.csv"
# output csv file2 - concatenate <input_csv> and  "_3cols.csv"


import sys
import urllib
import csv
import re
import json
from lxml import html
import requests
from xml.dom import minidom


DEBUG = True

def target_urls_generator(input_csv):
    """
    This is target.com URL generator that, given a list of Target.com DPCI codes as input can convert those into Target.com TCINs or Target.com URLs as output.
    :param input_csv: input csv filename
    """
    inputcsvWithoutExt = input_csv.replace(".csv", "")
    inputcsvWithoutExt = inputcsvWithoutExt.replace(".CSV", "")
    output_URLs_csv = "%s_URLs.csv" % inputcsvWithoutExt
    output_3cols_csv = "%s_3cols.csv" % inputcsvWithoutExt

    with open(output_URLs_csv, 'wb') as output_URLs_csvfile:
        output_URLs_csvwriter = csv.writer(output_URLs_csvfile, delimiter=',')
        with open(output_3cols_csv, 'wb') as output_3cols_csvfile:
            output_3cols_csvwriter = csv.writer(output_3cols_csvfile, delimiter=',')
            with open(input_csv, "rb") as input_csvfile:
                reader = csv.reader(input_csvfile, delimiter=",")
                for i, line in enumerate(reader):
                    if DEBUG:
                        print '{}: {}'.format(i, line)
                    if len(line) > 3:
                        if i > 0:
                            DPCI = "%s-%s-%s" % (
                                line[0].strip().zfill(3),
                                line[1].strip().zfill(2),
                                line[2].strip().zfill(4))
                        else:
                            continue
                    else:
                        DPCI = line[0].strip()

                    # search_url = "http://www.target.com/s?searchTerm=%s" % DPCI
                    s_json_url = "http://tws.target.com/searchservice/item/" \
                                 "search_results/v2/by_keyword?kwr=y&search_term=%s" \
                                 "&alt=json&pageCount=24&response_group=Items&zone=mobile&offset=0" % DPCI
                    try:
                        contents = requests.get(s_json_url).text
                        res_json = json.loads(contents)
                        URL = "http://www.target.com/%s" % \
                              res_json['searchResponse']['items']['Item'][0]['productDetailPageURL']
                        reg_exp = re.findall("(.*)#", URL)
                        if len(reg_exp) > 0:
                            URL = reg_exp[0]

                        TCIN = ""
                        reg_exp = re.findall("A-([0-9]+)", URL)
                        if len(reg_exp) > 0:
                            TCIN = reg_exp[0]
                    except:
                        URL = ""
                        TCIN = ""

                    if len(URL) > 0:
                        output_URLs_csvwriter.writerow([URL])
                    output_3cols_csvwriter.writerow([DPCI, TCIN, URL])
                    if DEBUG:
                        print [DPCI, TCIN, URL]


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        input_csv = sys.argv[1] # Book2.csv
        target_urls_generator(input_csv)
    else:
        print "#"*100
        print "This is target.com URL generator that, given a list " \
              "of Target.com DPCI codes as input can convert those into " \
              "Target.com TCINs or Target.com URLs as output."
        print "Please input correct arguments.\nfor ex: python Book2.csv"
        print "This creates 2 output files(Book2_URLs.csv, Book2_3cols.csv"
        print "#"*100
