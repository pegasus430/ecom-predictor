#!/usr/bin/python

# Get ids from a CSV file containing one on each line, and generate Walmart product URLs based on them

import sys
import re
from spiders_utils import Utils

base_url = "http://www.walmart.com/ip/"
with open(sys.argv[1]) as idsfile:
    for line in idsfile:
        # if there are other fields ignore them (get the first one)
        if "," in line:
            id_string = line.strip().split(",")[0]
        else:
            id_string = line.strip()
        # if it's not a number ignore it (could be a header line)
        if re.match("[0-9]+", id_string):
            # generate URL and output it
            url = Utils.add_domain(id_string, base_url)
            print url