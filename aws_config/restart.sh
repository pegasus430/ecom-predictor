#!/bin/bash
FILE=$1
SITE=$2

./resync.sh
vagrant up
./setup_sshfs.sh {2..10}
./run_all_crawlers.sh $FILE $SITE {1..10}
./setup_local_sshfs.sh
./monitor-tmux.sh "$FILE"_"$SITE"
