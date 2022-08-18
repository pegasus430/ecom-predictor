[TOC]

[THIS IS A DRAFT BEING ACTIVELY UPDATED]

# Overview
sqs-tools is a collection of useful SQS-related tools. S3 search, test jobs creation, deploy, status of autoscale groups (how many instances are running there)

# Queues

* `sqs_ranking_spiders_tasks_urgent` - urgent production tasks (will be processed asap)
*  `sqs_ranking_spiders_tasks` - incoming queue for tasks (production one)
*  `sqs_ranking_spiders_tasks_dev` - incoming queue for tasks (development one)
*  `sqs_ranking_spiders_tasks_tests` - incoming queue for tasks (test one)
* server_name + `sqs_ranking_spiders_output` - output data from instance(keys for spider logs and data at S3)
* server_name + `sqs_ranking_spiders_progress` - progress reports

# Input data

Task messages randomly retrieved from one of three available SQS mentioned above.

The incoming scraping message should be a JSON message of the following structure:

* task_id - the ID of the task from the UI server, integer

* searchterms_str - string to search (for bulk searches)

* url - product URL (for 'individual pages' searches)

* site - site to scrape, like `amazon` or `walmart` or `target` and so on

* server_name - the server name string (UID?) sent

* cmd_args - extra spiders arguments:
    * `quantity`, `user_agent` or `zip_code`, `ignore_variant_data` or any other spider param.
    * `scrape_questions` - collect q/a data, by default is False. True or False
    * `make_screenshot` - will make a screenshot of the given product URL (in case of product URL job or shelf page) or the SERP page (in case you passed a search term)

* branch_name - name of the branch that you want to test. This argument can be omitted or set to None - in this case 'master' branch will be used by default.

* with_best_seller_ranking - provide additional calculation of best sellers. True or False

Example:

```
{  
    "searchterms_str":"water",
    "server_name":"test_server_name",
    "cmd_args":{  
        "quantity":20
    },
    "site":"walmart",
    "task_id":4444,
    "branch_name": "unified_price_no_validation",  # optional
    "with_best_seller_ranking": True  # optional
}
```

# Supported input data formats

1. `{..., 'url': 'http://www.walmart.com/ip/31262048', ... }` - product urls (scrapes one product)

2. `{..., 'searchterms_str': 'batteries', ...}` - bulk searchterms mode (scrapes multiple products at once)

Most of the parameters are passed via `cmd_args` argument, except for:

* `with_best_seller_ranking` - walmart's "bestseller ranking" mode

* `branch_name` - a spiders' branch to use (`sc_production` used as the default one if no branch is specified)

* `server_name`, `site`, `task_id` - not used by the spiders themselves but in the SQS spiders core

For other possible options see https://bitbucket.org/dfeinleib/tmtext/src/6637317668bcd5c4198701bec95af2e310dc352c/deploy/sqs_ranking_spiders/test_sqs.py?at=master&fileviewer=file-view-default#test_sqs.py-27  (Python's `dict()` is like the PHP's `array()`)

# Output data

The output spider data files (non-split JSON lines) and the logs are uploaded to an Amazon S3 bucket called `spyder-bucket`. Also there will be stored logs from remote_instance_starter daemon. Keys at S3 will look like `2015/06/05/05-06-2015____wutu1197s1txa6d4b9uj9z6wj36q____test-server--186442____iphone____amazon.csv.zip` consist of `datestamp____random_hash____server_name____task_id____searchterm____site_name`. Pls note, that if in searchterm slash or backslash are present - this symbols will be stripped.

After uploading daemon will provide message to output SQS with following JSON format: 

```
msg = {
            '_msg_id': metadata.get('task_id', metadata.get('task', None)) [just the TASK ID given by the UI server],
            'type': 'ranking_spiders',
            's3_key_data': data_key.key,
            's3_key_logs': logs_key.key,
            'bucket_name': data_key.bucket.name,
            'utc_datetime': datetime.datetime.utcnow(),
            's3_key_instance_starter_logs': s3_key_instance_starter_logs,
            'csv_data_key': csv_data_key.key,
        }
```

Example output:
```
{
    "_msg_id": 4444, 
    "type": "ranking_spiders", 
    "s3_key_data": "/2015/04/03/03-04-2015____nbvqq1i7qn5d6cr659l6f11jkzar____4444____single-product-url-request____amazon.jl.zip", 
    "s3_key_logs": "/2015/04/03/03-04-2015____nbvqq1i7qn5d6cr659l6f11jkzar____4444____single-product-url-request____amazon.log.zip", 
    "bucket_name": "spyder-bucket2", 
    "utc_datetime": "2015-04-03T08:01:31.528410", 
    "s3_key_instance_starter_logs": "/2015/04/03/03-04-2015____nbvqq1i7qn5d6cr659l6f11jkzar____remote_instance_starter2.log",
    "csv_data_key": "/2015/04/03/03-04-2015____nbvqq1i7qn5d6cr659l6f11jkzar____4444____single-product-url-request____amazon.csv.zip"
}
```


