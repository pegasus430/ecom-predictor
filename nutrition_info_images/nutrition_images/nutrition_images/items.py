# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class NutritionImagesItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    image = scrapy.Field()
    slope_average = scrapy.Field()
    distance_average = scrapy.Field()
    nr_lines = scrapy.Field()
    is_likely_text = scrapy.Field()

class ScreenshotItem(scrapy.Item):
    text = scrapy.Field()
    path = scrapy.Field()
