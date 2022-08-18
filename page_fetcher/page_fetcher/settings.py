# Scrapy settings for page_fetcher project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'page_fetcher'

SPIDER_MODULES = ['page_fetcher.spiders']
NEWSPIDER_MODULE = 'page_fetcher.spiders'

ITEM_PIPELINES = {
    'page_fetcher.pipelines.PageFetcherPipeline': 300,
}

# Crawl responsibly by identifying yourself (and your website) on the
# user-agent
#USER_AGENT = 'page_fetcher (+http://www.yourdomain.com)'