# Progress report

To monitor the running spider, you can pull the progress messages which have the following structure:

```
    _msg = {
        '_msg_id': metadata.get('task_id', metadata.get('task', None)),
        'utc_datetime': datetime.datetime.utcnow(),
        'progress': 0
    }
```

The field `progress` from above can have the following values:

* `0` - the spider has actually started; if you don't see this message then it means the spider has not started yet OR it crashed and did not even write any logs

* `0-...` (just an integer) - the number of products scrapped by the spider (so if the spider has scraped 100 products by now, that value will be 100)

* `finished` - a string telling that the spider has successfully finished its task and all the products have been collected

* `failed` - a string telling that the spider wasn't started at all (if incorrect spider name was provided for example)


# SQS servers - job steps

The default user who 'executes' the code is `spiders`. His password is `spiders` (quite simple, huh?).

Everything is split up into different files, so almost anything can be easily updated. Only `remote_instance_starter.py` stored at the AMI instance. All other scripts will be used from cloned repo.

1) instance boots up   

2) `remote_instance_starter.py` script is executed by cron - it pulls the GIT repo with all the other files. But there are two cases when the script will not be executed:   
>
>a) One `remote_instance_starter.py` was already running on server instance. It checked by existing of  `remote_instance_starter.py.maker` file.   
>
>b) There is a stop flag in the our S3 bucket 'spyder-bucket'. It stored with key 'scrapy_daemon_stop_flag' as string 'true'. This flag is used so that we can build clear AMI instance without any tasks already executed. To allow our instances perform some tasks you need change this flag to 'false' or just remove it. 

Source location: tmtext/deploy/sqs_ranking_spiders/scrapy_daemon.py  


3) `post_starter_root.py` is executed by ROOT cron *after* the previous step is complete   

4) `post_starter_spiders.py` is executed *after* the previous step is complete   

5) `scrapy_daemon.py` is executed *after* all the steps above are successfully done. Script starts from the branch `sc_production`, so all changes, which are made in another branch, would be not recognized and not used by the system. 

6) `upload_logs_to_s3.py` is executed by cron after instance starts to boot up. If log file is not empty and last updated version wasn't uploaded yet script will upload it to S3.   

7) `task_id_generator.py` just support script that generate random hash and datestamp data same for `scrapy_daemon.py` and `upload_logs_to_s3.py`.   

# Testing scrapy_daemon
There are now two ways are available:

1) Run `python scrapy_daemon.py test` and manually check output. SQS will be faked.

2) Use unit-test. `python test_scrapy_daemon.py`. In this case real SQS and S3 services will be used. Test output can be checked at folder '/tmp/spiders_test_output'. This test should be run prior scrapy_daemon was started, cause test rewrite hash and datestamp data. Important: test will fail if amazon spider not work properly.


# Scaling autoscale group

The scaling is controlled by autoscale policies.
Each autoscale group has different scaling polices based on their needs.

# Command-line tests

There is a testing script that tests the whole chain: creates a message in the "incoming" queue, waits for the instance to spin up and finish the crawling task, validates the progress messages and the output data from the S3 bucket. It will test three possible cases:

* Task with 'searchterms_str'
* Task with 'product_url'
* Task with 'searchterms_str' and additional argument 'best_sellers_ranking'

```
Example usage:
$ python test_sqs_flow.py
```

as the result, it should print "EVERYTHING IS OK" message.

The execution may take up to 30*3 mins, sit tight. 

# GUI tests

Moved to a new dedicated page: https://bitbucket.org/dfeinleib/tmtext/wiki/SQS%20GUI%20tests

# Metrics
Three SQS metrics are available at [sqs-metrics.contentanalyticsinc.com/cache-stats](sqs-metrics.contentanalyticsinc.com/cache-stats) :
For the credential info, please reference https://bitbucket.org/dfeinleib/tmtext/wiki/General%20SC%20credentials

* Instaces running at this moment at group
* Total tasks sent to SQS during the day
* Total SQS instances spinned up during the day
  
