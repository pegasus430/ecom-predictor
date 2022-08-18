[TOC]

# What it is

Basically, it's just a convenient way to create a job and to get the results (and the logs) back from the SQS and the server(s). You can create as many jobs as you want, but please don't delete anything and sit tight - it takes from 5 min up to a few hours for a job to complete. Please remember about the "quantity" field - the higher the value, the more results are scraped and the longer you wait for the results.

It will not interfere with the production jobs, so it's always safe to use.

New spiders are added automatically, we just need to pull the latest master branch there.

*To add a new test job, click the "add" button in the right-upper corner. After you fill the data in and click "save", you can't change the job, so be attentive. After our script pushes the job you created into SQS, the status of the job changes into "pushed to sqs". After it's done, the status turns into "finished". If you see that, you're done - you may click the 'CSV' or 'Log' links and download the output CSV file (as it came from the spider, unsorted!) and the spider log (for debugging). 
*

# Use-cases

* QA team wants to make sure the spider(s) return correct data,

* QA team wants to find out the exact point of failure - spiders OR the data import\UI PHP part.

* SC developers want to perform bulk tests

* Somebody wants to estimate the execution time of some spider(s)

* Somebody wants to test the SQS

# Where it is

http://sqs-tools.contentanalyticsinc.com/admin/gui/job/

# Code location

See /product-ranking/sqs_tests_gui

# Server environment

Run /usr/bin/python /home/spiders/repo/tmtext/product-ranking/sqs_tests_gui/manage.py runfcgi protocol=fcgi minspare=4 port=8001 host=127.0.0.1 maxspare=5 method=threaded pidfile=/tmp/fcgi.pid

# More help

Check this video: https://drive.google.com/file/d/0B8ttf0X2ftVyTWd6MnhEUlZSSTA/view?usp=sharing

# How to create jobs (examples)

## ProductURL vs ProductURLS

There are 2 similar fields - Product URL and Product URLS. The first one is ONLY used to test the **SC individual URL mode**. The second one is ONLY used to test the **SC+CH mode (simulated CH mode)**. The outputs of these 2 modes are completely different:

* For SC individual URL mode, it's just the old SC output, but for a single URL (instead of many products returned by search term mode)

* For SC+CH mode, the output is the same as for the original appropriate CH spider