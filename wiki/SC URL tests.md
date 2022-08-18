[TOC]

# What it is

It's a web application for testing SC spiders (only for "product urls" mode; will not work for "searchterms_str" mode).

# Why

Because the GUI SQS test tool takes too much time to process tasks; sometimes it's useful to have a quick way to test some URLs.

# How to test

Just a few examples

http://sc-tests.contentanalyticsinc.com/get_data?url=http://www.walmart.com/ip/37002591

OR

http://sc-tests.contentanalyticsinc.com/get_data?spider=walmart&url=http://www.walmart.com/ip/37002591

- the servers above are on `sc_production` branch. To test on master branch, replace domain to `sc-tests-master.contentanalyticsinc.com` 

# Credentials 
See https://bitbucket.org/dfeinleib/tmtext/wiki/General%20SC%20credentials

to update password - ssh to server and 
sudo htpasswd /etc/nginx/.htpasswd admin

enter and confirm new password

# Accepted params

* `url` - a product URL you want to test

* `spider` (optional) - spider name, like "amazon" or "walmart_shelf_urls_products".

Use `spider` param when you want to override the default (automatically detected) spider name. Sometimes you need this, because we have "shelf pages" scrapers for some spiders, and it's not clear whether you want to use the "shelf" spider or "product ranking" spider for the given URL.

# Code location

See /product-ranking/flask_server.py

# Server environment

Run by: 

* cd /home/web_runner/repos/tmtext/product-ranking
* /usr/bin/python /usr/bin/gunicorn --workers=3 --timeout=600 --bind 127.0.0.1:5000 flask_server:app