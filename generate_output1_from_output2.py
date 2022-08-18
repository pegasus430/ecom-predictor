#!/usr/bin/python

# Generate results output file of type 1 from results output file of type 2, for results generated with search spider

import sys

from optparse import OptionParser
import re

parser = OptionParser()
parser.add_option("--output2_file", "-f", dest="output2",
                  help="Input file (of type 2)")

parser.add_option("--output1_file", "-o", dest="output1",
                  help="Output file name (of type 1)")

parser.add_option("--output1_nomatch_file", "-n", dest="output1_nomatch",
                  help="Output file name for unmatched URLs")

(options, args) = parser.parse_args()

with open(options.output2, "r") as output2_file:
    with open(options.output1, "w+") as output1_file:
        with open(options.output1_nomatch, "w+") as output1_nomatch_file:
            for line in output2_file:
                line = line.strip()
                # if there was a match
                if "," in line:
                    matched_url = line.split(",")[1]
                    output1_file.write(matched_url + "\n")
                # if it was unmatched
                else:
                    output1_nomatch_file.write(line + "\n")



