#!/bin/bash
seq 1 10 | xargs -P10 -I% vagrant ssh node% -c "pkill -9 -f run_crawler.sh"
