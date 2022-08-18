# Purpose #

Generate ZIP archive with product images for manual image submission

# Endpoints #

API is asynchronous. After creating submission it is placed in processing queue.

## Authorizations ##

Request must contain HTTP header `X-API-KEY` with API key value (default: `alo4yu8fj30ltb3r`)

## Create submission ##

Request must contain HTTP header `X-FEED-ID` with generated feed id. It must be unique. Use feed id for checking submission status.

Method: `POST`

Content-Type: `application/json`

Development endpoint (for prelim QA):

http://image-download-api.contentanalyticsinc.com:8080/submission

Production endpoint:

http://image-download-api.contentanalyticsinc.com/submission


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
      "image_type": "jpg", 
      "differences_only": ""
    }
  },
  "server": {
    "url": "http://test.contentanalyticsinc.com/", 
    "api_key": "test"
  }
}
```

Example answer:

```
#!js

{
    "feed_id": "test", 
    "status": "received"
}
```

Check `message` field if status is `error`

## Check submission state ##

Method: `GET`

Development endpoints (for prelim QA):

http://image-download-api.contentanalyticsinc.com:8080/submission/<FEED_ID>

Production endpoints:

http://image-download-api.contentanalyticsinc.com/submission/<FEED_ID>

Example answer:

```
#!js

{
    "feed_id": "test", 
    "file": "http://image-download-api.contentanalyticsinc.com:8080/test/resources/results.zip", , 
    "status": "ready"
}
```

`file` field contains url at archive with images

Possible states:

* received
* processing
* ready
* error

Check `message` field if status is `error`

# Dashboard #

Development: http://image-download-api.contentanalyticsinc.com:8080

Production: http://image-download-api.contentanalyticsinc.com

Dashboard allows review submissions and their state, check results, make tests

# Target #

Downloader: `target.py`

IMAGE NAMING REQUIREMENTS:

1. The main image will use the Target TCIN number .jpg. For example: 123456789.jpg
2. For additional images, use "_##". For example: 123456789_01.jpg, 123456789_02.jpg, etc.
3. File extension: Images must be in .jpg format

Therefore for TCIN = 123456789, images 1, 2, 3, etc. would be exported as: 123456789.jpg, 123456789_01.jpg, 123456789_02.jpg, etc.

**Submission arguments**:

retailer: target.com

type: images

options:

* image_type - image type for export: jpg, png, gif, tif
* differences_only - send only new images if value exists

# Amazon #

Downloader: `amazon.py`

**Submission arguments**:

retailer: amazon.com

type: images

options:

* image_type - image type for export: jpg, png, gif, tif
* naming_conventions - naming conventions

# Samsclub #

Downloader: `samsclub.py`

Images Naming Convention
All images must be named by the 13 digit UPC image name, followed by an underscore (_) and the appropriate image rank as speci ed below.
1. Use the product’s UPC/GTIN number that can be found in Retail Link by searching the item number.
2. Remove the last digit, and add zeros if necessary to the front to make the number of digits equal 13: 0012345678912_A.
3. Add an underscore (_) and an upper case letter after UPC image name to denote the image’s rank in the series of images (up to 9):
_A is the primary image, and _B through _I are the alternate images.
0012345678912_A, 0012345678912_B, 0012345678912_C, etc.
• FDA approved labels and FTC Energy Guide labels must be in the second position(_B).

Videos Naming Convention
All images must be named by the 13 digit UPC image name, followed by an underscore (_) and the word “VIDEO” at the end.
1. Use the product’s UPC/GTIN number that can be found in Retail Link by searching the item number.
2. Remove the check digit (the last number), and add zeros if necessary to the front to make the number of digits equal 13: 0012345678912.
3. Add an underscore (_) and an the word “VIDEO” at the end. 0012345678912_VIDEO.
Each item# can have 2 videos maximum on its product page. Then name the video  les with _A and _B su x.
Example:
0088818106039_VIDEO_A and 0088818106039_VIDEO_B

**Submission arguments**:

retailer: samsclub.com

type: images

options:

* image_type - image type for export: jpg, png, gif, tif

type: videos

No options

# Deploy API #

Server: image-download-api.contentanalyticsinc.com

Run **deploy** script

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

# Developing downloader for new retailer #

Add new downloader in `downloaders` directory and define mandatory property and method

```
#!python

class TargetImageSubmissionDownloader(ImageSubmissionDownloader):
    retailer = 'target.com'

    def task_images(self, options, products):
```

## Add new submission type ##

Create a new method in spider with the definition as `def task_<type>(self, options, products):`