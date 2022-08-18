# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

from scrapy.item import Item, Field


class BazaarVoiceReviewsItem(Item):
    bv_client = Field()

    # The entire BV data structure.
    data = Field()
