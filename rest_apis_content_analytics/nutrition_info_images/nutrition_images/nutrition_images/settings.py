# -*- coding: utf-8 -*-

# Scrapy settings for nutrition_images project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'nutrition_images'

SPIDER_MODULES = ['nutrition_images.spiders']
NEWSPIDER_MODULE = 'nutrition_images.spiders'

USER_AGENT = 'Mozilla'

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'nutrition_images (+http://www.yourdomain.com)'
