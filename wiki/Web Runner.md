# Table of contents
[TOC]

# Overview #

Web Runner is a REST service that allows to run Scrapy spiders through Scrapyd and to run commands over the resulting data.

The way it works is that spiders and commands are configured in the Web Runner and jobs can be started, polled (this is a polling interface) and eventually the resulting data retrieved.

The configuration goes in the main configuration file, for example, `production.ini`.

# Architecture #

Web Runner runs as a service under a web server (Apache or similar).

Behind it there is an Scrapyd instance which provides control over crawl jobs.

# Service Health #

Resource `/status/` provides the following data:

```
{
    "queues": {
        "product_ranking": {
            "running": 0,
            "finished": 500,
            "pending": 0
        }
    },
    "scrapyd_projects": [
        "product_ranking"
    ],
    "scrapyd_alive": true,
    "spiders": {
        "product_ranking": [
            "amazon_products",
            "amazonfresh_products",
            "asda_products",
[...]
            "walmart_products"
        ]
    },
    "webRunner": true,
    "scrapyd_operational": true,
    "summarized_queue": {
        "running": 0,
        "finished": 500,
        "pending": 0
    }
}
```

It is possible to request for part of the output. The way to achieve this is to add a parameter with the format: return=<returned_key>:<status.structure.dereferenced.by.dots>. Examples:

 - Get the summary queue:

```
$ curl 'http://127.0.0.1:6543/status/?return=summarized_queues:summarized_queue'

{"summarized_queues": {"running": 23, "finished": 500, "pending": 339}}
```

 - Get only the running queue size from sumarized_queue:

```
$ curl 'http://127.0.0.1:6543/status/?return=running_summary:summarized_queue.running'

{"running_summary": 27}
```

 - It is possible to return several items on the same query. The next one returns the running and pending queue size from `sumarized_queue` and the deployed scrapyd projects:

```
$ curl 'http://127.0.0.1:6543/status/?return=running_summary:summarized_queue.runningreturn=pending_summary:summarized_queue.pending&return=projects:scrapyd_projects'

{"pending_summary": 307, "projects": ["product_ranking"], "running_summary": 27}
```

 - It is also possible to return the output in plain text. This can be useful for Zabbix monitoring.

```
$ curl -H "Accept: text/plain" 'http://127.0.0.1:6543/status/?return=aaa:queues.product_ranking.running'

27
```

Be carefull the plain text option has several constrains, like not showing the given name to the metric (in the case above, `aaa`).



# Spiders #

## REST Service Interface ##

The API is as follows:

> Resource: /{resource}/  
> Method: POST  
> Code:
>
> -   502: Error communicating to external service (Scrapyd, etc).
> -   302: There will be several redirects, each will have an informational message that can be ignored.
> -   202: The job is running or waiting to run. The status will be in the response body. The client should continue polling.
> -   200: The job finished and the result is returned in this message. The content type of the result is JSONLines.
>
> Description: Starts a new spider job.

The `resource` is indicated in the configuration of Web Runner.

The parameters in the query string are passed on to the spider.

## Request Priorities ##

The priority of a crawl can be set by sending the `priority` parameter in the query string.

A priority of 0 is the lowest (and default) and a higher number is a higher priority.

For example:

```
$ curl http://localhost:6543/ranking_data/ -d site=bol -d searchterms_str=hair -d quantity=10 -d priority=100
```


## Configuration ##

The configuration goes into an INI file. This format does not support lists or nesting so this was emulated.

First, an example:

```
# Space separated list of spider configuration names.
spider._names = product_ranking_cfg
spider._scrapyd.base_url = http://localhost:6800/
spider._scrapyd.items_path = /location_of_scrapyd/items/{project_name}/{spider_name}/

spider.product_ranking_cfg.resource = /ranking_data
spider.product_ranking_cfg.spider_name = {site}_products
spider.product_ranking_cfg.project_name = product_ranking
```

`spider._scrapyd.base_url` has the URL to the Scrapyd service.

`spider._scrapyd.items_path` has the location of the directory tree for spider results.

`spider._names` has a space separated list of spider names.

For each name three other entries must exist:

*    `spider.{name}.resource`: The name of the resource that will represent this spider.
*    `spider.{name}.spider_name`: The name of the Scrapy spider.
*    `spider.{name}.project_name`: The project name under which the spider exists in the Scrapyd service.

There can be any number of configurations.


# Commands #

Commands are configured as resources in the Web Runner. They can receive any parameter that is passed in the query string.

