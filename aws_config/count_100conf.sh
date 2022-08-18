#!/bin/bash

echo "100.0 CONFIDENCE"
echo "----------"

FILE=$1

# if no second argument was given, just analyze one file
# the one given as first argument
if [ -z "$2" ]
then
	RES=$FILE
	if [ -f "$RES" ]
	then
		cat $RES | grep ",100\.00$" | wc -l
	fi

else

# if second argument was given, representing range of subbatches for this input
# to run the stats on - then run on given number of batches
# (input will be part of the filenames to be monitored)

	RANGE=${@:2}
	for NR in $RANGE
	do
		RES=shared_sshfs/"$FILE"_"$NR"_matches.csv
		if [ -f "$RES" ]
			then
			printf "$NR "; cat $RES | grep ",100\.00$" | wc -l		
		fi	
	done

	echo "-------------------------"
	printf "ALL "; cat shared_sshfs/"$FILE"_* | grep ",100\.00$" | wc -l

fi
