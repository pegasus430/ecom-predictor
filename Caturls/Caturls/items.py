# Definition of the models for the scraped items

from scrapy.item import Item, Field

class ProductItem(Item):
    product_url = Field() # url of product page
    category = Field() # category of product; optional