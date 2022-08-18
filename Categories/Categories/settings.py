# Scrapy settings for Categories project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'Categories'

#HTTPCACHE_STORAGE = 'scrapy.contrib.downloadermiddleware.httpcache.FilesystemCacheStorage'
#HTTPCACHE_POLICY = 'scrapy.contrib.httpcache.RFC2616Policy'
import os
homedir = os.getenv("HOME")
HTTPCACHE_DIR = homedir + '/.scrapy_cache'

SPIDER_MODULES = ['Categories.spiders']
NEWSPIDER_MODULE = 'Categories.spiders'

ITEM_PIPELINES = ['Categories.pipelines.CommaSeparatedLinesPipeline']

# don't filter duplicates
DUPEFILTER_CLASS = 'scrapy.dupefilter.BaseDupeFilter'

# set user agent to avoid blocking
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.57 Safari/537.36"
