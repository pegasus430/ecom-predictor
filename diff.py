#!/usr/bin/python

# Get set difference between two lists of lines
# (different from diff because it doesn't consider order of lines)

# doesn't work for duplicate lines - only takes into account unique occurences

import sys

lines1 = set()
lines2 = set()

# sys.argv.append("desc_titles_walmart.out")
# sys.argv.append("desc_titles_walmart_old.out")

with open(sys.argv[1], "r") as file1:
    with open(sys.argv[2], "r") as file2:
        for line in file1:
            lines1.add(line.strip())
        for line in file2:
            lines2.add(line.strip())

for line in lines1.difference(lines2):
    print line


