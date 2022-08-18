#!/usr/bin/python

# Get set difference between two lists of lines
# (different from diff because it doesn't consider order of lines)

# doesn't work for duplicate lines - only takes into account unique occurences

import sys
import re

with open(sys.argv[1], "r") as filein:    
    for line in filein:

        if "," in line:
            [url1, url2] = line.strip().split(",")

            # for second url:
            # remove parameters after ?
            m2 = re.match("(.*)\?.*", url2)
            if m2:
                url2 = m2.group(1)

            # remove part after ;
            m2 = re.match("(.*);.*", url2)
            if m2:
                url2 = m2.group(1)

        else:
            url2 = None
            url1 = line.strip()


        # for first url:
        # remove parameters after ?
        m1 = re.match("(.*)\?.*", url1)
        if m1:
            url1 = m1.group(1)

        # remove part after ;
        m1 = re.match("(.*);.*", url1)
        if m1:
            url1 = m1.group(1)

        if url2:
            print ",".join([url1, url2])
        else:
            print url1
