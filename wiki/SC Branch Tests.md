[TOC]



# What it is



This is a web-based tool for finding differences in spiders. You may think that this is another tool for testing.



# How it works



It runs 2 versions of the same spider against pre-defined sets of search terms. These 2 versions both have different branches. Then, 2 outputs of these spiders are compared and differences are displayed in reports.



# Why we need it



To make sure our changes we make (in new branches) do not break current code. In other words, that the features we implement and bugs we fix, do not produce new bugs.



# Where it is



http://sc-branch-tests.contentanalyticsinc.com/admin/



# Credentials



admin / Content12345



# How to use it



1. Log into the website - see "where it is"



2. Create a new TestRun: http://sc-branch-tests.contentanalyticsinc.com/admin/tests_app/testrun/add/



   Assume you changed the field "marketplace" and the branch name is Bug9999Marketplace. You want to compare it with Master.



   Exclude fields you want to ignore - "marketplace" in this case, in addition to the `_statistics` field which should always be excluded.



   Enter branch names, spider, and normally that's all.



3. Wait for about 5 mins and you'll see the report created at http://sc-branch-tests.contentanalyticsinc.com/reports/walmart_products/ (if you've been testing Walmart). You may choose the spider at http://sc-branch-tests.contentanalyticsinc.com (after you log in).



4. After the TestRun is finished, the status of your report will be Passed if there are no issues, or Failed otherwise. You'll see the list of differences at the same page, in the appropriate TestRun report's row.



![Выделение_509.png](https://bitbucket.org/repo/e5zMdB/images/4203903360-%D0%92%D1%8B%D0%B4%D0%B5%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5_509.png)



![Выделение_510.png](https://bitbucket.org/repo/e5zMdB/images/1519541213-%D0%92%D1%8B%D0%B4%D0%B5%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5_510.png)