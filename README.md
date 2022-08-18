TMText
=======

Spiders for each sitemap from list `sitemaps_list.txt`, using the scrapy framework.

Each spider can be run from its own folder, with `scrapy crawl <spider_name>`.

This will result in output files with the crawling results, in `<spider_name>_categories.jl` files in each spider's directory.

The main code for each spider is found in each spider's subdirectory called `spiders`, in the `<spider_name>_spider.py` file.