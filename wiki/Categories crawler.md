The Categories crawler is a scrapy project found in the "Categories" directory.

The crawler supports extraction of a site's product categories tree (full or partial), for different sites. For each site the implementation is common except for the spider file.

**When implementing support for a new site, only a spider file needs to be created** - it will be integrated with the rest of the crawler.


The crawler's structure follows the structure of a regular scrapy project.

spiders
========

In the spiders directory are the python source files containing the spiders.

For each site, there is a corresponding spider file.

Spider files are named like `<site>_spider.py`.

Each spider's name (the "name" property of the spider) has the corresponding site's name.

Example:

* for www.amazon.com:
      - spider file: amazon_spider.py
      - spider name: amazon

Each spider extracts product categories from a certain site, then returns each of them as an item of type `CategoryItem`, defined in the project's items.py file.

items
======

The items.py file defines the items used in the spiders. For crawling categories, relevant is `CategoryItem`, which defines the object types that must be returned by each spider.

`CategoryItem` contains several fields that describe a category, some of which are mandatory (every returned item in the spider should have it), others are optional:

__CategoryItem Fields__

Mandatory:

* url - string, the url of the category link
* text - string, the name of the category
* parent_url - string, the url to the parent of the category (mandatory if there is a parent category)
* department_text - string, name of top-level department (level 1) this category belongs to
* department_url - string, url to page of top-level department (level 1) this category belongs to
* department_id - integer, id of top-level department (level 1) this category belongs to. Should be a unique identifier (spider-wide) for the department.
* level - integer, the level of nesting. Departments (usually the top level categories) should be level 1. Their subcategories will be level 0, their further subcategories level -1 etc.
* description_wc - integer, wordcount of description for that category, as found on category's page. Will be 0 if no description is found. The wordcount should be computed using the tokenization method available in spiders_utils.py, in `Utils.normalize_text()`

Optional:

* parent_text - string, the name of the parent of the category
* grandparent_text - string, the name of the grandparent of the category
* grandparent_url - string, url to the grandparent category
* special - integer, is the category special or not? ('special' if it doesn't really contain products, but special offers, services etc). 1 if it is, empty if it isn't

* nr_products - integer, number of products in category. Must be extracted for categories where number of products is available on the category page

* description_title - string, title of description of category found on category landing page, if any.
* description_text - string, body of text of description of category found on category landing page, if any.

* keywords_wc - dictionary, number of occurrences of keywords from description tit le in description text. This is a dictionary with keywords as keys and word counts as values.
* keywords_density - dictionary, density of keywords from description title in description text. This is a dictionary with keywords as keys and percentage values as values. (same keywords from keywords_wc)

keywords_wc and keywords_density can be generated from a description title and a description text using the `Utils.phrases_freq()` method in spiders_utils.py

* catid - integer, unique identifier for category (needed for overall item count in pipelines, currently only available for Walmart)
* parent_catid - integer, parent category's catid (needed for overall item count in pipelines, currently only available for Walmart)

* classification - breakdown of a (sub)category into further subcategories, by various criteria (e.g. Brand) (optional)

e.g. of classification field:

      "classification": {
                         "<Criterion1>": [
                                             {"name": "<Name1.1>", "nr_products": <Nr1.1>},
                                             {"name": "<Name1.2>", "nr_products": <Nr1.2>}
                                         ]
                         }
pipelines
==========

The pipelines.py file defines the output format for the spiders.

The pipelines class used is `CommaSeparatedLinesPipeline`, which creates JSON objects from the categories items and writes one on each line, lines separated by commas.

For spiders with `compute_nrproducts` attribute set, it also tries to compute overall number of products for categories where it was not extracted, using their subcategories product counts.

settings
===========

The settings.py file defines settings for the spider.
Settings are currently default ones, except for duplicates filter:

    DUPEFILTER_CLASS = 'scrapy.dupefilter.BaseDupeFilter'

This means scrapy won't filter duplicate URLs. If filtering is needed, it should be done explicitly inside the spider. 