# Description #

This installation has the two servers running in a single micro instance.

Scrapyd is configured to run with 4 concurrent processes.

# Location #

> Server: keywords.contentanalyticsinc.com (public)  
> IP: 10.11.147.19 (private)  
> Port: 6543


# Summary of All Configured Resources #

Spiders:

- [/ranking_data/](Product Ranking Spiders)

Commands:

- /summary/
- /walmart_ranking_data_with_best_sellers/


# Spiders #

The deployed spiders are:

*    [Product Ranking Spiders](Product Ranking Spiders)

# Resources #

## Spiders ##

The product-ranking spiders are configured in the `/ranking_data/` resource. They accepts all the spider's parameters (such as `searchterms_str`, `quantity`, etc) plus parameter `site` which specifies the site to crawl (such as walmart, asda, tesco or amazon) and `group_name` which group several requests. 

```
spider.product_ranking.resource = /ranking_data
spider.product_ranking.spider_name = {site}_products
spider.product_ranking.project_name = product_ranking
```

For example, to access the service through the public IP to crawl Walmart.com for "hand soap":

- The following URL should be used: http://54.204.194.226:6543/raking_data/
- The following data should be POSTed:  
    - site: walmart
    - searchterms_str: hand soap

After the POST you'll be redirected to other resources and will have to poll until you get a 200 response.

You can add any other [parameter available for the spider](Product Ranking Spiders). Bear in mind that some parameters are specific to a particular spider (such as `search_sort` which is only for walmart) and others are common among all (like `quantity`).

The site can be any of the ones listed in the [spider's page](Product Ranking Spiders). For example: amazon, asda, tesco or walmart.


## Commands ##

### Summarize Search ###

The summarize search command is configured to summarize a single spider, which is how it's normally used.

The `filter` parameter would normally have values such as "brand=tide".

```
command.summary.cmd = ../product-ranking/summarize-search.py --filter '{filter}' - '{spider 0}'
command.summary.resource = summary
command.summary.content_type = text/csv
command.summary.crawl.0.spider_config_name = product_ranking
```

### Add Best Seller Ranking ###

The `add-best-seller.py` command adds a the `best-seller-ranking` field to the dataset by merging a default `search_sort` crawl and a crawl sorted by best sellers.

Sort order only exists for Walmart.com so this configuration already specifies the `site` parameter.

```
command.with-best-seller.cmd = ../product-ranking/add-best-seller.py '{spider 0}' '{spider 1}'
command.with-best-seller.resource = /walmart_ranking_data_with_best_sellers
command.with-best-seller.content_type = application/x-ldjson
command.with-best-seller.crawl.0.spider_config_name = product_ranking
command.with-best-seller.crawl.0.spider_params = site=walmart
command.with-best-seller.crawl.1.spider_config_name = product_ranking
command.with-best-seller.crawl.1.spider_params = site=walmart search_sort=best_sellers
```

Although the crawls are run concurrently (up to 4 in the current configuration), walmart.com's spider is quite slow so you may want to specify a `quantity` parameter.

Remember, after the POST you'll be redirected to other resources and will have to poll until you get a 200 response.

