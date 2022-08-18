#!/bin/bash

INPUT=$1
SITE=$2
# now argument list starts from argument 3
shift 2
NODES="$@"
# separate argument list one on each line
echo $NODES | sed -e 's/[ ]/\n/g' | \
	xargs -P10 -I% vagrant ssh node% -c "screen -dm /bin/bash /home/ubuntu/shared_sshfs/run_crawler.sh % $INPUT $SITE; sleep 5"
