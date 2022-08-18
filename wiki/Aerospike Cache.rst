Aerospike Cache
===============

Settings
========

Settings are stored in a JSON file located on S3 (`s3://settings.contentanalyticsinc.com/by_domain.json`).
It is composed of a list of lists of two values each. Each two value list is composed of a selector first and settings second.

The selector is a regex that should match the domain. When more than one selector matches, settings are merged together. Settings are squashed by priority (the order they appear in the list).

Here are some `examples <https://bitbucket.org/dfeinleib/tmtext/src/d80ec89d50830aacd64f81cacf2188d9204770d0/test/test_spiders_shared_code/test_utils.py?at=master&fileviewer=file-view-default#test_utils.py-9>`_.

Here is a format example:

.. sourcecode:: JSON

    [
      ["(www\\.)?example\\.com", {"cache": {"table": "example", "max-age": 86400}}],
      [
        ".+", {
          "cache": {
            "host": "ca-aerospike.aerospike.services.contentanalyticsinc.com",
            "max-age": 3600,
            "namespace": "cache",
            "port": 3000
          }
        }
      ]
    ]

List of available settings (they are all grouped inside a `cache` key):

* **host:** this is the Aerospike host.
* **port:** this is the Aerospike port.
* **namespace:** this is the namespace that should be used on Aerospike.
* **table:** this is the name of the bucket we should write to on Aerospike.
* **max-age/cache_ttl:** this is the maximum age a record can have to be valid, does not affect Aerospike.

To enable cache you need to fill all the settings, and max-age has to be > 0. max-age 0 disables the cache.

SQS Message
===========

Currently we are only allowing overriding of "max-age"/"cache_ttl" from the SQS message.

Stats
=====

These are available on Kibana. I created a `dashboard <https://kibana.contentanalyticsinc.com:443/goto/5ce76b08db27775eedef4da61b4712a9>`_ for commodity of use.

CH
==

There is no structure to store stats on CH besides the one that uploads to Logstash, so we are using it.

* **cache.hit:** count of cache hits.
* **cache.hit_bytes:** total bytes downloaded.
* **cache.hit_time:** total time it took to find and download.
* **cache.update:** count of cache updates.
* **cache.update_bytes:** total bytes uploaded.
* **cache.update_time:** total time it took to upload.
* **cache.miss:** count of cache misses.
* **cache.miss_time:** total time it took to lookup and miss.
* **cache.time:** total time used on missing, downloading and uploading.

SC
==

Scrapy has it `StatsCollector` structure, so I'm using it, and then uploading it to Logstash.

* **scrapy_stats.aerospikecache/hit/count:** count of cache hits.
* **scrapy_stats.aerospikecache/hit/bytes:** total bytes downloaded.
* **scrapy_stats.aerospikecache/hit/time:** total time it took to find and download.
* **scrapy_stats.aerospikecache/update/count:** count of cache updates.
* **scrapy_stats.aerospikecache/update/bytes:** total bytes uploaded.
* **scrapy_stats.aerospikecache/update/time:** total time it took to upload.
* **scrapy_stats.aerospikecache/miss/count:** count of cache misses.
* **scrapy_stats.aerospikecache/miss/time:** total time it took to lookup and miss.