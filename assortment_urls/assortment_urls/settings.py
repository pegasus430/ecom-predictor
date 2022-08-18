# -*- coding: utf-8 -*-

# Scrapy settings for assortment_urls project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'assortment_urls'

SPIDER_MODULES = ['assortment_urls.spiders']
NEWSPIDER_MODULE = 'assortment_urls.spiders'

ITEM_PIPELINES = {
    'assortment_urls.pipelines.AssortmentUrlsPipeline': 500,
}

DEPTH_PRIORITY = 1
SCHEDULER_DISK_QUEUE = 'scrapy.squeue.PickleFifoDiskQueue'
SCHEDULER_MEMORY_QUEUE = 'scrapy.squeue.FifoMemoryQueue'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'assortment_urls (+http://www.yourdomain.com)'

DOWNLOAD_DELAY = 0.1    # 250 ms of delay
