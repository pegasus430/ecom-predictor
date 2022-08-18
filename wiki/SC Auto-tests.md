[TOC]

# Goal

These auto-tests are supposed to solve the following issues:

1) automatically detect the site changes that cause invalid (or missing) data to be returned - and send notifications,

2) provide a useful way to validate the spiders output, giving the developers a better way to test their new code (if compared to the testing "by eyes")

# Features

Scraping the non-structured data is not a very robust way to get the information. Sites are changing, closing for maintenance, throwing captchas... It's not only important to **find out if the site has changed**, but it's also important to **avoid sending false-positive alerts when the site is just having a 5-minute short downtime** or something like that.

* Field-level check - the value of each field is validated against a list of pre-defined rules; like "product title should not be longer than 50 words"; "product url should not contain spaces or tags" etc.

* Dataset-level check - the whole result file is checked as well, allowing to find missing products, scraper errors, wrong number of results (for example, if Amazon should return 15000 products for search term "iphone battery" but only 150 products have been scraped - then it means the spider is not working correctly)

* Sufficiency - a single search term is not a very good way to validate with, so every **test run** consists of at least 10 test requests (aka search terms). It reduces the chance that the spider is working fine on one search term, while it fails (and we don't know about about) on another search term.

* Reliability - every spider is marked as **failed** only if the last 5 test runs failed. It helps to avoid situations when a short site downtime causes a false-positive alert to be sent. The alert is sent only if the spider continues to return invalid data for at least a few hours. Also, there is a 'threshold' logic - sometimes, search requests fail, so we can just let them fail. The alert won't be sent if there are less than N% of failed requests (currently, 10%). So, if 10% of all the search requests failed - it's considered to be ok. Only if more than 10% of all the test requests fail, then an alert is sent.

* Portability - the **test requests** and the **field validators** are configured in a base class and included in every spider's class. It makes it very easy to implement the validation for a new spider. A developer only needs to set the test requests, **ignored** and **optional** fields, tweak field validators (often it's not even needed), and that's all.

* Non-intrusive design - the spiders will continue to work exactly the same as before. Only if the **validation flag** is added, the spiders will be executed in the "validation" mode. It helps to avoid bugs while running in production, and also it does not add any extra CPU usage in production.

# Web application

There is a web applicaton for checking the spiders' state.

Dashboard URL: http://52.0.7.54:9090/tests/ (you should log in before, see below).

## Credentials

URL for authentication: http://52.0.7.54:9090/admin/
Login / password: admin / Content12345

## Desired state

All the spiders should have "passed" state:

![2015-05-20_2020.png](https://bitbucket.org/repo/e5zMdB/images/1558254833-2015-05-20_2020.png)

If a spider has a red FAILED status, then you may click on its name and see the list of its test runs:

![2015-05-20_2024.png](https://bitbucket.org/repo/e5zMdB/images/4183157950-2015-05-20_2024.png)

A **test run** is a list of test requests (aka search terms) that are executed during 1 batch. So, the test app takes about 10 test requests, and executes them one by one.

Ok, so you see the list of the test runs at the screenshot above. You can click at the test run and see the failed test requests (click at each test request to see the errors):

![2015-05-20_2031.png](https://bitbucket.org/repo/e5zMdB/images/1492945023-2015-05-20_2031.png)

there you'll see both dataset-level and field-level errors. Field-level errors will also display the number of the row in the data file where that error was found; and also the value of the field that did not pass the validation.

If you're a developer, download the data file and the log file and analyze the found issues.

# How it works

## Spider level

Every spider now has a new **validation flag** - and extra command-line argument `-a validation=1`. In this mode, the spider will be executed as normally, but a new signal will be called on "on_close" event and the list of found issues will be printed into STDOUT.

## Web-application level

There is a Django command called `check_spider`. It takes a random spider (or the particular spider if you provide the spider name), and creates a new test run for it. After it's finished, it updates the database and sends alerts if needed.

Every spider has Validator classes settings - a class that contains the list of **optional fields**, **ignored fields**, **test requests**.

* optional fields - the fields that should have a value in at least 1 row. So, if some products have "model", other don't have - then treat the field as optional.

* ignored fields - the fields that are ignored at all. So, if the site does not return the UPC code for any product, add this field to the list of ignored fields. DO NOT add the fields to this list if it has values! You will reduce the test coverage!

* percent_fields - the fields that are will be add to ERRORS if percent of inadmissible value more than percent_limit.

* test requests - there should be some fields that return 0 results, and some fields that return from X to Y results. Sites don't return fixed number of results, so we're using a range.

* ignore_log_errors etc. - all these settings are quite clear, try to "grep" the code to get the idea.

# Error codes and identifiers

* log_issues

    * errors found - there were some spider errors (python code generated an exception; or the ERROR even has been logged)

    * duplicated requests - there were 2 or more requests generated to the same location; if often means that something is not working as expected

    * offsite filtered requests - there were requests generated to some 3rd party websites; it often means the spider is not working as expected

* ranking

    * products missing - some products have not been scraped (but should). It may happen because of many reasons (failed captcha, 500 server error, http timeout etc.); each case should be investigated by a developer

* field-level errors: they have a digital prefix indicating the number of the row where that "bad" value was found. Then the field name goes, then its value. Example: `3   {'title': ''}`. It means, the field "title" is empty at row number 3. Another example: `15  {'image_url': '<strong>broken</strong>'} - the "image_url" field has a bad value with HTML tags, while it should have something like an image URL.

# Cache

It's only for development/debugging purposes! You can enable the cache by executing the "check_spider" command this way:

```
python manage.py check_spider amazon_products enable_cache
```

this will probably speed up things, but it will take the data from the cache, not from the actual site.

# Code update

Right now the automated code updates are not implemented. Will be soon. For now, just log into the server (ubuntu user, ubuntu_id_rsa key), authenticate as web_runner user, activate web_runner environment, cd into /home/web_runner/repos/tmtext/product_ranking_auto_tests, pull master, and then re-run manage.py:

```
./manage.py runserver 0.0.0.0:9090
```

# Server

http://ranking-auto-tests.contentanalyticsinc.com/tests/

Login: admin

Password: Content12345

# Bugzilla ticket

There is a BZ ticket regarding this feature: https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=21