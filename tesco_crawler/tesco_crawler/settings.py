# Scrapy settings for tesco_crawler project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'tesco_crawler'

SPIDER_MODULES = ['tesco_crawler.spiders']
NEWSPIDER_MODULE = 'tesco_crawler.spiders'

# Crawl responsibly by identifying yourself (and your website) on the
# user-agent
#USER_AGENT = 'tesco_crawler (+http://www.yourdomain.com)'
