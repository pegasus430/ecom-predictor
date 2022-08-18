## Code ##

Branch: **google_crawler**

Location: `tmtext/google_crawler`

## Installation ##

`pip install -r requirements.txt`

Set/update `CRAWLERA_APIKEY` in `google_crawler/settings.py`

## Usage for ranks scraping ##


```
#!text

usage: run_keyword_crawler.py [-h] [-d DOMAIN] [-p PROXY] [-o OUTPUT] [-l LOG]
                              keywords

Google crawler helper

positional arguments:
  keywords              File with a list of keywords

optional arguments:
  -h, --help            show this help message and exit
  -d DOMAIN, --domain DOMAIN
                        Domain for urls filtering
  -p PROXY, --proxy PROXY
                        Proxy server. Crawlera if not specified.
                        buyproxies.org - 34.205.229.206:60001, shader.io -
                        34.205.229.206:60000, rotatingproxies.com -
                        34.205.229.206:48359
  -o OUTPUT, --output OUTPUT
                        Output filename
  -l LOG, --log LOG     Log file path

```

keywords - must be CSV file with `keyword` column. Example: `keywords.csv`

```
#!text

keyword
televisions
4k television
tablet
ipad
iphone
walmart televisions
televisions walmart
walmart tablets
tablets walmart
hdtv
diapers
baby diapers
huggies
pampers
walmart diapers
```

**proxy** - proxy server for crawling Google:

* buyproxies.org - 34.205.229.206:60001
* shader.io - 34.205.229.206:60000 (most prefered)
* rotatingproxies.com - 34.205.229.206:48359

Spider is using Crawlera if proxy argument is not specified

**domain** - creates additional file with urls only for this domain

**output** - CSV file with results

Example call: `python run_keyword_crawler.py keywords.csv -d walmart.com`
```
#!text

2017-03-15 18:54:43 INFO:Log file: google_crawler.log
2017-03-15 18:54:43 INFO:Input file: keywords.csv
2017-03-15 18:54:43 INFO:Output file: keywords_ranks.csv
2017-03-15 18:54:43 INFO:Start crawler
2017-03-15 18:54:48 INFO:Filter urls for walmart.com in keywords_ranks_walmart.com.csv
```
Example output: `keywords_ranks_walmart.com.csv`

```
#!text

Keyword,Volume,URL,Position,Last Update
hanes,14800,http://www.hanes.com/,1,04/20/2017
hanes,14800,http://www.hanes.com/shop/hanes/women,2,04/20/2017
hanes,14800,http://www.hanes.com/shop/hanes/men,3,04/20/2017
hanes,14800,http://www.hanes.com/shop/hanes/clearance--1,4,04/20/2017
hanes,14800,http://www.hanes.com/shop/hanes/men/t-shirts/short-sleeve,5,04/20/2017
hanes,14800,http://www.hanes.com/shop/hanes/men/underwear/mens-underwear,6,04/20/2017
...
```


*Hint*: you can rerun crawler with the same parameters

* to continue scraping after stop
* to scrape additional keywords
* to filter results by other domain