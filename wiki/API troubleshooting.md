* [amazon-vendor-central](#markdown-header-amazon-vendor-centralcontentanalyticsinccom)
* [bulk-import](#markdown-header-bulk-importcontentanalyticsinccom)
    * [Content import](#markdown-header-content-import)
    * [MC Exports](#markdown-header-mc-exports)
* [import.contentanalyticsinc.com](#markdown-header-importcontentanalyticsinccom)
    * [Email fetcher](#markdown-header-email-fetcher)
    * [Walmart Retail Link](#markdown-header-walmart-retail-link)
* [mediacompare.contentanalyticsinc.com](#markdown-header-mediacomparecontentanalyticsinccom)
* [converters.contentanalyticsinc.com](#markdown-header-converterscontentanalyticsinccom)
* [media-audit.contentanalyticsinc.com](#markdown-header-media-auditcontentanalyticsinccom)
* [imageprocess.contentanalyticsinc.com](#markdown-header-imageprocesscontentanalyticsinccom)
* [productid.contentanalyticsinc.com](#markdown-header-productidcontentanalyticsinccom)
* [restapis-itemsetup.contentanalyticsinc.com](#markdown-header-restapis-itemsetupcontentanalyticsinccom)
* [image-download-api.contentanalyticsinc.com](#markdown-header-image-download-apicontentanalyticsinccom)
* [submissions.contentanalyticsinc.com](#markdown-header-submissionscontentanalyticsinccom)
* [sitemap.contentanalyticsinc.com](#markdown-header-sitemapcontentanalyticsinccom)

# amazon-vendor-central.contentanalyticsinc.com #

Server is running Amazon Vendor Central Spider

Project branch **vendor_central_prod**, project folder `tmtext/amazon_submit_images` and spider `tmtext/product-ranking/product_ranking/spiders/submit_amazon_images.py`

### Location ####

`/home/ubuntu/`. Main files are `app.py` and `submit_amazon_images.py`

### Restarting ###

```
#!bash

kill `cat twistd.pid`
twistd web --wsgi app.app
```

### Logs ###

App: `/home/ubuntu/_log/`

Server: `/home/ubuntu/twistd.log`

Web driver: `/home/ubuntu/geckodriver.log`

### Testing ###

Version for QA is running on **amazon-vendor-central-test.contentanalyticsinc.com** server, project branch **vendor_central_test**

### Troubleshooting ###

* check logs
* check `home/ubuntu/_output` with screenshots for specific id
* check web driver: possible issues with updated Firefox or Selenium
* try to restart service and kill hanged web driver instances: geckodriver, firefox, Xvfb

### Other links ###

[Amazon Vendor Spider](https://bitbucket.org/dfeinleib/tmtext/wiki/Amazon%20Vendor%20Spiders)

# bulk-import.contentanalyticsinc.com #

Server is running several services:

* Content import (Pepsico, P&G)
* MC Exports

User: admin

password: Bulk-import.2014

Nginx config: `/etc/nginx/sites-enabled/000-default`

## Content import ##

Project folder `tmtext/content_parser` and `tmtext/various/pepsico_images.py` for Pepsico content import

### Location ###

`/var/web/tmtext/content_parser/`

### Restarting ###

```
#!bash

cd /var/web/tmtext/content_parser
sudo kill `sudo cat twistd.pid`
sudo twistd web --port=8888 --wsgi=api.app
```

### Logs ###

App and server: `/var/web/tmtext/content_parser/twistd.log`

Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

Pepsico import cron: `/tmp/pepsico_import.log`

### Testing ###

Run app on 443 port for QA
```
#!bash

cd /home/sergeev/tmtext_parser/content_parser
sudo kill `sudo cat twistd.pid`
sudo twistd web --port=443 --wsgi=app.app
```
### Troubleshooting ###

* check logs
* try to restart service
* go to http://bulk-import.contentanalyticsinc.com/crons after cron config update

### Other links ###

[Master Catalog XML import API (Content Parsin API Endpoint)](https://bitbucket.org/dfeinleib/tmtext/wiki/Master%20Catalog%20XML%20import%20API%20(Content%20Parsin%20API%20Endpoint))

## MC Exports ##

Project folder `tmtext/mc_exports`

### Location ###

`/var/web/tmtext/mc_exports/`

### Restarting ###

```
#!bash

cd /var/web/tmtext/mc_exports
sudo kill `sudo cat twistd.pid`
sudo twistd web --port=8999 --wsgi=api.app
```

### Logs ###

App and server: `/var/web/tmtext/mc_exports/twistd.log`

Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

### Testing ###

Run app on 8080 port for QA
```
#!bash

cd /home/sergeev/tmtext/mc_exports
sudo kill `sudo cat twistd.pid`
sudo twistd web --port=8080 --wsgi=app.app
```
### Troubleshooting ###

* check logs
* try to restart service
* check `Template Mapping File.xlsx` and retailer templates at S3 bucket https://console.aws.amazon.com/s3/buckets/retailer-template-files/?region=us-east-1&tab=overview#. They could be found in `/var/tmp/mc_exports` also
* update templates if necessary
* check product data received from MC 

### Other links ###

* [MC Export API](https://bitbucket.org/dfeinleib/tmtext/wiki/MC%20Export%20API)
* [Retail Template Generator API](https://bitbucket.org/dfeinleib/tmtext/wiki/Retail%20Template%20Generator%20API)
* [Master Catalog API Documentation](https://bitbucket.org/dfeinleib/tmtext/wiki/Master%20Catalog%20API%20Documentation)

# import.contentanalyticsinc.com #

Server is running several services:

* Email fetcher
* Walmart Retail Link

## Email fetcher ##

Project folder `tmtext/email_fetcher`. Cron is fetching Samsclub reports

### Location ###

`/usr/local/scripts/crons/`

Replace files to update service

### Logs ###

`/var/log/fetcher.log`

### Testing ###

Run fetcher. Fetcher is marking processed emails as read. Mark them as unread after tests.

### Troubleshooting ###

* check logs
* log in import_sams@contentanalyticsinc.com to check inbox emails by subject.

### Other links ###

[E-mails fetcher](https://bitbucket.org/dfeinleib/tmtext/wiki/E-mails%20fetcher)

## Walmart Retail Link ##

Project folder `tmtext/WalMartRetailLink`. Service is fetching Walmart reports

QA Nginx config `/etc/nginx/sites-enabled/retail_link`

QA Uwsgi config `/etc/uwsgi/apps-available/retail_link.ini`

### Location ###

`/var/www/tmtext/WalMartRetailLink`

### Restarting ###

```
#!bash

cd /var/www/tmtext/WalMartRetailLink
sudo kill `sudo cat twistd.pid`
sudo twistd web --port=8080 --wsgi=api.app
```

### Logs ###

App: `/var/www/tmtext/WalMartRetailLink/twistd.log`

QA App: `/var/log/flask-uwsgi/retail_link.log`

QA Uwsgi: `/var/log/uwsgi/app/retail_link.log`

### Testing ###

```
#!bash

cd /home/ubuntu/tmtext/WalMartRetailLink
sudo service uwsgi restart
```

### Troubleshooting ###

* check logs
* check reports at [Retail Link](http://retaillink.wal-mart.com)

# mediacompare.contentanalyticsinc.com #

Service to compare images and videos.

Project folder `tmtext/image_matching_api`

Nginx config: /etc/nginx/sites-enabled/image-matching-api

### Location ###

`/var/web/tmtext/image_matching_api`

### Restarting ###

Service is running by docker
```
#!bash

cd /var/web/tmtext/
git pull
sudo docker restart api_media_compare_18
```

### Troubleshooting ###

Try to restart service. Ask ITs to do it if `sudo` is not working

### Other links ###

[Image Matching](https://bitbucket.org/dfeinleib/tmtext/wiki/Image%20Matching)

# converters.contentanalyticsinc.com #

Service for different converters

Project folder `tmtext/master_category`

Nginx config `/etc/nginx/sites-enabled/mastercategory_uwsgi`

### Location ###

`/home/ubuntu/tmtext/master_category`

### Restarting ###

```
#!bash

source /home/ubuntu/venv/mastercategory/bin/activate
cd /home/ubuntu/tmtext/master_category
nohup uwsgi --ini app.ini &>uwsgi.log &
```
or 
`kill -HUP master-pid`. Execute `ps afx` to look up pid of master `uwsgi` process

### Logs ###

App: `/home/ubuntu/tmtext/master_category/app.log`

Uwsgi: `/home/ubuntu/tmtext/master_category/uwsgi.log`

Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

### Testing ###

Dev repo is located at `/home/ubuntu/tmtext_dev`

```
#!bash

source /home/ubuntu/venv/mastercategory/bin/activate
cd /home/ubuntu/tmtext_dev/master_category
kill `cat twistd.pid`
PYTHONPATH=/home/ubuntu/tmtext_dev/master_category /home/ubuntu/venv/mastercategory/bin/twistd web --port="tcp:8080" --wsgi app.app
```

### Troubleshooting ###

* check logs
* try to restart service
* check product data received from MC
* check `/home/ubuntu/tmtext/master_category/_uploads`

### Other links ###

[Master Catalog API Documentation](https://bitbucket.org/dfeinleib/tmtext/wiki/Master%20Catalog%20API%20Documentation)

# media-audit.contentanalyticsinc.com #

Service for Media Audit

Project folder `tmtext/mediaaudit`

Nginx config `/etc/nginx/sites-enabled/mediaaudit`

Supervisor config `/etc/supervisor/conf.d/mediaaudit.conf`

Uwsgi config `/var/web/tmtext/mediaaudit/app.ini`

### Location ###

`/var/web/tmtext/mediaaudit`

### Restarting ###

```
#!bash

sudo supervisorctl restart mediaaudit
```

### Logs ###

App: `/var/web/logs/mediaaudit.log`

Nginx: `/var/web/logs/nginx/access.log`, `/var/web/logs/nginx/error.log`

### Testing ###

Run service on 8080 port for QA
```
#!bash

source /home/sergeev/tmtextenv/bin/activate
cd /home/sergeev/tmtext/mediaaudit
nohup python app.py >>app.log 2>&1 &
```

### Troubleshooting ###

* check logs
* try to restart
* check CH spiders results
* check Media Compare service at mediacompare.contentanalyticsinc.com
* check images in S3 bucket `rich-media-audit`

### Other links ###

* [Media Audit. Copying Scene7 images to Amazon S3 instance](https://bitbucket.org/dfeinleib/tmtext/wiki/Media%20Audit.%20Copying%20Scene7%20images%20to%20Amazon%20S3%20instance)
* [Image Audit](https://bitbucket.org/dfeinleib/tmtext/wiki/Image%20Audit)
* [Rich Media Brand Audit](https://bitbucket.org/dfeinleib/tmtext/wiki/Rich%20Media%20Brand%20Audit)

# imageprocess.contentanalyticsinc.com #

Service for nutrition image detection

Project folder `tmtext/nutrition_info_images`

Nginx config `/etc/nginx/sites-enabled/nutrition_images`

Uwsgi config `/etc/uwsgi/apps-enabled/nutrition_images.ini`

### Location ###

`/home/sergeev/tmtext/nutrition_info_images`

### Restarting ###

`sudo /etc/init.d/uwsgi restart`

### Logs ###

App: `/var/log/flask-uwsgi/nutrition_images.log`

Nginx: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

### Testing ###

Run service on 8080 port for QA

### Troubleshooting ###

* check logs
* try to restart
* update classifier

### Other links ###

* [Nutrition images service](https://bitbucket.org/dfeinleib/tmtext/wiki/Nutrition%20images%20service)
* [Servers Deployment - CH and Nutrition Images](https://bitbucket.org/dfeinleib/tmtext/wiki/Servers%20Deployment%20-%20CH%20and%20Nutrition%20Images)

# productid.contentanalyticsinc.com #

Service for managing product IDs

Project folder `tmtext/product_id_api`

Nginx config `/etc/nginx/sites-enabled/product_id_api`

Supervisor config `/etc/supervisor/conf.d/product_id_api.conf`

Uwsgi config `/var/web/tmtext/product_id_api/app.ini`

### Location ###

`/var/web/tmtext/product_id_api`

### Restarting ###

```
#!bash

sudo supervisorctl restart product_id_api
```

### Logs ###

App: `/var/web/logs/product_id_api.log`

Nginx: `/var/web/logs/nginx/access.log`, `/var/web/logs/nginx/error.log`

### Testing ###

Run service on 443 port for QA
```
#!bash

source /home/sergeev/tmtextenv/bin/activate
cd /home/sergeev/tmtext/product_id_api
sudo DEV_CONFIG=1 PYTHONPATH=/home/sergeev/tmtext/product_id_api /home/sergeev/tmtextenv/bin/twistd web --port="tcp:443" --wsgi app.app
```
### Troubleshooting ###

* check logs
* try to restart
* check DB tables
* remove `app.db` for QA

# restapis-itemsetup.contentanalyticsinc.com #

Service for Walmart content submissions and other tools

Project folder `tmtext/rest_apis_content_analytics`

Nginx config `/etc/nginx/sites-enabled/myproject`

Username: root

Password: AR"M2MmQ+}s9'TgH

**For tool id page**

Username: tool

Password: K4p8a2heYx

### Location ###

`/home/ubuntu/tmtext/rest_apis_content_analytics`

### Restarting ###

```
#!bash

source /home/ubuntu/tmtextenv/bin/activate
cd /home/ubuntu/tmtext/rest_apis_content_analytics
kill `cat /tmp/fcgi.pid`
python manage.py runfcgi protocol=fcgi minspare=4 port=8010 host=127.0.0.1 maxspare=5 pidfile=/tmp/fcgi.pid
```

### Logs ###

Nginx: `/var/log/nginx/error.log`

### Troubleshooting ###

* check logs
* try to restart
* check request at [API Explorer](https://developer.walmart.com/#/explorer/items)
* Walmart API returns `SYSTEM_ERROR.GMP_GATEWAY_API getPartnerInfo` error sometimes. Repeat request in that case

### Other links ###

* [Walmart Rest APIs](https://bitbucket.org/dfeinleib/tmtext/wiki/Walmart%20Rest%20APIs)
* [Walmart.com REST API Sample responses](https://bitbucket.org/dfeinleib/tmtext/wiki/Walmart.com%20REST%20API%20Sample%20responses)

# image-download-api.contentanalyticsinc.com #

Service for extracting product images. It is using by Retail Submission API

Project folder `tmtext/retail_image_submission_api`

Nginx config `/etc/nginx/sites-enabled/retail_image_submission_api`

Supervisor configs `/etc/supervisor/conf.d/retail_image_submission_api.conf`, `/etc/supervisor/conf.d/retail_image_submission_downloader.conf`

Uwsgi config `/var/web/tmtext/retail_image_submission_api/app.ini`

### Location ###

`/var/web/tmtext/retail_image_submission_api`

### Restarting ###

```
#!bash

sudo supervisorctl restart retail_image_submission_downloader
sudo supervisorctl restart retail_image_submission_api
```

### Logs ###

App: `/var/web/logs/retail_image_submission_api.log`, `/var/web/logs/retail_image_submission_downloader.log`

Nginx: `/var/web/logs/nginx/access.log`, `/var/web/logs/nginx/error.log`

### Testing ###

Run service on 8080 port for QA
```
#!bash

cd /home/sergeev/tmtext/retail_image_submission_api
kill `cat twistd.pid`
DEV_CONFIG=1 twistd web --port=8080 --wsgi=app.app
DEV_CONFIG=1 nohup celery -A app.downloader.celery worker --concurrency=1 -B >>celery.log 2>&1 &
```

### Troubleshooting ###

* check logs
* try to restart
* remove `app.db` for QA

### Other links ###

[Retail image export API](https://bitbucket.org/dfeinleib/tmtext/wiki/Retail%20image%20export%20API)

# submissions.contentanalyticsinc.com #

Service for content submission and other retailer tasks

Project folder `tmtext/retail_submission_api`

Nginx config `/etc/nginx/sites-enabled/retail_submission_api`

Supervisor configs `/etc/supervisor/conf.d/retail_submission_api.conf`, `/etc/supervisor/conf.d/retail_submission_crawler.conf`

Uwsgi config `/var/web/tmtext/retail_submission_api/app.ini`

### Location ###

`/var/web/tmtext/retail_submission_api`

### Restarting ###

```
#!bash

sudo supervisorctl restart retail_submission_crawler
sudo supervisorctl restart retail_submission_api
```

### Logs ###

App: `/var/web/logs/retail_submission_api.log`, `/var/web/logs/retail_submission_api.err.log`, `/var/web/logs/retail_submission_crawler.log`

Nginx: `/var/web/logs/nginx/access.log`, `/var/web/logs/nginx/error.log`

### Testing ###

Run service on 8080 port for QA
```
#!bash

cd /home/ubuntu/tmtext/retail_submission_api
kill `cat twistd.pid`
DEV_CONFIG=1 twistd web --port=8080 --wsgi=app.app
DEV_CONFIG=1 nohup celery -A app.crawler.celery worker --concurrency=1 -B >>celery.log 2>&1 &
```

### Troubleshooting ###

* check logs
* try to restart
* remove `app.db` for QA

### Other links ###

[Retail submission API](https://bitbucket.org/dfeinleib/tmtext/wiki/Retail%20submission%20API)

# sitemap.contentanalyticsinc.com #

Service for sitemap spiders

Project folder `tmtext/sitemap_utilities/sitemap_service`

Nginx config `/etc/nginx/sites-enabled/sitemap_service`

Supervisor configs `/etc/supervisor/conf.d/sitemap_service.conf`, `/etc/supervisor/conf.d/sitemap_service_crawler.conf`

Uwsgi config `/var/web/tmtext/sitemap_utilities/sitemap_service/app.ini`

### Location ###

`/var/web/tmtext/sitemap_utilities/sitemap_service`

### Restarting ###

```
#!bash

sudo supervisorctl restart sitemap_service_crawler
sudo supervisorctl restart sitemap_service
```

### Logs ###

App: `/var/web/logs/sitemap_service.log`, `/var/web/logs/sitemap_service.err.log`, `/var/web/logs/sitemap_service_crawler.log`

Nginx: `/var/web/logs/nginx/access.log`, `/var/web/logs/nginx/error.log`

### Testing ###

Run service on 8080 port for QA
```
#!bash

cd /home/ubuntu/tmtext/sitemap_utilities/sitemap_service
kill `cat twistd.pid`
DEV_CONFIG=1 twistd web --port=8080 --wsgi=app.app
DEV_CONFIG=1 nohup celery -A app.crawler.celery worker --concurrency=1 -B >>celery.log 2>&1 &
```

### Troubleshooting ###

* check logs
* try to restart
* remove `app.db` for QA
* increase size of RAM: product urls/ids are saving at memory for duplication detection

### Other links ###

[Sitemap API](https://bitbucket.org/dfeinleib/tmtext/wiki/Sitemap%20API)