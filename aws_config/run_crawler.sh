#!/bin/bash
cd /home/ubuntu/tmtext/search;
# batch number
BATCH=$1
# input file base name (wihout extension)
INPUT=$2
# target site
SITE=$3

IN=/home/ubuntu/shared_sshfs/"$INPUT"_"$BATCH".csv
OUT=/home/ubuntu/shared_sshfs/"$INPUT"_"$SITE"_"$BATCH"_matches.csv
time scrapy crawl $SITE -a product_urls_file=$IN \
-s LOG_ENABLED=1 -s LOG_LEVEL="DEBUG" -s HTTPCACHE_ENABLED=0 -a fast=0 -a output=3 \
-a outfile=$OUT 2>/home/ubuntu/shared_sshfs/search_log_"$INPUT"_"$SITE"_"$BATCH".txt;
sleep 10;

# only halt if this is not batch 1 (node 1 hosts shared folder)
HOST=`hostname`; 
if [ "$HOST" != "node1" ]
	then
	sudo halt;
fi
