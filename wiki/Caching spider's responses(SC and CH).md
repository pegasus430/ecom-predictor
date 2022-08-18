[This is a draft page for [Bug 1143](https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=1143). It will be updated in the future.]

# Purpose

The purpose of this feature to store responses received form SC spiders or CH spiders at S3 storage to reuse these objects later.

# Usage

To use cache layer with SC spiders you need add an extra spider arg `-a save_raw_pages=True`.  
To get results manually back you should:  

*  Connect to redis database
*  Based on request url get key from S3 bucket.
*  Download/read required data from S3 bucket.

# Useful tools

* `python product_ranking/extensions.py cache_map` - will list all available cached searchterms and product URLs

* `http://52.1.192.8/s3-cache/` - to search for a cached response, and view it online


# Main logic

For every response received by scrapy based on request will be created unique fingerprint. Next S3 path will be created with pattern `spider_name/fingerprint/compressed_response_ibject`. To provide easy access we store this S3 path(as value) next to response.url(as key) in redis HASH named `urls_and_s3_pathes`. After middleware will compress response body and uploat it to S3 bucket.


# Storage

Responses objects will be stored at S3 bucket `spiders-cache`. All objects older than 14 days will be automatically removed. This logic will be performed by Amazon LifeCycle rules.  
Storage have such architecture: `spider_name/response.url.fingerprint/compressed_response_object`.  
To check quantity of items(keys) at S3 bucket you may follow link [http://sqs-metrics.contentanalyticsinc.com/get_s3_cache_items_quantity](http://sqs-metrics.contentanalyticsinc.com/get_s3_cache_items_quantity). It will return data in JSON format so you may use this link as API.

# Files location

Whole service provided by middleware `MyHttpCacheMiddleware` located at `tmtext/product-ranking/product_ranking/cache_middlewares.py`. For CH spiders code located at `tmtext/special_crawler/cached_opener.py`. At this moment code located at branch `cache_sqs_ranking_spiders`.

# Necessary files and commands

* python product_ranking/cache_models.py list_to_pickle - to dump the current DB cache keys

* (being in product-ranking/sqs_tests_gui): ./manage.py download_list_of_s3_cache_files - to dump the list of all cache files from S32

# Admin Interface Requirements

Rough implementation of UI interface located at [http://sqs-metrics.contentanalyticsinc.com/s3_cache_metrics](http://sqs-metrics.contentanalyticsinc.com/s3_cache_metrics) (*admin / Content12345*)

* UI showing total number of pages in cache, total size of cache; number of pages by type; size of pages by type (type = search results page vs product item page)
* UI for configuring max cache age
* UI to turn cache on/off

