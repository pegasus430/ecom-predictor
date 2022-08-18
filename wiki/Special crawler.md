REST service that crawls and extracts data from an input site product page and serves it to clients, in JSON format.

The service supports GET requests to return data for a certain product, for either all data at once or for a specific type of data, or any combination of several types of data.

Supported sites:

* amazon
* argos
* babysecurity
* bestbuy
* bhinneka
* bloomingdales
* chicago
* chicksaddlery
* costco
* drugstore
* freshamazon
* freshdirect
* george ("direct.asda.com")
* hersheys
* homedepot
* impactgel
* kmart
* macys
* maplin
* newegg
* ozon
* peapod
* pgestore
* quill
* samsclub
* soap
* souq
* staplesadvantage
* staples
* statelinetack
* target
* tesco
* tescogroceries
* vitadepot
* walmart
* wayfair



__Resources__
==============

## GET `/get_data/?url=<product_url>[&site=<site>&data=<data_type1>&data=<data_type2>]`

__Request parameters__
======================

- Mandatory parameters:
    - `url` - the URL of the input product page. It is recommended that the URL is percent-encoded, especially if it contains `&` characters.

- Optional parameters:
    - `data`
    - `site` - the site of the input product page. If it is not provided explicitly, the service will infer it from the input URL

## Accepted values for parameters:

- **`site`** - the domain name for one of the supported sites above. Example: `walmart`
- **`data`** - can either not be specified, or be one of the strings in the list below. Any number of `data` parameters can be given in a request, in any combination.

    - `url`, - url of product
     - `event`,
     - `product_id`,
     - `site_id`,
     - `date`,
     - `status`,
     - `scraper`, - version of scraper in effect. Relevant for Walmart old vs new pages.
     - `product_name`, - name of product
     - `product_title`, - page title
     - `title_seo`, - SEO title
     - `model`, - model of product
     - `upc`, - upc of product
     - `features`, - features of product
     - `feature_count`, - number of features of product
     - `model_meta`, - model from meta
     - `description`, - short description / entire description if no short available
     - `long_description`, - long description / null if description above is entire description

     - `mobile_image_same`, - whether mobile image is same as desktop image, 1/0
     - `image_count`, - number of product images
     - `image_urls`, - urls of product images
     - `video_count`, - nr of videos
     - `video_urls`, - urls of product videos
     - `pdf_count`, - nr of pdfs
     - `pdf_urls`, - urls of product pdfs
     - `webcollage`, - whether video is from webcollage (?), 1/0
     - `htags`, - h1 and h2 tags
     - `loaded_in_seconds`, - load time of product page in seconds
     - `keywords`, - keywords for this product, usually from meta tag
      
     - `review_count`, - total number of reviews
     - `average_review`, - average value of review
     - `max_review`, - highest review score
     - `min_review`, - lowest review score
      
     - `price`, - price, string including currency
     - `in_stores`, - available to purchase in stores
     - `in_stores_only`, - whether product can be found in stores only
     - `owned`, - whether product is owned by site
     - `owned_out_of_stock`, - whether product is owned and out of stock
     - `marketplace`, - whether product can be found on marketplace
     - `marketplace_sellers`, - sellers on marketplace (or equivalent) selling item
     - `marketplace_lowest_price`
      
     - `categories`, - full path of categories down to this product's
     - `category_name`, - category for this product
     - `brand` - brand of product


- **`url`**:

    * For walmart.com, expected URL format is `http://www.walmart.com/<ip>[<optional-part-of-product-name]/<product_id>`
    * For tesco.com, expected URL format is `http://www.tesco.com/direct/<part-of-product-name>/<product_id>.prd`

**To be added**:
- Table with supported data types for each site
- expected URL formats for each site

In case of any invalid parameter value, the service will return an `InvalidUsage` error with a relevant error message, code 400. For more details see below.

__Running the service on your machine__
=======================================

Either

###1\. Run service directly:

Install dependencies in `requirements.txt` and `README.txt`

