#!/usr/bin/python

# Receive a file with two values separated by comma on each line
# In the second file, replace all occurences of first value with second value
# Output results on stdout

import sys
import re

newlines = []
changedlines = []

# store all lines in second file in a list
lines2 = []
with open(sys.argv[2], "r") as outfile:
    for lineout in outfile:
        lines2.append(lineout.strip())

with open(sys.argv[1], "r") as infile:
    for line in infile:
        (value1, value2) = line.strip().split(",")
        for lineout in lines2:
            if value1 in lineout:
                newline = lineout.replace(value1, value2)
                newlines.append(newline)
                changedlines.append(lineout)

# append the ones that were not found a match
newlines = set(newlines).union(set(lines2).difference(set(changedlines)))

for line in newlines:
    print line
