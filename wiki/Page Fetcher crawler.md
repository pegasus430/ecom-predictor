## Overview ##

This is a simple scraper that takes the URLs to retrieve from a JSON service and stores the results of scraped pages back to said service.

The program depends on:

* scrapy
* requests
* [Captcha breaker](Captcha breaker)

## Usage ##

The crawler is a typical Scrapy app with the following additional parameters:

* service_url: URL of the URL service. This parameter is mandatory.
* limit: The maximum number of URLs to fetch from the URL service. By default, 100.
* captcha_retries: The number of times to try to solve a captcha. 0 means never solve captchas. By default, 10.

Sample usage limiting to 10 urls and 5 attempts to solve captchas:

    scrapy crawl url_service -a 'service_url=http://ec2-54-85-61-24.compute-1.amazonaws.com/services/' -a limit=10 -a captcha_retries=5

Sample usage with a default limit of 100:

    scrapy crawl url_service -a 'service_url=http://ec2-54-85-61-24.compute-1.amazonaws.com/services/'


## Environment Setup ##


The detailed instructions to setup the environment to test the server are:

1. [Setup VirtualEnv](VirtualEnv Setup)
1. [Setup Git](Git Setup)
1. Clone the git repository: `git clone git@bitbucket.org:dfeinleib/tmtext.git`
1. Change dir to the project's directory: `cd tmtext/page_crawler`
1. Create a virtual environment: `virtualenv --no-site-packages .`
1. Activate the virtual environment: `source bin/activate`
1. Install dependencies: `pip install scrapy requests`
