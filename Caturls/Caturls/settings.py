# Scrapy settings for Caturls project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/topics/settings.html
#

BOT_NAME = 'Caturls'

SPIDER_MODULES = ['Caturls.spiders']
NEWSPIDER_MODULE = 'Caturls.spiders'
ITEM_PIPELINES = ['Caturls.pipelines.CaturlsPipeline']
LOG_ENABLED = False

# use proxy
DOWNLOADER_MIDDLEWARES = {
    'scrapy.contrib.downloadermiddleware.httpproxy.HttpProxyMiddleware': 110,
    'Caturls.middlewares.ProxyMiddleware': 100,
}

#TODO: do we need this to allow duplicates?
#DUPEFILTER_CLASS = 'scrapy.dupefilter.BaseDupeFilter'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'Caturls (+http://www.yourdomain.com)'
