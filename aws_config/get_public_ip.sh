#!/bin/bash

node=$1
vagrant ssh-config node$node 2>/dev/null | \
python -c 'import sys; import re; text=sys.stdin.read(); m=re.match(".*HostName ([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\s.*",text,flags=re.MULTILINE|re.DOTALL); print m.group(1)'