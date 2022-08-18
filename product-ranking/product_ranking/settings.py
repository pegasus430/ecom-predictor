# Scrapy settings for product_ranking project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

import os
import sys
from scrapy import log

IS_AWS_INSTANCE = os.path.isdir("/home/spiders/virtual_environment")
if IS_AWS_INSTANCE:
    log.msg('AWS INSTANCE')
    print('AWS INSTANCE')
else:
    log.msg('NOT AN AWS INSTANCE, SETTINGS ADJUSTED')
    print('NOT AN AWS INSTANCE, SETTINGS ADJUSTED')

def _install_pip():
    # TODO: a workaround for SQS - fix post_starter_spiders.py and remove
    # install PIP packages for sure?
    os.system('python /home/spiders/repo/post_starter_spiders.py')
    os.system('python /home/spiders/repo/tmtext/deploy/sqs_ranking_spiders/post_starter_spiders.py')
if IS_AWS_INSTANCE:
    _install_pip()

BOT_NAME = 'product_ranking'

SPIDER_MODULES = ['product_ranking.spiders']
NEWSPIDER_MODULE = 'product_ranking.spiders'

# Commented ones are unused and can be removed
ITEM_PIPELINES = {
    'product_ranking.pipelines.LowerVariantsPropertiesNames': 300,
    'product_ranking.pipelines.RemoveNoneValuesFromVariantsProperties': 300,
    'product_ranking.pipelines.CutFromTitleTagsAndReturnStringOnly': 300,
    'product_ranking.pipelines.SetMarketplaceSellerType': 300,
    'product_ranking.pipelines.AddSearchTermInTitleFields': 300,
    'product_ranking.pipelines.CheckGoogleSourceSiteFieldIsCorrectJson': 400,
    # 'product_ranking.pipelines.WalmartRedirectedItemFieldReplace': 800,
    # 'product_ranking.pipelines.SetRankingField': 900,
    'product_ranking.pipelines.MergeSubItems': 1000,
    'product_ranking.pipelines.BuyerReviewsAverageRating': 300,
    # 'product_ranking.pipelines.CollectStatistics': 1300
    'product_ranking.pipelines.AddCrawledAt': 800
}


RANDOM_UA_PER_PROXY = True

# Delay between requests not to be blocked (seconds).
DOWNLOAD_DELAY = 0.5

# allow max N seconds to download anything
DOWNLOAD_TIMEOUT = 60

# Maximum URL length
URLLENGTH_LIMIT = 5000

# show all duplicates (makes debugging easier)
DUPEFILTER_DEBUG = True

if not 'EXTENSIONS' in globals():
    EXTENSIONS = {}
# EXTENSIONS['product_ranking.extensions.StatsCollector'] = 500

if IS_AWS_INSTANCE:
    EXTENSIONS['product_ranking.extensions.IPCollector'] = 500
    EXTENSIONS['product_ranking.extensions.RequestsCounter'] = 500
    EXTENSIONS['product_ranking.extensions.LogstashExtension'] = 500
    LOGSTASH_ENABLED = True
    WEBSERVICE_ENABLED = False
    TELNETCONSOLE_ENABLED = False

EXTENSIONS['product_ranking.extensions.SignalsExtension'] = 100
# memory limit
EXTENSIONS['scrapy.contrib.memusage.MemoryUsage'] = 500
MEMUSAGE_LIMIT_MB = 2048
MEMUSAGE_ENABLED = True

USE_PROXIES = False

# redefine log foramtter. DropItem exception provided with ERROR level
#LOG_FORMATTER = 'product_ranking.pipelines.PipelineFormatter'

# Value to use for buyer_reviews if no reviews found
ZERO_REVIEWS_VALUE = [0, 0.0, {'1': 0, '2': 0, '3': 0, '4': 0, '5': 0}]

CWD = os.path.dirname(os.path.abspath(__file__))

