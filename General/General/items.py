# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/topics/items.html

from scrapy.item import Item, Field

class CategoryItem(Item):
    url = Field() # url of category
    text = Field() # name of category
    parent_text = Field() # name of parent category
    parent_url = Field() # url of parent category
    grandparent_text = Field() # name of grandparent category
    grandparent_url = Field() # url of grandparent category
    level = Field() # level of category in the nested list (from narrower to broader categories)
    special = Field() # is it a special category? (1 or nothing)
    description_text = Field() # text of category description (if any)
    description_title = Field() # title of category description (if any)
    description_wc = Field() # number of words in description text, 0 if no description
    keyword_count = Field()
    keyword_density = Field()
    nr_products = Field() # number of items in the category
    department_text = Field() # name of the department it belongs to
    department_url = Field() # url of the department it belongs to
    department_id = Field() # unique id of the department it belongs to

class ProductItem(Item):
    url = Field() # url of product page
    site = Field() # site (domain) this product was extracted from
    list_name = Field() # name of product - from bestsellers list
    product_name = Field() # name of product - from product page
    page_title = Field() # title (title tag text) of product page
    department = Field() # department of product - its name
    price = Field() # price of product - a string like "29.5$"
    listprice = Field() # "list price" of product - a string like "29.5$"
    rank = Field() # rank of the product in the bestsellers list
    SKU = Field() # SKU code of product (where available)
    UPC = Field() # UPC code of product (where available)
    date = Field() # date when this was extracted
    bspage_url = Field() # url of the bestsellers page the product was found on (for department-wise bestsellers)

    prod_context = Field() # contains html context in which product info was found. use this field for inspecting page structure