Run service directly:

    $ cd special_crawler
    $ sudo python crawler_service.py

Or

###2\. Run the service from a virtualenv:

Create virtualenv, install dependencies (in `special_crawler/requirements.txt`), and activate it:

    $ mkdir <virtualenv_directory>
    $ virtualenv <virtualenv_directory>
    $ . <virtualenv_directory>/bin/activate
    $ pip install -r requirements.txt

Set python path to virtualenv python binary in service shebang line (first line in the `crawler_service.py` file)

    #!/<virtualenv_directory_fullpath>/bin/python

Run service (the file should be executable):
    
    $ sudo ./crawler_service.py

When you're done you can exit the virtualenv; while inside it, run:

    $ deactivate

__Responses__
=============

The service returns a JSON object according to this spec: https://github.com/ContentAnalytics/tmeditor/wiki/Scraper-Spec

Status codes:

- `200` - request was successful
- `404` - route was not found
- `400` - invalid usage (usually bad parameters)
- `500` - internal server error
- `502` - error communicating with scraped site (usually when the request to the product page from the scraper gets a `500` status code response)

**To be added**: response code for unavailable product.

## Errors

In case of any error (400/404/500/502), the service will return a JSON response with the key `"error"` and the value a relevant message.

Example:

`400` error:

    $ curl "localhost/get_data?site=amazon&url=http://www.amazon.com"
    {
      "error": "Unsupported site: amazon"
    }

`404` error:

    $ curl "localhost/get_something_else""
    {
      "error": "Not found"
    }

`500` error:

    $ curl "localhost/get_data?url=http://www.walmart.com/ip/1031296&data=long_description"
    {
      "error": "Internal server error"
    }

`502` error:

    $ curl "localhost/get_data?url=http://www.walmart.com/ip/1031296&data=long_description"
    {
      "error": "Error communicating with site crawled."
    }

## Successful response

In case of **success**, service returns a JSON response having as keys the types of data requested (or all types of data if "data" parameter not specified in the request), and as values, the extracted data for the input product.

