## Overview ##

This is a crawler of reviews of tesco.com products.

This service depends on the following modules:

- scrapy


## Anatomy of tesco,com ##

Tesco uses [Bazaar Voice](http://www.bazaarvoice.com/) (BV) for reviews. Reviews are retrieved from BV via an AJAX request which populates a container DIV.

Fortunately, all BV' javascript library does is build a large URL to fetch reviews in JSON format.

Unfortunately, a secondary request is necessary to fetch a mostly configured URL with the `passkey` and other parameters.


## Usage ##

The crawler is a typical Scrapy app with the following additional parameters:

* start_url: The URL to fetch.
* start_url_fn: The path to a file which contains URLs to fetch (one per line).

For example, to scrape reviews of a single product and output the result to the console:

    scrapy crawl tesco_review -a start_url='http://www.tesco.com/direct/toni-guy-deep-barrel-waver/211-6304.prd?pageLevel=&skuId=211-6304' -t csv


For example, to scrape reviews of several products using a file for the URLs and write the output to a file:

    scrapy crawl tesco_review -a start_urls_fn=tesco_haircare.txt -t csv -o reviews.csv


## Environment Setup ##


The detailed instructions to setup the environment to test the server are:

1. [Setup VirtualEnv](VirtualEnv Setup)
1. [Setup Git](Git Setup)
1. Clone the git repository: `git clone git@bitbucket.org:dfeinleib/tmtext.git`
1. Change dir to the project's directory: `cd tmtext/tesco_crawler`
1. Create a virtual environment: `virtualenv --no-site-packages .`
1. Activate the virtual environment: `source bin/activate`
1. Install dependencies: `pip install scrapy`
1. Scrape a page by URL:


    `scrapy crawl tesco_review -a start_url='http://www.tesco.com/direct/toni-guy-deep-barrel-waver/211-6304.prd?pageLevel=&skuId=211-6304'`


1. Scrape a page using a file for URLs:


    `scrapy crawl tesco_review -a start_urls_fn=tesco_haircare.txt`