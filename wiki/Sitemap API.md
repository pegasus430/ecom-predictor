**Outdated, needs update with new spiders and tasks**

# Purpose #

Crawl sitemap for retail website, It could be shelf urls, item urls, etc

# Endpoints #

API is asynchronous. After creating request it is placed in processing queue.

## Authorizations ##

Request must contain basic authorization. Default user `admin:p38YuqNm(t58X8PaV45%`

## Create request ##

Method: `POST`

Content-Type: `application/json`

Development endpoint (for prelim QA):

http://sitemap.contentanalyticsinc.com:8080/request

Production endpoint:

http://sitemap.contentanalyticsinc.com/request

Example:

```
#!js

{
  "request": {
    "type": "shelf_to_item_urls", 
    "retailer": "walmart.com", 
    "options": {
      "urls": [
        "https://www.walmart.com/browse/kitchen-appliances/blenders/4044_90548_90546_4831"
      ]
    }
  }
}
```

Example answer:

```
#!js

{
    "request_id": "123", 
    "status": "received"
}
```

Check `message` field if status is `error`. Use `request_id` value for checking status of request

## Check request state ##

Method: `GET`

Development endpoints (for prelim QA):

http://sitemap.contentanalyticsinc.com:8080/request/<REQUEST_ID>

Production endpoints:

http://sitemap.contentanalyticsinc.com/request/<REQUEST_ID>

Example answer:

```
#!js
{
    "file": "http://sitemap.contentanalyticsinc.com/123/resources/results.zip", 
    "message": "Success", 
    "request_id": 123, 
    "status": "ready"
}

```

`file` field contains url at archive with result files

Possible states:

* received
* processing
* ready
* error

Check `message` field if status is `error`

# Dashboard #

Development: http://image-download-api.contentanalyticsinc.com:8080

Production: http://image-download-api.contentanalyticsinc.com

Dashboard allows review requests and their state, check results, make tests

# Walmart #

Spider: `walmart.py`

## Crawl list of items from shelf page ##

**Request arguments**, mandatory are **marked**:

**retailer**: walmart.com

**type**: shelf_to_item_urls

options:

* **urls** - array of shelf urls for scraping item urls
* all - boolean value to scrape all items via price filters. Walmart shows 1000 items only by default

## URLs/UPCs to Amazon URLs ##

**Request arguments**, mandatory are **marked**:

**retailer**: walmart.com

**type**: upc_to_asin

options:

* **urls** - array of Walmart URLs

or

* **upcs** - array of UPCs

# Target #

Spider: `target.py`

## Crawl list of shelf pages ##

**Request arguments**, mandatory are **marked**:

**retailer**: target.com

**type**: sitemap_to_shelf_urls

## Crawl list of items from shelf page ##

**retailer**: target.com

**type**: shelf_to_item_urls

options:

* **urls** - array of shelf urls for scraping item urls
* exclude - array of categories id to exclude from result (5xsxe - Movies, music & books)

## Crawl all items ##

It is crawling list of shelf pages and all items for each of them. Each shelf page has own CSV file with item urls

**retailer**: target.com

**type**: sitemap_to_shelf_to_item_urls

options:

* exclude - array of categories id to exclude from result (5xsxe - Movies, music & books)

## Crawl all items in one file ##

It is the same task as **sitemap_to_shelf_to_item_urls** but stores items in one file

**retailer**: target.com

**type**: sitemap_to_item_urls

options:

* exclude - array of categories id to exclude from result (5xsxe - Movies, music & books)

Create request example:

POST endpoint http://sitemap.contentanalyticsinc.com/request
```
#!js

{
  "request": {
    "type": "sitemap_to_item_urls", 
    "retailer": "target.com", 
  }
}
```

Answer:
```
#!js

{
    "request_id": 65, 
    "status": "received"
}
```

Use 'request_id' to check status of request:

GET endpoint http://sitemap.contentanalyticsinc.com/request/65

```
#!js
{
    "request_id": 65, 
    "status": "processing"
}

```

Check 'file' field if status is 'ready' or 'message' field if status is 'error'

```
#!js
{
    "file": "http://sitemap.contentanalyticsinc.com/65/resources/results.zip", 
    "message": "Success", 
    "request_id": 65, 
    "status": "ready"
}

```

# Amazon #

Spider: `amazon.py`

## Crawl list of items from shelf page ##

**Request arguments**, mandatory are **marked**:

**retailer**: amazon.com

**type**: shelf_to_item_urls

options:

* **urls** - array of shelf urls for scraping item urls

# Jumbo #

Spider: `jumbo.py`

## Crawl list of items from shelf page ##

**Request arguments**, mandatory are **marked**:

**retailer**: jumbo.com

**type**: shelf_to_item_urls

options:

* **urls** - array of shelf urls for scraping item urls

# Ocado #

Spider: `ocado.py`

## Crawl list of items from shelf page ##

**Request arguments**, mandatory are **marked**:

**retailer**: ocado.com

**type**: shelf_to_item_urls

options:

* **urls** - array of shelf urls for scraping item urls

# Sainsburys #

Spider: `sainsburys.py`

## Crawl list of items from shelf page ##

**Request arguments**, mandatory are **marked**:

**retailer**: sainsburys.co.uk

**type**: shelf_to_item_urls

options:

* **urls** - array of shelf urls for scraping item urls

# Ah #

Spider: `ah.py`

## Crawl list of items from shelf page ##

**Request arguments**, mandatory are **marked**:

**retailer**: ah.nl

**type**: shelf_to_item_urls

options:

* **urls** - array of shelf urls for scraping item urls

# Jet #

Spider: `jet.py`

## Crawl list of all items ##

**Request arguments**, mandatory are **marked**:

**retailer**: jet.com

**type**: sitemap_to_item_urls

## Crawl list of items from shelf page ##

**Request arguments**, mandatory are **marked**:

**retailer**: jet.com

**type**: shelf_to_item_urls

options:

* **urls** - array of shelf urls for scraping item urls
* all - boolean value to scrape all items via price filters. Jet shows 504 items only by default

# Safeway #

Spider: `safeway.py`

## Crawl list of all items ##

**Request arguments**, mandatory are **marked**:

**retailer**: safeway.com

**type**: sitemap_to_item_urls

options:

* login - account email
* password - account password
or
* zip_code - location for scraping in Guest Mode

# Homedepot #

Spider: `homedepot.py`

## Crawl list of all items ##

**Request arguments**, mandatory are **marked**:

**retailer**: homedepot.com

**type**: sitemap_to_item_urls

# Instacart #

Spider: `intacart.py`

## Crawl list of all items ##

**Request arguments**, mandatory are **marked**:

**retailer**: instacart.com

**type**: sitemap_to_item_urls

options:

* login - account email
* password - account password
* store - storefront 

# Deploy API #

Server: sitemap.contentanalyticsinc.com

Run **deploy.sh** script

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

Add new spider in `spiders` directory and define mandatory property and method

```
#!python

class WalmartSitemapSpider(SitemapSpider):
    retailer = 'walmart.com'

    def task_shelf_to_item_urls(self, options):
```

## Add new request type ##

Create a new method in spider with the definition as `def task_<type>(self, options):`