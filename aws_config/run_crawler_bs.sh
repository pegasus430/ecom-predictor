#!/bin/bash
cd /home/ubuntu/tmtext/search;
# batch - will determine range of products
BATCH=$1
# bestsellers link
LINK=$2
# target site
SITE=$3
# batch name
NAME=$4
# maximum range for this batch
MAX_RANGE=$5

LRANGE=$(($MAX_RANGE / 10 * ($BATCH-1)))
RRANGE=$(($MAX_RANGE / 10 * $BATCH))
if [[ $BATCH == 10 ]]
then
RRANGE=$MAX_RANGE
fi
RANGE=$LRANGE-$RRANGE
echo "$RANGE"

OUT=/home/ubuntu/shared_sshfs/"$NAME"_"$SITE"_bestsellers_matches_"$BATCH".csv
time scrapy crawl $SITE -a bestsellers_link=$LINK -a bestsellers_range="$RANGE" \
-s LOG_ENABLED=1 -s LOG_LEVEL="DEBUG" -s HTTPCACHE_ENABLED=0 -a fast=0 -a output=6 \
-a outfile=$OUT 2>/home/ubuntu/shared_sshfs/search_log_"$NAME"_"$SITE"_bestsellers_"$BATCH".txt;
sleep 10;

# only halt if this is not batch 1 (node 1 hosts shared folder)
HOST=`hostname`; 
if [ "$HOST" != "node1" ]
	then
	sudo halt;
fi
