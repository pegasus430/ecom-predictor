Scraping product categories from 10 sitemaps and grouping them.

# Description

## Scraping

The Categories spider found in the Categories folder supports scraping of product categories for different sites, in the project there is a separate source file containing the spider for each site:

* Walmart
* Amazon
* Bestbuy
* Wayfair
* Overstock
* Tigerdirect
* BJs
* Bloomingdales
* Sears
* Toysrus
* Staples
* Sherwin-Williams

The spiders crawl these sitemaps and extract the names and URLs of the categories, and store them in JSON files as objects (one object on each line), which are key-value pairs, with the keys `text` for the category name and `url` for the URL.

__Example__ of output object:

    {"url": ["http://www.bestbuy.com:80/site/Electronics/TV-Video/abcat0100000.c?id=abcat0100000"], "text": ["TV & Home Theater"]}

This is the complete list of possible fields (keys):

* url - the url of the category link
* text - the name of the category
* parent_text - the name of the parent of the category (optional)
* parent_url - the url to the parent of the category (optional)
* grandparent_text - analogous (optional)
* grandparent_url - analogous (optional)
* department_text - name of top-level department this category belongs to (level 1. Exception: for Amazon departments are level 2)
* department_url - url to page of top-level department this category belongs to (level 1. Exception: for Amazon departments are level 2, some of them don't have URLs)
* department_id - id of top-level department this category belongs to (level 1. Exception: for Amazon departments are level 2)
* level - the level of nesting. I have chosen the value 0 to describe the main level of categories, greater numbers for their parents (1 for parents, 2 for grandparents), and -1 for lists where there are very detailed subcategories, these are marked with -1, -2 for their subcategories etc.
* special - is the category special or not? (in the sense we talked about in the emails). 1 if it is, empty if it isn't

additional_fields:

* nr_products - number of products in category. This is currently available for category landing pages that explicitly give the number of products available in the page (usually not for departments).
* description_title - title of description of category found on category landing page, if any.
* description_text - body of text of description of category found on category landing page, if any.
* description_wc - number of words in body of text of description. If no description found, description_wc=0
* keywords_wc - number of occurrences of keywords from description title in description text. This is a dictionary with keywords as keys and word counts as values.
* catid - unique identifier for category (optional, currently only available for Walmart)
* parent_catid - parent category's catid (optional, currently only available for Walmart)
* keywords_density - density of keywords from description title in description text. This is a dictionary with keywords as keys and percentage values as values. (same keywords from keywords_wc)
* classification - breakdown of a (sub)category into further subcategories, by various criteria (e.g. Brand) (optional)

e.g. of classification field:

      "classification": {
                         "<Criterion1>": [
                                             {"name": "<Name1.1>", "nr_products": <Nr1.1>},
                                             {"name": "<Name1.2>", "nr_products": <Nr1.2>}
                                         ]
                         }

Sites for which "additional fields" are available:

* Walmart
* Staples
* Bestbuy
* Macys
* Amazon

Example output files can be found in `sample_outputs`.

## Documentation

[Categories crawler](Categories crawler)

## Grouping

These output files are used to generate groups of similar categories across different sites.

To generate groupings, run script `group_categories.py`. This will generate a file `groups.jl`, in a similar format to the spiders' output files, but containing additional fields such as `Group_name`, `Group_members` and `site`. Currently this script generates groupings for level 1 categories (departments).

__Example output item__ for groupings:

    {"Group_members": [{"url": "http://www.overstock.com/Bedding-Bath/43/store.html", "text": "Bedding & Bath", "site": "overstock", "level": 1}, {"url": "http://www.wayfair.com/Bed-and-Bath-C215329.html", "text": "Bed & Bath", "site": "wayfair", "level": 1}], "Level": 1, "Short_name": "Bedding, Bath", "Group_name": "Bedding & Bath; Bed & Bath"}

## Statistics

Statistics for number of levels, departments, categories and subcategories for each site are generated with the `statistics.py` script. This will output a file `statistics.txt` containing a table with the statistics.


# Tools

The spiders are written using the [scrapy](http://scrapy.org/) framework for python. 

In order to generate the output files you will need it installed on your system. Here is an installation guide: http://doc.scrapy.org/en/latest/intro/install.html

Alternatively, I can generate the output files and add them to the repository so no installation is needed, neither is running the spiders.

All the scripts are written in python 2.7.3. Python packages used and necessary for running the scripts:

* [nltk](http://nltk.org/)
* [networkx](http://networkx.github.io/)

# Usage

Each of the spiders generates a JSON output file named `<spider_name>_categories.jl`, located in the spider's main directory.

To run the spider and generate the file, from the spider's main directory, run:
    
    scrapy crawl <spider_name>

(`spider_name` must be all lowercase letters)

__Example__:

    cd Categories
    scrapy crawl amazon

This will generate the file `amazon_categories.jl`.

The output files contain one JSON object on each line, lines are separated by commas.

To generate groupings run `group_categories.py`. This will generate the file called `groups.jl`.

To generate statistics run `statistics.py`. This will generate the file `statistics.txt`.