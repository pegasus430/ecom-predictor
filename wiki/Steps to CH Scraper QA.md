# Steps to CH Scraper QA #

*********************************************

single url testing via browser accessing the scraper server

*********************************************
http://52.1.156.214/get_data?url= <url>

example: http://52.1.156.214/get_data?url=http://www.walmart.com/ip/38067903

*********************************************

single url testing on the scraper server

*********************************************

curl localhost/get_data?url=<url>


**********************************************

## Testing on scraper server - small list testing ##

**********************************************


1) get access to a scraper server

ssh ubuntu@52.1.156.214


2) check bitbucket.org/dfeinleib/tmtext (on brower)

	for any updates to CH scrapers

	- click on pull requests

	- look at open pull requests

	- look at merged requests

	(any commits or merge to master for special_crawler)


3) on the scraper server (this step is to update server with master code)

	> cd tmtext

	> git fetch

	> git rebase

	> cd special_crawler

	(I confirm the files committed have been updated)

	> su kill -SIGHUP 933


The step above is to restart python:

Check the running processes: ps xau | grep uwsgi

These are the processes that respond to the curl localhost/get_data request.

Find the process id that has the “Ss” in the line, as opposed to “Sl”

Here the process id is 933

Restart python: sudo kill -SIGHUP 933

Differently from what the command name suggests, this will actually not kill the process but tell it to re-start (-SIGHUP option).

Check the process: ps xau | grep uwsgi

You will notice that all the process ids of the “Sl” processes have changed.



4) scrapers are ready for testing


5) go back to /home/ubuntu and create a test directory for yourself

I have winnie_test.  Under winnie_test, I have a directory for each site scraper.


6) create csv lists for testing

- for instance under walmart, I have walmart_webc.csv to test supplemental content changes

(site url lists are in repo: /tmtext/special_crawler/url_lists directory)


7) please see winnie_test for scripts to run a list 

the script I commonly use is curlurls.py which skips over comments in the csv file.

(scripts for small batch testing are in repo: /tmtext/special_crawler/url_lists directory)

usage:  python ../curlurls.py <csv file> <outdir>

example:  to run in the walmart dir

> python ../curlurls.py walmart_webc.csv webc10


8) check results

a.  if you have previous good results (if you run yesterday and output dir was webc8, you want to compare those)

example:  

> cd web9c

> diff 1.txt ../webc8    # this is to compare with previous run

b.  if you don't have previous results, you have to look at each json output file and verify by opening the url in the browser and see if scraper extracted all the correct info.

c.  note any new fields, changes to the site, changes to the product pages

d.  things like review count might change; products going out of stock
(you can confirm by viewing url in browser)

e.  anything else change, you would need to check the product url in browser and flag another problems/issues.

f.  useful ways to do check: grep <fields> *.txt  and compare to previous working directories


9) when checking a new bug report, keep adding the problem urls to the csv list.  

- always check previously working urls to make sure new fix did not break working urls.

- I like adding a comment with a "#" to keep track of what scraper should exrract or what bug is being fixed.


10) open/close/comment bug reports.

report issues with urls examples when finding problems with the scraper. 


**********************************************

## Testing on elsa - large batch/all site crawl ##

**********************************************

1) log on to elsa (http://elsa.contentanalyticsinc.com)

(elsa will pull scraper code from master) 


2) if batches you need are not already on elsa, load a batch or full-site url list onto server

(via content health/new batch gui)


3) coordinate with Adriana before re-crawling


4) do the crawl, do_stats, filter steps for the batch

(via system/site crawler, system/do_stats monitor, system/filters gui)


5) analyze and sanity check the batch in general

(via content health gui)

look at filters/summary table

use result table to click on urls to verify

look for problem areas/issues to see if they are fixed

focus on issues being fixed/features being added

use categories/brands to isolate groups for testing	

note anything suspicous by comparing numbers from current crawl to previous dates

note any red flags items


6) step 5 where another QA person would be great to help with sanity checking


7) (the more eyes the better)


**********************************************

## release to tmtext production ##

**********************************************

1) when scraper is fully verified with no issues with scraper testing & large batch testing on elsa, request a scraper release to production branch the production branch will automatically be used by all demo/sales/customer servers