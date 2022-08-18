#!/bin/bash

# for a _urls file (result of product matching containing oly matches urls) given as argument,
# count total number of urls, unique and duplicates

FILE=$1

TOTAL=$((`cat $FILE | wc -l` - 1))
UNIQUE=$((`cat $FILE | sort -u | wc -l` - 1))
DUPLICATES=$(($TOTAL - $UNIQUE))
echo "total $TOTAL"
echo "unique $UNIQUE"
echo "duplicates $DUPLICATES"