Additionally, commands can be configured to depend on the output of spiders.  
When configured this way, the spiders will be run first and the command will be executed with the output of all spiders.

The standard output of the command will be returned as the final response.

## REST Service Interface ##

The API is as follows:

> Resource: /{resource}/  
> Method: POST  
> Code:
>
> -   502: Error communicating to external service (Scrapyd, command error, etc).
> -   302: There will be several redirects, each will have an informational message that can be ignored.
> -   202: The job is running or waiting to run. The status will be in the response body. The client should continue polling.
> -   200: The job finished and the result is returned in this message. The content type of the result depends on the command.
>
> Description: Starts a new command job.


## Configuration ##

First, an example:

```
command._names = summary other_command ...

command.summary.resource = /summary/
command.summary.cmd = ../product-ranking/summarize-search.py --filter '{filter}' - '{spider 0}'
command.summary.content_type = text/csv
command.summary.crawl.0.spider_config_name = product_ranking_cfg
command.summary.crawl.0.spider_params = quantity=20 something_else=something
```

The configuration "summary" configures `summarize-search.py` to be run with parameter `--filter` whose value `{filter}` comes from the request and argument `{spider 0}` which is the output of the first "crawl".

"spider_config_name" is the name of a spider configuration as described in the first half of this page.

"spider_params" are parameters for the spider configuration.

## Sample Interaction ##

On this session `curl` is used to operate over the "cat1" resource by POSTing to it in order to execute the `cat` command on the output of a spider (`product-ranking`).

The `cat1` resource takes no parameters but the spiders accept all parameters they normally take plus the `site` parameter which specifies the site to be crawled.

First the POST to get it all started:
```
$ curl --verbose http://localhost:6543/cat1/ -d 'site=walmart;searchterms_str=laundry detergent;quantity=100;group_name=Laundry Detergent'
* Hostname was NOT found in DNS cache
*   Trying 127.0.0.1...
* Connected to localhost (127.0.0.1) port 6543 (#0)
> POST /cat1/ HTTP/1.1
> User-Agent: curl/7.35.0
> Host: localhost:6543
> Accept: */*
> Content-Length: 59
> Content-Type: application/x-www-form-urlencoded
> 
* upload completely sent off: 59 out of 59 bytes
< HTTP/1.1 302 Found
< Content-Length: 1005
< Content-Type: text/html; charset=UTF-8
< Date: Fri, 20 Jun 2014 01:20:08 GMT
< Location: http://localhost:6543/command/cat1/pending/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&searchterms_str=laundry+detergent&quantity=100
* Server waitress is not blacklisted
< Server: waitress
< 
<html>
 <head>
  <title>302 Found</title>
 </head>
 <body>
  <h1>302 Found</h1>
  The resource was found at /command/cat1/pending/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&amp;searchterms_str=laundry+detergent&amp;quantity=100; you should be redirected automatically.
Command 'cat1' started with 1 crawls.

 <script type="text/javascript">
    var fileref=document.createElement("link")
    fileref.setAttribute("rel", "stylesheet")
    fileref.setAttribute("type", "text/css")
    fileref.setAttribute("href", "http://localhost:6543/_debug_toolbar/static/css/toolbar.css")
    document.getElementsByTagName("head")[0].appendChild(fileref)
</script>

<div id="pDebug">
    <div style="display: block; " id="pDebugToolbarHandle">
        <a title="Show Toolbar" id="pShowToolBarButton"
           href="http://localhost:6543/_debug_toolbar/313430363534393238353035353532" target="pDebugToolbar">&laquo; FIXME: Debug Toolbar</a>
    </div>
</div>
</body>
* Connection #0 to host localhost left intact
```

You may also try this one to start crawling the website:

```
curl --verbose http://localhost:6543/ranking_data/  -d 'site=walmart;searchterms_str=laundry detergent;quantity=100;group_name=Laundry Detergent'
```

(For walmart and pgestore, change `/ranking_data/` to `/ranking_data_with_best_sellers/`)

What happened is that the server responded that everything is OK and that we should proceed to another URL (`302 Found`).

The next URL is, of course, in the `Location` header. It is also mentioned in the body of the request with a human readable message describing what's going on ("Command 'cat1' started with 1 crawls.").

The `/command/cat1/pending/...` resource is the waiting area until the crawls finish execution.

