# Definition of the models for the scraped items

from scrapy.item import Item, Field

class SearchItem(Item):
    product_name = Field() # name of the search result product
    product_url = Field() # url of result product page
    product_model = Field() # product model of product as extracted from its page or the results page (if found somewhere other that inside its name)
    product_upc = Field() # product UPC
    product_dpci = Field() # product DPCI. Identifier specific to target.com
    product_asin = Field() # product DPCI. Identifier specific to amazon.com
    product_brand = Field() # product brand as extracted from special element in product page
    product_category_tree = Field() # product cateogory tree - list of categories, from top level to lowest level
    product_keywords = Field() # product keywords (from page source, meta elements)
    product_image_url = Field() # main image url
    product_image_encoded = Field() # main image, encoded as a string using its histogram and blockhash

    manufacturer_code = Field() # product code on manufacturer site. e.g.: product code on maplin.co.uk (when maplin is manufacturer), 
                                # "manufacturer reference" on amazon.co.uk
    bestsellers_rank = Field() # product rank in bestsellers list on target site

    origin_url = Field() # original product url
    origin_name = Field() # product name on origin site
    origin_model = Field() # original (source) product model
    origin_upc = Field() # original (source) product UPC
    origin_dpci = Field() # original (source) product DPCI. Identifier specific to target.com
    origin_asin = Field() # original (source) product DPCI. Identifier specific to amazon.com
    origin_brand = Field() # original (source) product brand
    origin_brand_extracted = Field() # source product brand - as extracted from product name: not guaranteed to be correct
    origin_category_tree = Field() # source product cateogory tree - list of categories, from top level to lowest level
    origin_keywords = Field() # source product keywords (from page source, meta elements)
    origin_image_url = Field() # source product main image url
    origin_image_encoded = Field() # source product image, encoded as a string using its histogram and blockhash


    origin_manufacturer_code = Field() # product code on manufacturer site.
                                       #  e.g.: product code on maplin.co.uk, "manufacturer reference" on amazon.co.uk
    origin_bestsellers_rank = Field() # product rank in bestsellers list on source (origin) site

    product_origin_price = Field() # price of product on origin site, in dollars
    product_target_price = Field() # price of product on target site, in dollars

    product_images = Field() # for manufacturer spider: nr of product images on target (manufacturer) site
    product_videos = Field() # for manufacturer spider: nr of product videos on target (manufacturer) site

    confidence = Field() # score in percent indicating confidence in match
    UPC_match = Field() # binary field (1/0) indicating if there was a match between UPCs
    model_match = Field() # binary field (1/0) indicating if there was a match between model numbers

# items used in walmart_fullurls spider to match walmart ids to their product pages full URLs
class WalmartItem(Item):
    walmart_id = Field()
    walmart_short_url = Field() # like http://www/walmart.com/ip/<id>
    walmart_full_url = Field()