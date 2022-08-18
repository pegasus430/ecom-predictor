# Scrapy settings for General project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/topics/settings.html
#

BOT_NAME = 'General'

SPIDER_MODULES = ['General.spiders']
NEWSPIDER_MODULE = 'General.spiders'

ITEM_PIPELINES = ['General.pipelines.GeneralPipeline']

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'General (+http://www.yourdomain.com)'