The data types are grouped into several containers, as described in the [spec](https://github.com/ContentAnalytics/tmeditor/wiki/Scraper-Spec)

Example output:

    $ curl "localhost/get_data?url=http://www.walmart.com/ip/Betty-Crocker-Warm-Delights-Molten-Chocolate-Cake-Mix-3.35-oz/10311296"
  
    {
    "classification": {
      "brand": "Betty Crocker", 
      "categories": [
        "Food", 
        "Bakery & Bread", 
        "Dessert Breads"
      ], 
      "category_name": "Dessert Breads"
    }, 
    "date": "2014-11-05 19:44:04", 
    "event": null, 
    "page_attributes": {
      "htags": {
        "h1": [
          "Betty Crocker Warm Delights Molten Chocolate Cake Mix, 3.35 oz"
        ], 
        "h2": [
          "About this item", 
          "Customer Reviews | 2 reviews | 4 out of 5", 
          "Customer Q&A", 
          "Product Recommendations", 
          "Site Information"
        ]
      }, 
      "image_count": 1, 
      "image_urls": [
        "http://i5.walmartimages.com/dfw/dce07b8c-80a6/k2-_8d1a8bee-020a-470b-b274-7eec7e636170.v1.jpg"
      ], 
      "keywords": "Betty Crocker Warm Delights Molten Chocolate Cake Mix, 3.35 oz, Wal-mart, Walmart.com", 
      "loaded_in_seconds": 0.82, 
      "mobile_image_same": null, 
      "pdf_count": 0, 
      "pdf_urls": null, 
      "video_count": 0, 
      "video_urls": null, 
      "webcollage": 0
    }, 
    "product_id": null, 
    "product_info": {
      "description": "Kosher dairy Just add water and microwave     Ingredients:\u00a0   Cake: Sugar, Enriched Flour Bleached (Wheat Flour, Niacin, Iron, Thiamin Mononitrate, Riboflavin, Folic Acid), Partially Hydrogenated Soybean And/Or Cottonseed Oil, Cocoa Processed With Alkali, Corn Starch, Distilled Monoglycerides, Modified Corn Starch, Dried Egg Whites, Whey Protein Isolate, Cellulose Powder, Baking Soda, Salt, Monocalcium Phosphate, Corn Syrup Solids, Nonfat Milk, Soy Lecithin, Xanthan Gum, Artificial Flavor. Freshness Preserved By BHT, Citric Acid, Tocopherol, Ascorbic Acid. Fudge Sauce Pouch: Water, Sweetened Condensed Skim Milk (Skim Milk, Sugar, Corn Syrup), Sugar, Fructose, Partially Hydrogenated Palm Kernel Oil, Cocoa, Corn Starch, Buttermilk, Cocoa Processed With Alkali, Butter, Whey, Salt, Sodium Alginate, Natural And Artificial Flavor, Potassium Sorbate (Preservative), Artificial Color, Mono And Diglycerides, Xanthan Gum, Sodium Bicarbonate. Contains Wheat, Milk, Egg And Soy Ingredients.       Directions:\u00a0   Stir cake mix And 1/4 cup water in bowl until well mixed. Squeezechocolate pouch 10 times. Tear pouch open, And squeeze lines ofchocolate over batter. Note: microwave time is approximate. Microwaveuncovered on high 1 minute 15 seconds or until only a few dime-size wetspots remain. If necessary, microwave 10 seconds longer. Caution: hot.Remove To heatproof surface, holding rim with both hands. Cool 5 minutesbefore you indulge. High altitude (3500-6500 ft): no change. Important:do not bake in oven or toaster oven. Do not leave microwave unattended.Do not use bowl for reheating. Do not microwave pouches.", 
      "feature_count": 6, 
      "features": "Model No.:29652\nShipping Weight (in pounds):0.209\nProduct in Inches (L x W x H):1.68 x 6.0 x 6.0\nAssembled in Country of Origin:USA\nOrigin of Components:USA\nWalmart No.:9295191", 
      "long_description": null, 
      "model": "29652", 
      "model_meta": "29652", 
      "product_name": "Betty Crocker Warm Delights Molten Chocolate Cake Mix, 3.35 oz", 
      "product_title": "Betty Crocker Warm Delights Molten Chocolate Cake Mix, 3.35 oz", 
      "title_seo": "Betty Crocker Warm Delights Molten Chocolate Cake Mix, 3.35 oz - Walmart.com", 
      "upc": "016000296527"
    }, 
    "reviews": {
      "average_review": 4.0, 
      "max_review": null, 
      "min_review": null, 
      "review_count": 2
    }, 
    "scraper": "Walmart v2", 
    "sellers": {
      "in_stores": null, 
      "in_stores_only": null, 
      "marketplace": 0, 
      "marketplace_lowest_price": null, 
      "marketplace_sellers": null, 
      "owned": 1, 
      "owned_out_of_stock": null, 
      "price": null
    }, 
    "site_id": null, 
    "status": "success", 
    "url": "http://www.walmart.com/ip/Betty-Crocker-Warm-Delights-Molten-Chocolate-Cake-Mix-3.35-oz/10311296"
     }

## Request only specific types of data

Note: The service will make sure a minimum number of requests will be made to the crawled site for any group of data requested.

Each individual requested data type will be returned in its container.

Example:

Requesting only review_count and product title:

    $ curl "localhost/get_data?url=http://www.walmart.com/ip/Betty-Crocker-Warm-Delights-Molten-Chocolate-Cake-Mix-3.35-oz/1031296&data=review_count&data=product_title"

    {
      "product_info": {
        "product_title": "Betty Crocker Warm Delights Molten Chocolate Cake Mix, 3.35 oz"
      }, 
      "reviews": {
        "review_count": 2
      }
    }

## Writing new scrapers

Instructions for commiters to tmtext related to programming new scrapers for new sites can be found [here](Special crawler programming)