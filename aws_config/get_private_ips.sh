#!/bin/bash

# rewrite hosts file
echo "" > hosts
for node in "$@";
	do
	IP=`vagrant ssh -c 'ifconfig \
	 | python -c "import sys; import re; \
	 from pprint import pprint; a = (sys.stdin.read()).split(\"\n\");\
	 b=  map(lambda x: x.group(1), filter(None, map(lambda x: re.search(\"(\d+\.\d+\.\d+\.\d+)\",x) , a))) \
	 ; print b[0] "' \
	 node$node | grep -v WARNING`;
	 echo "node$node $IP" >> hosts;
done
