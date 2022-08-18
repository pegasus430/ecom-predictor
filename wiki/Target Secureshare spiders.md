[TOC]

# Servers

## pre-install applications

geckodriver

firefox

Xvfb

node.js

## Test

http://52.90.103.121/
http://52.90.103.121/api

The code on this server should use this GIT branch: **api_target_secureshare**

# HTTP Basic auth

Login: upload

Password: #tss#1612*

# Test Server Login Info

Username: user

Password: pass

# Running The Server
```
#!bash
ssh ubuntu@52.90.103.121 -p 65321 
sudo stop targetsecureshare
sudo start targetsecureshare
```
For test machine, in addition start the nodejs app on the previous screen
```
#!bash
forever killall
cd ~/amazon_vendor_central_sandbox/tss/
forever start server.js
``` 

# miscellaneous

## Screenshots downloading

You can download the screenshots produced by the scraper. First, check scraper's logs and find a link that looks like `target-secureshare-submissions/2016/12/21/20161221397432-e5ad821d-26f0-4a79-9503-2599504b97b5.zip` - always starting with `target-secureshare-submissions/` and always ending with `.zip`. Copy it and paste in the form at http://52.90.103.121/get-screenshots

## watch log file

http://52.90.103.121/_log/logging.txt

## watch sandbox log

http://52.90.103.121/_log/logging.txt