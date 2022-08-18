#!/bin/bash

INPUT="http://www.walmart.com/browse/electronics/tvs/3944_1060825_447913"
SITE="amazon"
NAME="walmart_tvs"

MAX_RANGE=686

for node in "$@"
do
    vagrant ssh  node$node -c "screen -dm /bin/bash /home/ubuntu/shared_sshfs/run_crawler_bs.sh $node $INPUT $SITE $NAME $MAX_RANGE; sleep 5";
done
