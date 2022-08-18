# Scrapy settings for search project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/topics/settings.html
#

from scrapy import log

BOT_NAME = 'search'

SPIDER_MODULES = ['search.spiders']
NEWSPIDER_MODULE = 'search.spiders'
ITEM_PIPELINES = ['search.pipelines.URLsPipeline']
#LOG_STDOUT = True
# LOG_ENABLED = False
#LOG_FILE = "search_log.out"
# LOG_LEVEL=log.WARNING
DUPEFILTER_CLASS = 'scrapy.dupefilter.BaseDupeFilter'

HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'
# HTTPCACHE_POLICY = 'scrapy.extensions.httpcache.RFC2616Policy'

DOWNLOAD_DELAY = 0.5

DOWNLOAD_HANDLERS = {'s3': None,}

import os
homedir = os.getenv("HOME")
HTTPCACHE_DIR = homedir + '/.scrapy_cache'

# don't cache redirects because of amazon spider for which captchas pages are redirects and cause infinite loops
#TODO: set this on a per-spider basis?
HTTPCACHE_IGNORE_HTTP_CODES = ['302']

#HTTPCACHE_STORAGE = 'scrapy.contrib.httpcache.DbmCacheStorage'
#HTTPCACHE_ENABLED = True

DOWNLOADER_MIDDLEWARES = {
    # use proxy
    'scrapy.contrib.downloadermiddleware.httpproxy.HttpProxyMiddleware': 110,
    'search.middlewares.ProxyMiddleware': 100,

    # You can use this middleware to have a random user agent every request the spider makes.
    # You can define a user USER_AGEN_LIST in your settings and the spider will chose a random user agent from that list every time.
    # 
    # You will have to disable the default user agent middleware and add this to your settings file.

    'search.randomUA_middleware.RandomUserAgentMiddleware': 400,
    'scrapy.contrib.downloadermiddleware.useragent.UserAgentMiddleware': None,
}

EXTENSIONS = {
    'search.Handle503_extension.SpiderLog503' : 500
}

# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36"

# User agent rotation settings
ROTATE_UA = True
USER_AGENT_LIST = [ USER_AGENT ]

# populate user agent list
try:
    with open("UA_list.txt") as ua_input:
        for line in ua_input:
            USER_AGENT_LIST.append(line.strip())
except:
    USER_AGENT_LIST = [ USER_AGENT ]

# fall back to default values if file not found
if not USER_AGENT_LIST:
    USER_AGENT_LIST = [ USER_AGENT ]
