#!/bin/bash
seq 1 10 | xargs -P10 -I% vagrant rsync node%
