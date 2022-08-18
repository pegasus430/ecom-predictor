# Development Overview

## We have a large number of crawlers in 3 forms:

* Content Health, called CH crawlers

They are located in tmtext/special_crawler/
Some spiders to check for reference:
extract_dockers_data.py
extract_levi_data.py

* Scorecard/Insights, called SC crawlers

They are located in tmtext/product-ranking/product_ranking/spiders/
Some spiders to check for reference:
staples.py
jet.py

* Shelf, called shelf crawlers, which sometimes rely on the SC crawlers

They are located in tmtext/product-ranking/product_ranking/spiders/
Some spiders to check for reference:
staples_shelf.py
jet_shelf.py

In general, they are for crawling ecommerce web sites at large scale. 

Crawls are queued into SQS queue on AWS.

## Workflow

Work assignments are made in Bugzilla. Make sure to have your code peer-reviewed before merging anything.

Do not merge any code or deploy anything to production without prior written approval from QA team.

Bugzilla:

Priority = P. Highest priority is 9, lowest is 1
Bug type: Hotfix, Critical and Feature. Hotfix should be worked on first, regardless of priority. 

## Source code locations

CH = content health

SC = scorecard = product-ranking = insights

* product-ranking/sqs_tests_gui/ - the source code of our sqs-tools server
* product-ranking/product_ranking - SC sub-project
* CH scrapers are all in tmtext/special_crawler/
* shelf scrapers are sub-part of SC and located in the SC folder
* screenshot scrapers are part of SC

## Work items

Scrapers:

* Implementing new scrapers. These should be modeled on existing scrapers.

* Scraper improvements. Bug fixes for existing scrapers such as missing data, incorrect data, data not in correct fields; changes to ecommerce sites that are being scraped

Infrastructure:

* Better throttling / control over crawling

* Better logging to external log server so we can more easily understand errors

* Better testing tools - faster, easier to use

## Coding

* Please write clean code and use comments

[Please read more technical details here](https://bitbucket.org/dfeinleib/tmtext/wiki/Product%20Spider%20Programming)