Let's follow on to the next URL:
```
$curl -v 'http://localhost:6543/command/cat1/pending/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&searchterms_str=laundry+detergent&quantity=100'
* Hostname was NOT found in DNS cache
*   Trying 127.0.0.1...
* Connected to localhost (127.0.0.1) port 6543 (#1)
> GET /command/cat1/pending/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&searchterms_str=laundry+detergent&quantity=100 HTTP/1.1
> User-Agent: curl/7.35.0
> Host: localhost:6543
> Accept: */*
> 
< HTTP/1.1 202 Accepted
< Content-Length: 819
< Content-Type: text/html; charset=UTF-8
< Date: Fri, 20 Jun 2014 01:20:22 GMT
* Server waitress is not blacklisted
< Server: waitress
< 
<html>
 <head>
  <title>202 Accepted</title>
 </head>
 <body>
  <h1>202 Accepted</h1>
  The request is accepted for processing.<br/><br/>
Crawlers still running: 1


 <script type="text/javascript">
    var fileref=document.createElement("link")
    fileref.setAttribute("rel", "stylesheet")
    fileref.setAttribute("type", "text/css")
    fileref.setAttribute("href", "http://localhost:6543/_debug_toolbar/static/css/toolbar.css")
    document.getElementsByTagName("head")[0].appendChild(fileref)
</script>

<div id="pDebug">
    <div style="display: block; " id="pDebugToolbarHandle">
        <a title="Show Toolbar" id="pShowToolBarButton"
           href="http://localhost:6543/_debug_toolbar/313430363534393238363531393230" target="pDebugToolbar">&laquo; FIXME: Debug Toolbar</a>
    </div>
</div>
</body>
* Connection #1 to host localhost left intact
```

This time we get an HTTP status `202 Accepted`. This means that the request is correct but we should retry after a small delay. The reason for this is that there are still crawlers running, as is mentioned in the body.

After a moment we retry and get:
```
$ curl -v 'http://localhost:6543/command/cat1/pending/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&searchterms_str=laundry+detergent&quantity=100'
* Hostname was NOT found in DNS cache
*   Trying 127.0.0.1...
* Connected to localhost (127.0.0.1) port 6543 (#0)
> GET /command/cat1/pending/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&searchterms_str=laundry+detergent&quantity=100 HTTP/1.1
> User-Agent: curl/7.35.0
> Host: localhost:6543
> Accept: */*
> 
< HTTP/1.1 302 Found
< Content-Length: 985
< Content-Type: text/html; charset=UTF-8
< Date: Fri, 20 Jun 2014 01:24:33 GMT
< Location: http://localhost:6543/command/cat1/result/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&searchterms_str=laundry+detergent&quantity=100
* Server waitress is not blacklisted
< Server: waitress
< 
<html>
 <head>
  <title>302 Found</title>
 </head>
 <body>
  <h1>302 Found</h1>
  The resource was found at /command/cat1/result/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&amp;searchterms_str=laundry+detergent&amp;quantity=100; you should be redirected automatically.
Crawlers finished.

 <script type="text/javascript">
    var fileref=document.createElement("link")
    fileref.setAttribute("rel", "stylesheet")
    fileref.setAttribute("type", "text/css")
    fileref.setAttribute("href", "http://localhost:6543/_debug_toolbar/static/css/toolbar.css")
    document.getElementsByTagName("head")[0].appendChild(fileref)
</script>

<div id="pDebug">
    <div style="display: block; " id="pDebugToolbarHandle">
        <a title="Show Toolbar" id="pShowToolBarButton"
           href="http://localhost:6543/_debug_toolbar/313430363534393238353838363838" target="pDebugToolbar">&laquo; FIXME: Debug Toolbar</a>
    </div>
</div>
</body>
* Connection #0 to host localhost left intact
```

We are redirected again (`302 Found`)! This time to the promising resource `/command/cat1/result/...`.

```
$ curl -v 'http://localhost:6543/command/cat1/result/eNprYIotZIhQYGBgMDAxsUg1MzRKszC0NDRMNbZMM7IwMjIwMEg0SLI0NjQuZEzUAwDrwgpa/?site=walmart&searchterms_str=laundry+detergent&quantity=100'
[...]
```

This will reply `200 OK` with the output of the command, which is exactly the output of the spider. It was not copied because it's too much.

This is a simple example of how to use the server, you'll never use this resource (`cat1`) in practice because it produces the same output as a spider, you'd call the spider resource (`/ranking_data/`) directly instead.

# Command and Spider Status #

It is possible to query the status of a Web Runner command or spider, using the `history` service. The URL for that are:

