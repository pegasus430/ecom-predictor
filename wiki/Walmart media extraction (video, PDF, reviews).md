The script *walmart_media_extraction/extract_walmart_media.py* checks for a given Walmart product if it has 

1. any special media available on its product page (videos or specification PDF) and returns their source URLs if found.
2. product reviews, and returns the total number of reviews and value of average review (in stars, 0-5)

## Note:

The version of this service that is currently compatible with the tmcrawler crawlers and being used by them is on the **`walmart_media_old` branch**.

The version of the service on the `master` branch is the implementation of the "special crawler", which is an extension of this service (but extracts more data on walmart products), and its documentation can be found on https://bitbucket.org/dfeinleib/tmtext/wiki/Special%20crawler

Usage: input and output
========================

The script can be run from command line, with

###1. walmart media:###

* **input** = walmart product URL (must be of the form `http://www.walmart.com/ip/<product_id>`)
* **output** = video and PDF URLs, if any, in JSON format (if for a given product the video/PDF doesn't exist, the value of the corresponding JSON field will be null)

###2. walmart reviews:###

* **input** = walmart product URL (must be of the form `http://www.walmart.com/ip/<product_id>`)
* **output** = total reviews and average review, in JSON format, both numbers represented as strings (if for a given product there are no reviews, the value of the corresponding JSON field will be null)

##Example usage and output (local):##

    $ python extract_walmart_media.py http://www.walmart.com/ip/14245213
    {"pdf_url": "http://media.webcollage.net/rwvfp/wc/cp/11581706/module/cpwalmart/_cp/products/1333731773759/tab-c3103441-c635-40ab-9aa6-4fab48aff87d/resource-18b92a11-1808-4f63-88c6-5a8a3d5a6a86.pdf", "video_url": "http://media.webcollage.net/rwvfp/wc/cp/11581706/module/cpwalmart/_cp/products/1333731773759/tab-f91f669a-238f-487b-affb-c4866de8b1a7/resource-46e97959-65f8-4dc2-8970-d7192f165da5.mp4.flash.flv"}

    $ python extract_walmart_media.py  http://www.walmart.com/ip/23848268 
    {"pdf_url": null, "video_url": null}


REST API - client
======================

The script also has a REST interface

The URL for getting any data from the service looks like:

    <host>/get_walmart_data/<optional_parameter>/?url=<walmart_product_page_url>

with an optional parameter to specify the data type:

- PDF - get URL of PDF for the product (JSON format)
- video - get URL of video for the product (JSON format)
- media - get both PDF and video (JSON format)
- reviews - get reviews data for the product (JSON format)

Giving no option of these as the parameter leads to default behaviour of returning **all data** above (in JSON format).

### Status codes

    200 - data extracted and returned successfully
    404 - resource not found or invalid usage

These are the 5 options briefly described above:

### 1. for all data - GET method: `get_walmart_data` ###

    <host>/get_walmart_data/?url=<walmart_product_page_url>

##Example call:##

    $ curl 54.88.158.61/get_walmart_data/http://www.walmart.com/ip/1234
    {
      "average_review": "5",
      "pdf_url": null,
      "total_reviews": "3",
      "video_url": null
    }

###2. for media data - GET method: `get_walmart_data/media`###

    <host>/get_walmart_data/media/?url=<walmart_product_page_url>

##Example call:##
    $ curl 54.88.158.61/get_walmart_data/media/http://www.walmart.com/ip/1234
    {
      "pdf_url": null,
      "video_url": null
    }

###3. for (only) PDF URL - GET method: `get_walmart_data/PDF`###

##Example call:##
    $ curl 54.88.158.61/get_walmart_data/PDF/?url=http://www.walmart.com/ip/1234
    {
      "pdf_url": null
    }

###4. for (only) video URL - GET method: `get_walmart_data/video`###

##Example call:##
    $ curl 54.88.158.61/get_walmart_data/video/?url=http://www.walmart.com/ip/1234
    {
      "video_url": null
    }

###5. for reviews data - GET method: `get_walmart_data/reviews`###

##Example call:##

    $ curl 54.88.158.61/get_walmart_media/reviews/?url=http://www.walmart.com/ip/34335838
    {
      "average_review": "3.3", 
      "total_reviews": "20"
    }


If there are any **errors**, the response will be still in JSON format (for consistency), with an `error` key and its corresponding value containing the error message.

**Example error response:**

    $ curl 54.88.158.61/get_walmart_data/?url=htt
    {
      "error": "Parameter must be a Walmart URL of the form: http://www.walmart.com/ip/<product_id>"
    }

REST API - server
====================

The REST service is hosted on a micro AWS instance with the name *tmtext-get-walmart-media* and the following public IP:

    54.88.158.61

and following private IP (in the network of AWS machines pertaining to the account, inside the VPC):

    10.0.0.185

**Setting up the server**

The script only depends 2 python modules:

- flask
- lxml

To install the service follow these steps:

* pull tmtext code from repo, switch to `walmart_media_old` branch.
* install python package manager and use it to install flask and lxml module, or use the `requirements.txt` file directly:

`sudo apt-get install python-pip`

`pip install -r requirements.txt`

* make sure port 80 is open
* run the script:

`cd tmtext/walmart_media_extraction`

`sudo ./walmart_media_app.py`

To do:
-------

* __Obs__: The script is able to correctly detect if there is an actual video on the page (regardless of presence of "Video" button), but it cannot yet detect other types of material shown when the "Video" button on the page is pressed. Example: product http://www.walmart.com/ip/14245213 contains other material aside from video

* The script can currently correctly detect and extract the following types of videos:
    - videos from media.webcollage (ex http://www.walmart.com/ip/14245213)
    - customer reviews videos (ex  http://www.walmart.com/ip/15018287) - for a product there is usually a main video loaded in the player, and a couple of other customer reviews videos available to view instead. The script returns the URL for the main video.

Some videos (a minority) are neither of these, and those are not extracted correctly 
yet. Example http://www.walmart.com/ip/19526003 , http://www.walmart.com/ip/22099816

The estimations below describe the distribution of video presence/absence and video types among walmart products.

Tests -- Statistics
=====================

Some statistics were computed on a random sample of 4000 Walmart products. Below the results on this sample are used to estimate the overall distribution:

* **18.1%** of Walmart products have either a 'Video' button on their page (or a video with no 'Video' button)
* for **68.1%** of these a video URL was successfully extracted by this utility
* **21.5%** of products with 'Video' button (or video) on their page didn't actually have a video, but other type of media. ex http://www.walmart.com/ip/29384562
* **10.2%** of products with videos had videos which were not identified by the utility (support needs to be added for these). ex http://www.walmart.com/ip/19526003, http://www.walmart.com/ip/22099816
* **70.2%** of products with videos have videos from webcollage (all correctly extracted). ex http://www.walmart.com/ip/14245213
* **1.8%** of products with videos have customer reviews videos (all correctly extracted). ex http://www.walmart.com/ip/15018287
* for **4.06%** of products with video (or 'Video' button) a webcollage video was found, even though 'Video' button was not available on the product page