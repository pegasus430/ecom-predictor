[TOC]

# General #

Cache system for SQS. When it can be usefull: when there are many tasks with the same search term or products list for some site. To not run each job, only first one will be executed and all other will receive its cached results. This rule applies only for jobs, which are requested same day. So if job result cached one day and then cache for it is requested on the next day, no cached result will be returned.


# Task options #

SQS tasks support few options to interact with the cache:

* `sqs_cache_get_ignore` (defaults to `false`) - if this key is set to true, it will force the task to run, even if there is fresh result for it in cache.
* `sqs_cache_save_ignore` (defaults to `false`) - if this key is set to true, then finished job result will not be saved to the cache.
* `sqs_cache_time_limit` (defaults to `day`) - this key indicates, that cached response must be not older then allowed age. If there will be cached response for some task, but it will be considered as old, it will be skipped. This key supports few values:
    - `day` - default value for this key. All cached records will be valid, if they were saved for current day.
    - `hour` - cached record will be valid, if it was created for current hour. For example, if cached result requested for task, which was started at 15:21, response will be valid, if it was saved between 15:00 and current time. *Important*: note, that value is valid only for current hour, but not for all responses, which were saved in the period of last hour (`14:21 - 15:21` - this is not correct, `15:00 - 16:00` - correct).
    - `30 minutes` - same as above, but for 30 minutes window.
    - `15 minutes` - same as above, but for 15 minutes window.


Example of task with the given parameters:

```
{
  'task_id': 162097, 
  'searchterms_str': 'monkey', 
  'cmd_args': {'quantity': 20}, 
  'site': 'amazon', 
  'server_name': 'test_server', 
  'sqs_cache_get_ignore': false, 
  'sqs_cache_save_ignore': false,
  'sqs_cache_time_limit': '30 minutes'
}
```


# Statistics #

Sqs and its cache statistics is saved and can be accessed from [this page](sqs-metrics.contentanalyticsinc.com/stats). Credentials for this page are: `admin / Conten12345`.Data, available from the page: daily number of raised instances, daily number of executed tasks, current number of running instances, tasks waiting in all sqs queues, hourly statistics of executed tasks, cached items count, most recently used cached items.
Additionally, every day at 00:00 UTC mail with basic statistics is sending to support@contentanalyticsinc.com.


# Clearing the cache #

All statistics and daily used cache counters are cleared every day right after daily email report is sent. But there is a possibility to manually clear cache data. This action is available at [this page](http://sqs-metrics.contentanalyticsinc.com/clear_cache). There are few checkboxed that can be selected to remove specifical data from cache: 

- `S3 keys to the cached data` is responsible for handling actual cache data. If you wish to just remove all cached responses, but not the statistics, it is enough just to select this option.
- `Stats of most used cached items` is responsible for just hadnling statistics of most used cached items.
- `Stats of the sqs: count of tasks and instances` is responsible for counters of daily raised autoscale instances and total exectuted tasks.
- `Stats of the urgent queue` is responsible for handling statistics of the urgent queue tasks.
After all required options selected, just submit with "Clear" button. Selected items will be cleared immediately.


# Debugging #

Some thoughts on matching jobs and finding their logs:

```
Some additional information about logs and data files for finished tasks:
- first of all, you need to find out, which server executed certain task (lets say, we have task from test_server with id 12345). To do this, you need to follow to this link http://52.1.192.8/search-files/, enter required id and server name (12345 in our case) and do search. You will receive list of all s3 files, which contain required id in its name.
- in the given list, press on the link with the required file which you want to check (csv, log, jl or progess files).
- if there is only a progress file for the task, this means that result for this task was received from cache. To find out exact result, you need to check remote instance starter log for the instance, on which this task was executed. In this log file you can find, which cached response was returned for the task. This record will look like this: "INFO:Got cached result for task 3149 (ruslan-test): /2015/09/17/17-09-2015____yubtv32luam6zy22lpa8u6zgigmc____stom--175903____single-product-url-request____walmart.".
- all you need then, is to copy the path "2015/09/17/17-09-2015____yubtv32luam6zy22lpa8u6zgigmc____stom--175903____single-product-url-request____walmart", and do second search on http://52.1.192.8/search-files/. You will see list of all files, which were returned for this task. 

Few words about s3 bucket with scraped data files: each key consists of few elemts, separated by the "____". This elements are: 
- "/2015/09/17/17-09-2015" - date, when instance was started
- "yubtv32luam6zy22lpa8u6zgigmc" - instance id
- "stom--175903____single-product-url-request____walmart." - task data
- "csv.zip", "log.zip", "jl.zip", "progress.zip" - final part of the key name, indicating different files for the task.
```


# Cron jobs #

Each day cron runs script to send email with statistics and clears all outdated records in cache db. This includes: all cached items, which are older then 7 days, executed tasks statistics for the passed day, number of most used cache items. 

# Workflow with cache web interface #

## Main workflow ##

### To get a cache need send the `POST` request: ###

`http://sqs-metrics.contentanalyticsinc.com/get_cache` with **two** params: `task` and `queue`.

* `task` - task dictionary from **SQS**.

* `queue` - SQS **queue name**.

From `task` generates unique key and gets result for task from cache. 
Also the cache additionally checks the tasks stay time to skip too old tasks.

### To save a cache need send the `POST` request: ###

`http://sqs-metrics.contentanalyticsinc.com/save_cache` with **two** params: `task` and `message`.

* `task` - task dictionary from **SQS**.

* `message` - Key to get result from **Amazon S3** (Compressed by `zlib`).


From `task` generates unique key and saves result for task in cache with current timestamp.

## Other ##

### The creation of unique key ###

To create unique keys for the cache the service gets from tasks keys and values and generates unique key from them.

* `key`-`value`**:**`key`-`value`...

* Order is: `site`, `url`, `urls`, `searchterms_str`, `with_best_seller_ranking`, `branch_name`.

    - Also key-value pairs from **sorted** `cmd_args` dictionary.

* Reductions is: 
    - `searchterms_str` - store as `term` in cache.
    - `with_best_seller_ranking` - store as `bsr` in cache.
    - `branch_name` - store as `branch` in cache.
 
* If any value by key is empty - then it is ignored.

# Code location

* General SQS SC cache code /deploy/cache_layer/
* *sqs-metrics* server code: /deploy/cache_web_interface/
* SC SQS core uses the cache code intensively, so it's worth having a look into /deploy/sqs_ranking_spiders/ as well

# Server environment

Run /home/web_runner/virtualenv/web_runner/bin/uwsgi --master --emperor /etc/uwsgi/vassals/ --die-on-term --daemonize 1

If it doesn't work, try to run this: /home/web_runner/virtualenv/web_runner/bin/uwsgi --ini cache_uwsgi.ini