*    For commands: http://{server}:6543/command/{command_name}/`history`/{jobid}
*    For spiders: http://{server}:6543/`history`/project/{project name}/spider/{spider name}/job/{jobid}/

Both queries returns a similar output. It a a JSON dictionar with 2 keys:

*    "status": contains 4 values with the jobid status: running, pending, finished, unavailable
*    "history": it contains a list of list events related to the request. Each event is a 2 atom list with:
     *    date: the event date
     *    Description: a description of the event 

Example:

```
curl -v 'http://localhost:6543/history/project/product_ranking/spider/walmart_products/job/2246bad271ad11e4a0cd120f727ce37e/'

{"status": "finished", "history": [["2014-11-21 18:35:14.639724", "Request arrived from 127.0.0.1."], ["2014-11-21 18:35:15.577298", "Spider walmart_products started. \nid=2246bad271ad11e4a0cd120f727ce37e"], ["2014-11-21 18:35:28.749534", "Requesting status from 127.0.0.1."], ["2014-11-21 18:36:22.546954", "Spider walmart_products finished. Took 0:01:06."], ["2014-11-21 18:36:22.546954", "Request finished. Took 0:01:07 since created."], ["2014-11-21 18:36:29.950483", "Requesting status from 127.0.0.1."], ["2014-11-21 18:36:46.451749", "Requesting status from 127.0.0.1."], ["2014-11-21 18:37:28.114421", "Requesting results from 127.0.0.1."]]}
```

# Scraping single product pages #

A new extra feature. Some spiders (currently, amazon.com and walmart.com) support sraping and returning results for a given product page, like http://www.walmart.com/ip/BLU-Studio-5.5-S-D630u-GSM-Dual-SIM-Android-Cell-Phone-Unlocked-White/36125974. Example of call:

```
curl --verbose http://localhost:6543/ranking_data/  -d 'site=amazon;product_url=http%3A%2F%2Fwww.amazon.com%2FGT-T9500-Android-Smartphone-Screen-SP6820%2Fdp%2FB00FBMU3UY%2Fref%3Dsr_1_1%3Fie%3DUTF8%26qid%3D1420882674%26sr%3D8-1%26keywords%3Dandroid' 
```

The url may or may not be encoded. The difference between the normal mode (search and then scrape each product) and this mode (single page) is that we pass `product_url` arg instead of `searchterms_str`.

The output file contains an extra field - `is_single_result` - which is True in this mode (single product page).

The output file contains only one JSON object, instead of the list of JSONs.

This all works exactly the same way as for searchterms crawling. An UI server sends a request, and then (after some time) the UI server comes back and polls the data.

The job data and status can be retrieved just as normally (http://SERVER_ADDRESS:6543/crawl/project/product_ranking/spider/SITE_products/job/JOB_ID/)


# Extra params #

## Mobile/Desktop user agent ##

`user_agent` : one of the following:

* desktop - normal browser, default

* iphone_ipad - iphone\ipad

* android - android phone or tablet

Example call: 

```
$ curl http://localhost:6543/ranking_data/ -d site=bol -d searchterms_str=hair -d user_agent=iphone_ipad
```


# Extra fields #

Some spiders (Walmart currently) support `sponsored_links`. Structure:

```
"sponsored_links": [
  {"ad_title": "Title blabla - bold text",
   "ad_text": "Text blabla",
   "visible_url": "http://blabla (the URL you see as text)",
   "actual_url": "http://ololo (the actual URL after redirect)"},
  {"ad_title": "Title blabla",
   "ad_text": "Text blabla",
   "visible_url": "http://blabla",
   "actual_url": "http://ololo"}
]
```

For more information, please read http://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=182#c6

# Priority tasks #

Requests from some servers may be executed with higher priority. When pyramid received request from such server it will increment it's priority by 500.
For this you need just follow at our web interface to `simple_cli/priority_servers_list_handling` and provide at form list of required IPs separated by `|` pipe symbol. Really you may use not IP, but any other identifier provided at request header 'HTTP_X_FORWARDED_FOR'. Or you may use not web interface but just manually edit file located on server `/tmp/priority_servers` with the same rules.

# Versions #

On October 2014 the following versions are being running on production:

*    Scrapy 0.24.4 
*    scrapyd 1.0.1

The version is managed by pip. So it may change according when the server is deployed.

# Deployments #

There are the following deploys:

*    [[WebRunnerInstanceOne]]
*    [[WebRunnerInstanceTwo]]

# Deploy Procedure #
[[Web Runner Deploy Procedure]]