#!/bin/bash

# open URLs from file in browser:
# open in chrome each pair of URLs in a file containing a pair of URLs separated by a comma on each line

# take file as first argument
filename=$1

# keep track of line number, declare it as an int
linenr=1

# separator - so that you can read line by line in the for below
IFS=$'\n'
for line in `cat $filename`
do
	# if there is product name (quotes indicate it), remove it
	if [[ "$line" == *\"* ]]
		then
		line=`echo $line | cut -d'"' -f3 | cut -c 2-`
	fi

	# if there's a match
	if [[ "$line" == *,* ]]
		then
		echo "$line" | cut -d',' -f1 | xargs google-chrome
		second=`echo "$line" | cut -d',' -f2`
		if [ -n "$second" ]
		then
			echo "$second" | xargs google-chrome
		fi
		third=`echo "$line" | cut -d',' -f3`
		if [ -n "$third" ]
		then
			echo "$third" | xargs google-chrome
		fi
	# if there's only one result
	else
		google-chrome "$line"
	fi


	# print current line number
	echo $linenr
	linenr=$((1+linenr))

	# wait for user input before opening next pairs of urls
	read aux

done

unset IFS