# RANDOM PROXY SETTINGS
# Retry many times since proxies often fail
RETRY_TIMES = 15
# Retry on most error codes since proxies fail for different reasons
RETRY_HTTP_CODES = [500, 502, 503, 504, 400, 403, 404, 408]

DOWNLOADER_MIDDLEWARES = {
    'scrapy.contrib.downloadermiddleware.retry.RetryMiddleware': 90,
    'scrapy.contrib.downloadermiddleware.httpproxy.HttpProxyMiddleware': 110,
    'scrapy_crawlera.CrawleraMiddleware': 600, # pip install scrapy-crawlera
    'product_ranking.extensions.AerospikeCache': 1
}
if IS_AWS_INSTANCE:
    DOWNLOADER_MIDDLEWARES['product_ranking.custom_middlewares.ProxyFromConfig'] = 100

CRAWLERA_ENABLED = False  # false by default
CRAWLERA_APIKEY = '0dc1db337be04e8fb52091b812070ccf'
CRAWLERA_URL = 'http://content.crawlera.com:8010'

TWOCAPTCHA_APIKEY = "e1c237a87652d7d330c189f71c00ec0b"

SENTRY_DSN = 'https://5beebab970d74a1d89048c873d0f48cd:ee4855c03a1f4abdad945eb288b8f754@sentry.io/222613'

_args_names = [arg.split('=')[0] if '=' in arg else arg for arg in sys.argv]
if 'validate' in _args_names:
    if not 'ITEM_PIPELINES' in globals():
        ITEM_PIPELINES = {}
    ITEM_PIPELINES['product_ranking.validation.ValidatorPipeline'] = 99


HTTPCACHE_DIR = os.path.join(CWD, '..', '_http_s3_cache')  # default

if 'save_raw_pages' in _args_names:
    #DOWNLOADER_MIDDLEWARES['scrapy.contrib.downloadermiddleware.httpcache.HttpCacheMiddleware'] = 50
    #DOWNLOADER_MIDDLEWARES['product_ranking.cache.PersistentCacheMiddleware'] = 50
    HTTPCACHE_ENABLED = True
    HTTPCACHE_POLICY = 'product_ranking.cache.CustomCachePolicy'
    HTTPCACHE_STORAGE = 'product_ranking.cache.S3CacheStorage'
    HTTPCACHE_EXPIRATION_SECS = 0  # forever
    EXTENSIONS['product_ranking.extensions.S3CacheUploader'] = 999

if 'load_raw_pages' in _args_names:
    HTTPCACHE_ENABLED = True
    HTTPCACHE_POLICY = 'product_ranking.cache.CustomCachePolicy'
    HTTPCACHE_STORAGE = 'product_ranking.cache.S3CacheStorage'
    HTTPCACHE_EXPIRATION_SECS = 0  # forever
    EXTENSIONS['product_ranking.extensions.S3CacheDownloader'] = 999

if 'enable_cache' in _args_names:  # for local development purposes only!
    HTTPCACHE_ENABLED = True
    HTTPCACHE_POLICY = 'product_ranking.cache.CustomCachePolicy'
    HTTPCACHE_STORAGE = 'product_ranking.cache.CustomFilesystemCacheStorage'
    HTTPCACHE_EXPIRATION_SECS = 0  # forever
    HTTPCACHE_DIR = os.path.join(CWD, '..', '_http_cache')


try:
    from settings_local import *  # noqa:F401
except ImportError:
    pass

if IS_AWS_INSTANCE:
    from randomproxy import Mode
    DOWNLOADER_MIDDLEWARES['product_ranking.randomproxy.RandomProxy'] = 100
    PROXY_MODE = Mode.RANDOMIZE_PROXY_ONCE
    PROXY_LIST = '/tmp/http_proxies.txt'
# shared CH and SC code
sys.path.append(os.path.join(CWD, '..', '..'))
sys.path.append(os.path.join(CWD, '..', '..', 'spiders_shared_code'))
sys.path.append(os.path.join(CWD, '..', '..', 'product_ranking'))
