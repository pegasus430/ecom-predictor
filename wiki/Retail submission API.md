1. [Purpose](#markdown-header-purpose)
2. [Endpoints](#markdown-header-purpose)
    1. [Authorizations](#markdown-header-authorizations)
    2. [Create submission](#markdown-header-create-submission)
    3. [Check submission state](#markdown-header-check-submission-state)
3. [Dashboard](#markdown-header-dashboard)
4. Retailers
    1. [Target](#markdown-header-target)
    2. [Amazon](#markdown-header-amazon)
    3. [Dollar general](#markdown-header-dollar-general)
    4. [123stores](#markdown-header-123stores)
    5. [Google Manufacturer Center](#markdown-header-google-manufacturer-center)
    6. [Jet](#markdown-header-jet)
    7. [Walmart](#markdown-header-walmart)
    8. [Samsclub](#markdown-header-samsclub)
5. [Deploy API](#markdown-header-deploy-api)
6. [Development endpoint run](#markdown-header-development-endpoint-run)
7. [Add new retailer](#markdown-header-developing-spider-for-new-retailer)

# Purpose #

* Generate submission files and send them on retailer's website. Files generation based on `criteria` argument in request. It is using for requesting data from Master Catalog. *General cases*: send product images or text forms.
* Perform other actions on retailer's website. It is possible to send requests without `criteria` and data loading from MC. *General cases*: download reports or check some information

# Endpoints #

API is asynchronous. After creating submission it is placed in processing queue.

## Authorizations ##

Request must contain HTTP header `X-API-KEY` with API key value (default: `alo4yu8fj30ltb3r`)

## Create submission ##

Request must contain HTTP header `X-FEED-ID` with generated feed id. It must be unique.

Method: `POST`

Content-Type: `application/json`

Development endpoints (for prelim QA):

* http://submissions.contentanalyticsinc.com:8080/api/v1/sandbox/submissions

* http://submissions.contentanalyticsinc.com:8080/api/v1/submissions

Production endpoints:

* http://submissions.contentanalyticsinc.com/api/v1/sandbox/submissions

* http://submissions.contentanalyticsinc.com/api/v1/submissions


Example:

```
#!js

{
  "criteria": {
    "filter": {
      "products": [
        2750
      ]
    }
  }, 
  "submission": {
    "type": "images", 
    "retailer": "target.com", 
    "options": {
      "do_submit": false, 
    }
  }, 
  "server": {
    "status": "1", 
    "read_only": false, 
    "remote_user": "", 
    "user_id": 0, 
    "name": "Test", 
    "url": "http://pepsico-demo.contentanalyticsinc.com/", 
    "created_date": {
      "date": "2016-07-07 00:00:00", 
      "timezone_type": 3, 
      "timezone": "UTC"
    }, 
    "api_key": "d28ab4cd79d9cbb75467c267614f0266d2220b4f", 
    "id": 3
  }
}
```

Example answer:

```
#!js

{
    "submission_id": "test", 
    "status": "received"
}
```

Check `message` field if status is `error`.

submission_id is equal X-FEED-ID value, use it to check submission state.

## Check submission state ##

Method: `GET`

Development endpoints (for prelim QA):

http://submissions.contentanalyticsinc.com:8080/api/v1/sandbox/submissions/<submission_id>

http://submissions.contentanalyticsinc.com:8080/api/v1/submissions/<submission_id>

Production endpoints:

http://submissions.contentanalyticsinc.com/api/v1/sandbox/submissions/<submission_id>

http://submissions.contentanalyticsinc.com/api/v1/submissions/<submission_id>

Example answer:

```
#!js

{
    "submission_id": "test", 
    "file": "https://target-secureshare-submissions.s3.amazonaws.com/2017/04/13/test_results.zip", 
    "screenshots": "https://target-secureshare-submissions.s3.amazonaws.com/2017/04/13/test_screenshots.zip", 
    "status": "ready"
}
```

`file` field contains url at archive with generated files during submission

`screenshots` field contains url at archive with browser screenshots of the submission flow

Possible states:

* received
* processing
* ready
* error

Check `message` field if status is `error`

# Dashboard #

Development: http://submissions.contentanalyticsinc.com:8080

Production: http://submissions.contentanalyticsinc.com

User **default**, password **alo4yu8fj30ltb3r**

Dashboard allows review submissions and their state, check results. 

# Target #

Spider: `target.py`

S3 bucket: target-secureshare-submissions 

Domain: https://secureshare.target.com

Sandbox: http://submissions.contentanalyticsinc.com:8888/. Credentials: `user/pass`

Run sandbox: `node sandbox/tss/server.js` or as daemon `forever start sandbox/tss/server.js`

## Submissions ##

### Images (deprecated) ###

Uploading product images on Target

**Submission arguments**, mandatory are **marked**:

**retailer**: target.com

**type**: images

options:

* username - secureshare login
* password - secureshare password
* emails - list of addresses to send message
* subject - subject of message
* content - content of message
* **do_submit** - flag to make submission at the end

### Content ###

Sending exported MC template to e-mail

**Submission arguments**, mandatory are **marked**:

**retailer**: target.com

**type**: content

options:

* supplier_name - supplier name
* additional_emails - list of cc addresses
* **do_submit** - send e-mail to support@contentanalyticsinc.com if false 

# Amazon #

Spider: `amazon.py`

S3 bucket: vendor-central-submissions

Domain: https://vendorcentral.amazon.com

Sandbox: http://submissions.contentanalyticsinc.com:8889/. Credentials: `user/pass` or `ryan@contentanalyticsinc.com/pass`

Run sandbox: `node sandbox/avc/server.js` or as daemon `forever start sandbox/avc/server.js`

## Submissions ##

### Text ###

Uploading product data (HPC form) on Amazon Vendor Central

**Submission arguments**, mandatory are **marked**:

**retailer**: amazon.com, fresh.amazon.com, pantry.amazon.com, primenow.amazon.com

**type**: text

options:

* **primary** - AVC credentials: **email** - login, **password** - password, case_title - subject title for submission form
* **do_submit** - flag to make submission at the end
* emails - list of CC addresses
* differences_only - send only changed data
* submit_by_category - send separate request for each category
* submit_by_brand - send separate request for each brand
* item_limit - limit number of products in one form
* comments - description comments for submission form
* fields_only - list of fields to include at HPC form: long_description, browse_keyword, ingredients, usage_directions, safety_warnings, bullets

### Images ###

Uploading product images on AVC

**Submission arguments**, mandatory are **marked**:

**retailer**: amazon.com

**type**: images

options:

* **primary** - AVC credentials: **email** - login, **password** - password
* **do_submit** - flag to make submission at the end
* **naming_conventions** - images naming rules

### Credentials validation ###

Try to log in Vendor Central only

**Submission arguments**, mandatory are **marked**:

**retailer**: amazon.com

**type**: credentials_validation

options:

* **primary** - AVC credentials: **email** - login, **password** - password

### Remove images ###

Uploading file with removed images on Amazon Vendor Central

**Submission arguments**, mandatory are **marked**:

**retailer**: amazon.com

**type**: remove_images

options:

* **primary** - AVC credentials: **email** - login, **password** - password
* **do_submit** - flag to make submission at the end
* **file** - URL to download user's file
* **filename** - name of user's file
* emails - list of CC addresses

# Dollar general #

Spider: `dollargeneral.py`

## Submissions ##

### Content ###

Uploading exported template on SFTP server

**Submission arguments**, mandatory are **marked**:

**retailer**: dollargeneral.com

**type**: content

options:

* sftp_ip_address - SFTP server
* sftp_username - SFTP user
* sftp_password - SFTP password
* sftp_dir - SFTP directory for uploads
* destination_ip - this IP address is using in file naming

Options are defined in `config.json` file but could be overwritten by options from request. It allows develop UI at API caller side.

## Retailer config ##

File: `config.json`

Format: JSON

```
#!js

{
  "dollargeneral.com": {
    "sftp_ip_address": "54.175.228.114",
    "sftp_username": "magento",
    "sftp_password": "",
    "sftp_dir": "TODO",
    "destination_ip": "dollargeneral"
  }
}
```

# 123stores #

Spider: `one23stores.py`

## Submissions ##

### Content ###

Uploading exported template on SFTP server

**Submission arguments**, mandatory are **marked**:

**retailer**: 123stores.com

**type**: content

options:

* sftp_ip_address - SFTP server
* sftp_username - SFTP user
* sftp_password - SFTP password
* sftp_dir - SFTP directory for uploads
* destination_ip - this IP address is using in file naming

Options are defined in `config.json` file but could be overwritten by options from request. It allows develop UI at API caller side.

## Retailer config ##

File: `config.json`

Format: JSON

```
#!js

{
  "123stores.com": {
    "sftp_ip_address": "54.175.228.114",
    "sftp_username": "magento",
    "sftp_password": "",
    "sftp_dir": "TODO",
    "destination_ip": "123stores"
  }
}
```

# Google Manufacturer Center #

Spider: `google_mc.py`

## Submissions ##

### Content ###

Uploading exported template on SFTP server

**Submission arguments**, mandatory are **marked**:

**retailer**: google.com

**type**: content

options:

* **sftp_ip_address** - SFTP server
* **sftp_username** - SFTP user
* **sftp_password** - SFTP password
* **sftp_dir** - SFTP directory for uploads

# Jet #

Spider: `jet.py`

## Submissions ##

### Content ###

Uploading product data to Jet.com

**Submission arguments**, mandatory are **marked**:

**retailer**: jet.com

**type**: content

options:

* **test** - test API keys: {"user": "API user", "pass": "Secret"}
* **live** - live API keys: {"user": "API user", "pass": "Secret"}

### Check ###

Check status of submission. 

**Submission arguments**, mandatory are **marked**:

**retailer**: jet.com

**type**: check

options:

* **test** - test API keys: {"user": "API user", "pass": "Secret"}
* **live** - live API keys: {"user": "API user", "pass": "Secret"}
* **jet_file_id** - file id received from Jet

No need to check state after content submissions. It will be done automatically during processing.

## Additional data at response ##

Response has **data** with fields:

* jet_file_id - file id received from Jet
* products - array of products with SKU status and substatus
    * product_id - MC product id
    * sku - merchant defined SKU used for upload (vendor_item_sku_number, upc, asin or gtin)
    * sku_status - Jet product status
    * sku_substatus - Jet product substatus

# Walmart #

Spider: `walmart.py`

S3 bucket: walmart-submissions

## Submissions ##

### Content ###

Generating and uploading XML product feed to Walmart.com

**Submission arguments**, mandatory are **marked**:

**retailer**: walmart.com

**type**: content

options:

* **version** - XML version: `1.4.1` for restapis server, `3.1` for restapis-itemsetup server
* **consumer_id** - for 3.1 only
* **private_key** - for 3.1. only 
* item_limit - limit number of products in one XML

### Rich media ###

Generating and uploading XML rich media feed to Walmart.com

**Submission arguments**, mandatory are **marked**:

**retailer**: walmart.com

**type**: rich_media

options:

* item_limit - limit number of products in one XML

Submission is using restapis server.

### Check ###

Check status of submission. 

**Submission arguments**, mandatory are **marked**:

**retailer**: walmart.com

**type**: check

options:

* **version** - XML version: `1.4.1` for restapis server, `3.1` for restapis-itemsetup server
* **feed_id** - feed id received from Walmart
* feeds - list of feed ids

No need to check state after content or rich media submissions. It will be done automatically during processing.

## Additional data at response ##

Response has **data** with fields:

* feed_id - feed id received from Walmart
* default - source response from Walmart API

# Samsclub #

Spider: `samsclub.py`

## Submissions ##

### Images ###

Uploading product images on FTP server. It is using [external service](Retail image export API) to prepare images 

**Submission arguments**, mandatory are **marked**:

**retailer**: samsclub.com

**type**: images

options:

* **ftp_server** - FTP server
* **ftp_username** - FTP user
* **ftp_password** - FTP password
* **ftp_dir** - FTP directory for uploads (Images_01_FTP)

### Videos ###

Uploading product videos on FTP server. It is using [external service](Retail image export API) to prepare videos 

**Submission arguments**, mandatory are **marked**:

**retailer**: samsclub.com

**type**: videos

options:

* **ftp_server** - FTP server
* **ftp_username** - FTP user
* **ftp_password** - FTP password
* **ftp_dir** - FTP directory for uploads (Videos_02_FTP)

# Deploy API #

Server: submissions.contentanalyticsinc.com

Run **deploy.sh** script or follow step by step instruction

Packages and PostgreSQL:

```
#!bash

sudo apt-get update

sudo apt-get install -y libpq-dev
sudo apt-get install -y supervisor lib32z1-dev virtualenvwrapper
sudo apt-get install -y libffi-dev libssl-dev build-essential
sudo apt-get install -y libxml2-dev libxslt1-dev python-dev python-lxml

echo '# Setup PostgreSQL'
echo "# Installing dependencies..."
sudo apt-get install -y postgresql postgresql-client postgresql-contrib

# Create new database
echo "# Database creation..."
sudo su postgres -c psql template1 << EOF
ALTER USER postgres WITH PASSWORD 'password';
EOF
sudo su postgres -c "createdb retail_submission_api"
```

Note: development version is using local SQLite database `app.db`


```
#!bash

sudo mkdir /var/web
sudo chmod 777 /var/web
cd /var/web
git clone https://bitbucket.org/dfeinleib/tmtext.git
mkdir /var/web/logs
mkdir /var/web/logs/nginx
virtualenv tmtextenv
source tmtextenv/bin/activate
pip install -r tmtext/retail_submission_api/requirements.txt
```

requirements.txt:

```
#!python

Flask==0.12.2
Flask-Login==0.4.0
Flask-RESTful==0.3.5
Flask-SQLAlchemy==2.2
Jinja2==2.9.6
MarkupSafe==1.0
SQLAlchemy==1.1.10
Werkzeug==0.12.2
amqp==1.4.9
aniso8601==1.2.1
anyjson==0.3.3
argparse==1.2.1
asn1crypto==0.22.0
billiard==3.3.0.23
boto==2.47.0
celery==3.1.25
cffi==1.10.0
click==6.7
cryptography==1.8.1
enum34==1.1.6
idna==2.5
ipaddress==1.0.18
itsdangerous==0.24
kombu==3.0.37
ndg-httpsclient==0.4.2
packaging==16.8
paramiko==2.1.2
psycopg2==2.7.1
pyOpenSSL==17.0.0
pyasn1==0.2.3
pycparser==2.17
pyparsing==2.2.0
pysftp==0.2.9
python-dateutil==2.6.0
pytz==2017.2
requests==2.14.2
selenium==3.4.2
six==1.10.0
uWSGI==2.0.15
wsgiref==0.1.2
xlrd==1.0.0
xlwt==1.2.0
olefile==0.44
pillow==4.2.1
pytesseract==0.1.7
xlutils==2.0.0
```

API is using PhantomJS as main web driver http://phantomjs.org/download.html. Copy `phantomjs` file in virtual environment `bin` directory (or in system `bin`)

Nginx config:

```
#!bash

sudo tee /etc/nginx/sites-available/retail_submission_api <<EOF
server {
    listen      80 default_server;
    server_name _;
    charset     utf-8;
    client_max_body_size 75M;

    access_log /var/web/logs/nginx/access.log;
    error_log /var/web/logs/nginx/error.log;

    location /favicon.ico {
        access_log off;
        log_not_found off;
    }

    location /static {
        alias /var/web/tmtext/retail_submission_api/app/static;
    }

    location / {
        include uwsgi_params;
        uwsgi_pass 127.0.0.1:8000;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/retail_submission_api /etc/nginx/sites-enabled/retail_submission_api

sudo service nginx restart

```

Uwsgi config:

```
#!bash

sudo tee /var/web/tmtext/retail_submission_api/app.ini <<EOF
[uwsgi]
socket = 127.0.0.1:8000
chmod-socket = 664
uid = www-data
gid = www-data

chdir = /var/web/tmtext/retail_submission_api
virtualenv = /var/web/tmtextenv
home = /var/web/tmtextenv
wsgi-file = /var/web/tmtext/retail_submission_api/wsgi.py

master = true
processes = 4
threads = 2
harakiri = 60

buffer-size = 32768
die-on-term = true
vacuum = true

lazy-apps = true

EOF

```

Supervisor configs:

```
#!bash

sudo tee /etc/supervisor/conf.d/retail_submission_api.conf <<EOF
[program:retail_submission_api]
environment=PATH="/var/web/tmtextenv/bin"
directory = /var/web/tmtext/retail_submission_api
user = www-data
command = /var/web/tmtextenv/bin/uwsgi app.ini
redirect_stderr=true
stderr_logfile = /var/web/logs/retail_submission_api.err.log
stdout_logfile = /var/web/logs/retail_submission_api.log
stdout_logfile_maxbytes = 100MB
stdout_logfile_backups=30
autostart = true
autorestart = true
killasgroup = true
stopasgroup = true
stopsignal = INT

EOF

sudo tee /etc/supervisor/conf.d/retail_submission_crawler.conf <<EOF
[program:retail_submission_crawler]
environment=PATH="/var/web/tmtextenv/bin"
directory = /var/web/tmtext/retail_submission_api
user = www-data
command = /var/web/tmtextenv/bin/celery -A app.crawler.celery worker --concurrency=5 -B -s /var/tmp/celerybeat-schedule
redirect_stderr=true
stderr_logfile = /var/web/logs/retail_submission_crawler.err.log
stdout_logfile = /var/web/logs/retail_submission_crawler.log
stdout_logfile_maxbytes = 100MB
stdout_logfile_backups=30
autostart = true
autorestart = true
killasgroup = true
stopasgroup = true
stopsignal = INT

EOF

sudo service supervisor restart

```

## Development endpoint run ##

Note: development version is using local SQLite database `app.db`

Run API frontend: 

```
#!bash

kill `cat twistd.pid`
DEV_CONFIG=1 twistd web --port=8080 --wsgi=app.app
```

Logs are in **twistd.log**

Run backend:

```
#!bash

DEV_CONFIG=1 nohup celery -A app.crawler.celery worker --concurrency=1 -B >>celery.log 2>&1 &
```

Logs are in **celery.log**

# Developing spider for new retailer #

Add new spider in `spiders` directory and define mandatory properties:

```
#!python

class TargetSubmissionSpider(SubmissionSpider):
    retailer = 'target.com'

```

## Add new submission type ##

Create a new method in spider with the definition as `def task_<type>(self, options, products, **kwargs):`