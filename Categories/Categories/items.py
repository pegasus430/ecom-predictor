# Definition of models for the scraped items

from scrapy.item import Item, Field

class CategoryItem(Item):
    url = Field() # url of category
    text = Field() # name of category
    parent_text = Field() # name of parent category (if any)
    parent_url = Field() # url of parent category page
    grandparent_text = Field() # name of 'grandparent' category (optional)
    grandparent_url = Field() # url of 'grandparent' category (optional)
    level = Field() # level of category in the category tree (from narrower to broader categories). Departments have level 1, top level categories level 0, further subcategories have levels<0
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
    classification = Field() # dictionary containing breakdown of a (sub)category into further subcategories, by various criteria (e.g. Brand). Optional (for now only implemented for Walmart)
    # Classification dictionary structure:
    # "classification": {
                        # "<Criterion1>": [
                        #                     {"name": "<Name1.1>", "nr_products": <Nr1.1>},
                        #                     {"name": "<Name1.2>", "nr_products": <Nr1.2>}
                        #                 ]
                        # }

    page_text = Field() # name of page in sitemap that the category was found on (necessary for some sites, optional)
    page_url = Field() # url of page in sitemap that the category was found on (necessary for some sites, optional)

    toplevel_category_text = Field() # (optional, not yet implemented) name of top-level (level 0) category that current item belongs to
    toplevel_category_url = Field() # (optional, not yet implemented) url of page of top-level (level 0) category that current item belongs to

    catid = Field() # (optional) unique id identifying current item. Used where categories tree is necessary (where total item count for each category is used)
    parent_catid = Field() # (optional) unique id identifying parent of current category. Used where categories tree is necessary (where total item count for each category is used)


class ProductItem(Item):
    url = Field() # url of product page
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
