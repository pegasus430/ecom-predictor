-- CODE --

2 separate scrapers:
	SC 
	CH (Content Health)

SQS Core code is here: /deploy/scrapy_daemon.py

/deploy consists of AWS-related scripts

/product-ranking/sqs_tests_gui  --->  deployed to http://sqs-tools.CAinc.com server

important branches:
	master 
	those branches are automatically pulled by the system:
		sc-production
		production (CH)

— OVERVIEW — 
* custom Load Balancer
* custom git pull logic 

* jobs run every midnight UTC
* every job state is being cached
* sqs core validates cache before processing
* sqs core consumes messages and spawns scraper processes
* sqs core deletes every message from the initial queue (processing time)
* sqs core adds a message to another queue and a job gets rescheduled in case of failure
* a django app is being used for monitoring
(product-ranking/sqs_tests_gui)

Product Ranking Spiders, see also SQS core / SQS cache and Tips & Tricks & Advice and Auto-tests and GUI tests and SC URLs tests and SC Branch Tests - for Developers;
see also Obsolete, old auto-tests page for this type of spiders
php server manages them

product-ranking = SC 

95% of things related to testing, debugging SQS core etc. are at http://sqs-tools.contentanalyticsinc.com/

admin:
	http://sqs-tools.contentanalyticsinc.com/admin / admin / SD*/#n\%4a

— IMPROVEMENTS —

* logging (Logentries, Elastic)
* more flexible scale up/down
* a different approach for job scheduler (an easier approach)
* an ability to deploy more flexibly without waiting till 00 UTC
* an ability test SQS Core from a custom dev branch/environment
* AWS Lambda ?