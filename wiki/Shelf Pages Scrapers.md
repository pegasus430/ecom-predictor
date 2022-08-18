[TOC]

# What it is

This is another type of crawlers to scrape product links from 'Shelf' pages (like http://www.walmart.com/browse/baby/diapers/5427_486190_1101406).

This type of spiders is similar to the Product Ranking Spiders (**SC**orecard Spiders), so the spider files are located in the same folder `/product-ranking/product_ranking/spiders/`

The following 3 fields are scraped at the moment:

* assortment_url - an array for scraped product links (**not in use?**)

* results_per_page - the number of products per page, reported by site itself

* scraped_results_per_page - the actual number of products per page, as the spider actually collected

# Accepted params

* spider name (like for SC spiders)

* product_url (like for SC spiders)

* num_pages - the number of pages to scrape, in case if there are many products returned (default value is 1).

# Example run

```
 scrapy crawl walmart_shelf_urls_products  -a product_url=http://www.walmart.com/browse/baby/diapers/5427_486190_1101406
```

OR

```
 scrapy crawl walmart_shelf_urls_products -a num_pages=9999 -a product_url=http://www.walmart.com/browse/baby/diapers/5427_486190_1101406
```

# Supported platforms

Both SQS-based core and SC keyword servers support this. You only need the correct spider name and (optionally) `num_pages` param.

# Example response

There are currently 2 types of responses:

1) http://dpaste.com/2VX0G4D.txt - basically, only URLs are scraped (and ordered already)

2) http://dpaste.com/2TJT4TZ.txt - the output is somehow similar to SC spiders (use `ranking` field to sort the URLs)

# Collected fields

* shelf_name - see https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=3313#c8
* shelf_path - see see https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=3313#c8
* scraped_results_per_page - contains num of URLs per page for "type 1" spiders (see "Example response" section)
* assortment_url - contains collected URLs for "type 1" spiders (see "Example response" section) (**not in use?**)