You may directly request quantity of instances running at this moment. For this you may use url: [sqs-metrics.contentanalyticsinc.com/get_sqs_instances_quantity](sqs-metrics.contentanalyticsinc.com/get_sqs_instances_quantity).  
For example `curl --user admin:Content12345  http://52.4.67.56/get_sqs_instances_quantity`. Note: this link  secured with HTTP authorization.

Also these metrics will be sent by email every day to [support@contentanalyticsinc.com](support@contentanalyticsinc.com)

# Additional tool for debugging

For debuging purposes additional web interface was created. It located at [sqs-metrics.contentanalyticsinc.com/failed_logs](sqs-metrics.contentanalyticsinc.com/failed_logs) and secured with HTTP authorization (*admin / Content12345*). This page will display all logs file without output .zip files (from failed spiders).    

Also you may filter links by task id - this will display all corresponding bucket keys. Or try to found corresponding remote_instance_starter_log by task id contained inside it.
WARNING: This page will be very slow because it fetch whole S3 bucket for last three days.

# Notes
Sometimes, really very seldom, two or more remote_instance_starter scripts may run. So maybe quantity of running instances should be checked not only by flag but also by some `ps` means.

# Debugging

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

If you need to download the instance starter log follow this steps:
- Open http://52.1.192.8/search-files/
- Search the instance id, Example: "yubtv32luam6zy22lpa8u6zgigmc" 
- Click on the file which name ends with remote_instance_starter2.log 
```

## Example

Imagine you want to check SQS logs for this job:![Выделение_325.png](https://bitbucket.org/repo/e5zMdB/images/1312546248-%D0%92%D1%8B%D0%B4%D0%B5%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5_325.png)

You may check job's logs by simply clicking the link "Log" (see the right column of the row).

If it's not available or you need the instance log (i.e. log of scrapy_daemon.py file), then you have to do this:

* get the SQS ID (aka task ID) of the job (it's 164036 in the example from above)

* go to http://sqs-tools.contentanalyticsinc.com/search-files/ and paste the SQS ID there and Search button. You'll see this: ![Выделение_326.png](https://bitbucket.org/repo/e5zMdB/images/3037515116-%D0%92%D1%8B%D0%B4%D0%B5%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5_326.png)

* the job logs we need are markered there. Why are the jobs we need? Because the ID is 164036, and the server name is "test-server", and the date is the date when we ran that task.

* if you want to get the instance log (i.e. scrapy_daemon.py log), select the instance ID (it's ____tt264u1htbz3v2kolxzze5m03606____ in our case) and search for it. You'll see the list of all the jobs executed on this instance, as well as the scrapy_daemon log.

* now, the file ending with "remote_instance_starter2.log" is the one you need: ![Выделение_327.png](https://bitbucket.org/repo/e5zMdB/images/2814464014-%D0%92%D1%8B%D0%B4%D0%B5%D0%BB%D0%B5%D0%BD%D0%B8%D0%B5_327.png)


# Creating new AMI image for autoscaling group

Few steps should be done in order to create new ami image.

* Set contents of the S3 key `scrapy_daemon_stop_flag`, availabe at the bucket `spyder-bucket` to `true`. When this flag is set, sqs system is paused and new raised instances will not execute jobs untill this flag will be removed
* Connect to new server, from which you are going to create new AMI image.
* Set up new server in the way that you need. Note, that you don't have to set up everything from the scratch, everything that is required to run the project, already installed here.
* After setup is done, you need to clear all redundant files from the sever. To do that, run `sudo python ~/clean_instances.py` from ubuntu user. If the file is absent at the user home directory, same file can be found in the project directory `deploy/sqs_ranking_spiders/clean_instance.py`. Just run it with sudo.
* Server is done and can be shut down. Extract AMI image from it and set it to be used on autoscale groups.
* After all steps are done, remove `scrapy_daemon_stop_flag` key in `spyder-bucket`. SQS process will resume and new servers are all ready to run jobs

# Other

**DO NOT READ ANYTHING BELOW, THIS IS OLD, NON-ACTUAL AND OUTDATED***

Workflow:

1) The UI side sends a new message into the SQS queue [**QUEUE NAME?**]

2) Something somehow starts a new EC2 instance [**WHAT AND HOW?**]

3) Then a deployment script [**CREATE IT**] is executed by something [**by what?**] and then it deploys the code into the previously created instance

4) Then, when everything is ready, the instance pulls the message from the queue. [**How does the instance knows which message to pull? or it just pulls a random message?**]

5) Then the script that pulled the data [**create this script**] executes `scrapy crawl` command. We don't want to use Scrapyd here, it's just terrible (path issues, hard to debug, keeps the jobs in memory, bloody hell).

6) Then the script takes the results from scrapy and pushes them back to the queue.

7) Done?