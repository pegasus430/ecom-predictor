# How Regression Works
Every day, after nightly regression testing, review data for changes.
Regression testing results can be viewed at:
http://regression.contentanalyticsinc.com:8080/regression/login/?next=/regression/

This interface is slow for reviewing data, an easier way is to get ssh access to a server from ITS and create a tunnel:
```
#!bash
ssh -L 127.0.0.1:5432:scraper-test.cmuq9py90auz.us-east-1.rds.amazonaws.com:5432 ubuntu@23.21.39.219
```
Then connect to the psql database through that tunnel:
```
#!bash
psql --username=root --host=localhost scraper_test
```

For testing, a bash script is run which spins up a new AWS instance, runs the regression testing on that new instance, and then terminates it. The only argument passed to this script is the name of the site.

Look for changes in structure, value, type and check the JSON.

# Adding A New Site

1) Copy a Jenkins job for regression and replace all references to the site name with the new site

2) Add the site to test_scraper_service.py

3) Add the site to regression_service_email_notification.py

Adding/Deleting Urls:
Log into http://regression.contentanalyticsinc.com:8080/regression/console/
Mass url imports for adding urls
Url samples for managing urls (scraper needs to run once for url imports to be added to samples)