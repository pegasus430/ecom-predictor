#!/bin/bash
# get urls and titles for all walmart urls in file provided as argument
for url in `cat $1`; do printf "$url\t"; curl $url 2>/dev/null | grep "<h1 class=\"productTitle\"" | python -c "import sys; line=sys.stdin.read(); import re; m=re.match('<[^>]*>([^<>]*)</h1>',line); print m.group(1)"; done
