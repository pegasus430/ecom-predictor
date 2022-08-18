[TOC]

# Servers

## Production

**Never** use this server for test purposes - anything you submit there will go live.

http://amazon-vendor-central.contentanalyticsinc.com

http://amazon-vendor-central.contentanalyticsinc.com/api

The code on this server should use this GIT branch: **vendor_central_prod**

## Test

http://amazon-vendor-central-test.contentanalyticsinc.com

http://amazon-vendor-central-test.contentanalyticsinc.com/api

The code on this server should use this GIT branch: **vendor_central_test**

## Development

This server contains latest features that are not ready for production yet.

http://amazon-vendor-central-dev.contentanalyticsinc.com

http://amazon-vendor-central-dev.contentanalyticsinc.com/api

The code on this server should use this GIT branch: **vendor_central_dev**

# HTTP Basic auth

Login: upload

Password: N*$%4DSz

# Test Server Login Info

Username: user

Password: pass

# Running The Server
```
#!bash
ssh -p 65321 ubuntu@amazon-vendor-central.contentanalyticsinc.com
screen -r
sudo python app.py
```
or
```
#!bash
kill `cat twistd.pid`
twistd web --wsgi app.app
```

For amazon-vendor-central-test.contentanalyticsinc.com, in addition start the nodejs app on the previous screen
```
#!bash
node server.js
``` 

# Logging

You can get logging information by going to http://amazon-vendor-central.contentanalyticsinc.com/_log/  
*logging.txt* purposed for general tasks (image and text submissions)  
*sales_logging.txt* purposed for logging Amazon Sales tasks 

# Screenshots downloading

You can download the screenshots produced by the scraper. First, check scraper's logs and find a link that looks like `vendor-central-submissions/2016/10/21/18544fd7-91e3-45e1-aa11-9b1d70c49e84.zip` - always starting with `vendor-central-submissions/` and always ending with `.zip`. Copy it and paste in the form at http://amazon-vendor-central-dev.contentanalyticsinc.com/get-screenshots