# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

from scrapy.item import Item, Field


class PageItem(Item):
    base_url = Field()
    total_time = Field()

    id = Field()
    url = Field()
    imported_data_id = Field()
    category_id = Field()
    body = Field()


class RequestErrorItem(Item):
    base_url = Field()

    id = Field()
    http_code = Field()
    error_string = Field()
