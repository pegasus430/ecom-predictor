#!/bin/bash
FILE=$1

echo "ERRORS"
echo "-----------"

# if no second argument was given, just analyze one file
# the one given as first argument
if [ -z "$2" ]
then
	LOGFILE=$FILE
	if [ -f "$LOGFILE" ]
	then
		cat $LOGFILE | grep ERROR | wc -l
	fi

else

# if second argument was given, representing range of subbatches for this input
# to run the stats on - then run on given number of batches
# (input will be part of the filenames to be monitored)

	RANGE=${@:2}
	for NR in $RANGE
	do
		LOGFILE=shared_sshfs/search_log_"$FILE"_"$NR".txt
		if [ -f "$LOGFILE" ]
			then
			printf "$NR "; ack "ERROR" $LOGFILE | wc -l
		fi
	done
fi
