General instructions
---------------------

This crawler service, with code residing in the `tmtext` repo, in the `special_crawler` directory, is a REST service that extracts info on products from several ecommerce sites, and returns it in JSON format.

The service supports several sites, for every site the response has the same structure.

The code is structured into:

- a main `Scraper` class, in `extract_data.py`, that all the other scraper classes will extend. This class handles parsing the request, calling the individual scrapers for extracting data for a specific site, and returning the response in a specific format. The format should conform to the spec [here](https://github.com/ContentAnalytics/tmeditor/wiki/Scraper-Spec)

- individual scraper classes that extend the base scraper class, one for each site. (example: `WalmartScraper`, code in `extract_walmart_data.py`). These scrapers handle implementation of methods that handle extraction of each individual data type for a certain site (example of data types: title, price etc).

- the actual web app, found in `crawler_service.py`. This imports the supported scrapers, and uses them to respond to requests. All active scrapers should be found in `SUPPORTED_SITES` variable in `crawler_service.py`. This is a dictionary that associates the domain of a supported site with the class that implements the scraper for it.

### Instructions for writing a scraper

- create a new branch branching from `master`. Before merging into master, make sure to follow the instructions below, under the `Merging into master` heading.

- add a new scraper class that extends `Scraper`, in its own source code file (preferably named `extract_*_data.py`)
- add a class variable (to the new scraper) named `DATA_TYPES` that will be a dictionary containing returned data types as keys, and methods that handle extraction of those data types as values.

    - Valid data types are the ones in `BASE_DATA_TYPES_LIST` in `extract_data.py`
    - The `DATA_TYPES` dictionary only needs to contain the data types for which your specific scraper has support. For the others, the service will automatically return null.
    - The following data types don't need to be implemented in the subscrapers, because they are already implemented in the base class (any implementation in the scrapers will overwrite the base class implementation): 
        - `date`
        - `loaded_in_seconds`
        - `status`
        - `url`
        - `event`
        - `owned`
        - `owned_out_of_stock`
        - `site_online_in_stock`
        - `in_stores_in_stock`
        - `marketplace_in_stock`
        - `in_stores_only`
        - `online_only`
        - `in_stock`
        - `meta_tags`
        - `meta_tags_count`
    - *to be added* (ignore for now): If there are data types for which the methods that implement extraction don't use the page source's lxml tree at all, but use other requests (e.g. for javascript generated content, for which the site uses AJAX requests), they should be added to a separate (but similar) `DATA_TYPES_SPECIAL` dictionary, so the base class can make the needed requests more effieciently.

- implement in the scraper class each of the methods declared in `DATA_TYPES`. They will implement extraction of the corresponding data type and return the result.
    + For extracting info from the product page source's DOM tree, some `Scraper` class's attributes can and should be used: 

        - `self.tree_html` - an lxml tree of the page's DOM. It is available in each subscraper class, and DOM elements can be accessed using `self.tree_html.xpath(...)`

        - `self.product_page_url` - the url of the product in the request, also available in every subscraper class if needed.
            
    + The return values should be in accordance with the definition of the data types in the [spec](https://github.com/ContentAnalytics/tmeditor/wiki/Scraper-Spec), making sure the correct type is returned (e.g. string, list) and that `None` is returned for data that was not found.
    
    + Please document your code using comments and docstrings.

- optionally (but recommended), implement the input validation `check_url_format()` method, that should use `self.product_page_url` and return `True` if it looks like a valid url for the given site, or `False` if it doesn't. Along with it, add a class variable `INVALID_URL_MESSAGE`, that contains a string describing the expected url format (in accordance with your implementation of the input validation) - to be used as an error message for clients that made requests with invalid urls.

- in `crawler_service.py`, import your scraper and add it to `SUPPORTED_SITES`. Make sure there are no syntax errors in your scraper or they will break the entire service.

#### Other details

- No image: *to be added* (ignore for now)


#### Examples

As models for developing your own scraper, you can look at `extract_walmart_data.py` or `extract_tesco_data.py`


### Adding new data types

If you are given an explicit task to add new data types (except from the ones in the spec), then aside from adding them to `DATA_TYPES` in your scraper, you also need these changes to the base class (otherwise they will be ignored):

- add your new data type to the `BASE_DATA_TYPES_LIST` class variable in the `Scraper` class (the `extract_data.py` file), along with a comment describing it in short.

- if in the response object, this new data type should not be found directly in the object's root, but in one of the containers (e.g. `page_attributes`, `seller`), you need to also add it to the `DICT_STRUCTURE` class variable, in the list corresponding to its container.

- add it to the [spec](https://github.com/ContentAnalytics/tmeditor/wiki/Scraper-Spec)

### Non-product pages

#### The idea

The scrapers need to identify when the current page being scraped is not actually a valid product page and abort scraping to avoid returning irrelevant results. These pages can be either of unavailable/discontinued products (e.g. http://www.walmart.com/ip/2443178), or different types of content altogether (category pages etc).

The service has a mechanism implemented so that it will automatically abort scraping and return a failure message if it encounters such an invalid page.

#### Adding support for non-product detection to a scraper

All that the individual scrapers have to do is implement the `not_a_product()` method defined in the base `Scraper` class, and return `True` in case the current page does not look like a valid product page.

#### Ideas for identifying non-product pages

For deciding if you're looking at a valid product page, you can use some heuristics using the page source, the content and the html attributes.
It's recommended that you try to make it as robust as possible so that it works for various examples, so that you don't reject actual product pages even if their structure varies a bit.

For example, there might be the html element that holds the product name, that could look something like this:

    <div class="product-name"> Some Product <div>

You could check for this class `product-name` that probably doesn't exist in other types of pages. You could couple this with another similar test to make sure it's robust.

When a task for implementing this is assigned to you, you will also be provided specifications with examples of non-product pages for that site, that can be used in implementing the page validation.

An example of a simple implementation can be found in the walmart scraper (`extract_walmart_data.py`), and another in the bhinneka scraper (`extract_bhinneka_data.py`)

Merging into master
-------------------

When merging code related to the supplemental crawler service (`special_crawler/crawler_service.py`) from other branches into the master branch, the following should be taken into account to make sure the service will still work properly.

So before merging, these things should be checked:

1. There are no new dependencies
2. Tests should pass

Details:

###1. New dependencies

If new scrapers are implemented, and they have new python dependencies (that are not part of the python core modules), these scrapers **should not be pushed to master**. These would cause an exception in the deployed service.

You should let me (Ana) know about them, and I'll take care of merging and deploying safely.

###2. Testing

To make merging safer, there are some minimal tests that should be run before merging.

To run all tests:

First start the service. For instructions for running the service, see the [documentation wiki](https://bitbucket.org/dfeinleib/tmtext/wiki/Special crawler), under the [`Running the service on your machine` heading](https://bitbucket.org/dfeinleib/tmtext/wiki/Special%20crawler#markdown-header-running-the-service-on-your-machine).

Then in a separate terminal run the tests:

    $ cd special_crawler
    $ python -m unittest test_service.ServiceSimpleTest

- If the new code is a change in an existing scraper, just run the existing tests.
- If the new code implements a new scraper, a test should be written for the new site in the `ServiceSimpleTest` class, following the example of the tests for the other sites.

To run the tests for just one site:

    $ python -m unittest test_service.ServiceSimpleTest.test_<site>_specificdata

and

    $ python -m unittest test_service.ServiceSimpleTest.test_<site>_alldata

Of course, other tests can be added as well.

Obviously, all tests should pass before merging into master.

Also, please make sure you don't push other changes except from the newly implemented scraper and the minimal necessary changes in `crawler_service.py` (importing the new scraper and adding it to `SUPPORTED_SITES`)


[outdated] Migration to new response format
--------------------------------------------------------

All scrapers that are part of this service need to undergo some restructuring in order for the response object to:

1. Be uniform across all scrapers/sites
2. Conform with the spec [here](https://github.com/ContentAnalytics/tmeditor/wiki/Scraper-Spec)

For this, most changes need to be done to the base class (`Scraper.py`), which will take care of packing data in containers like described in the spec, and return the json object.
These were implemented and can be found on the **`sc_restructure_output`** branch.

Some changes need to be done to the subscrapers as well. Below are the steps that need to be followed.

##Instructions

#### 1. Branch out from `sc_restructure_output`

This branch contains the changes made so far related to restructuring the response object. We should work on this separate branch before everything is in place and can be pushed to master and 100% usable.
So please, instead of your usual branch, use one branched from `sc_restructure_output` instead. 

    $ git checkout sc_restructure_output        # switch to relevant branch
    $ git checkout -b <your_new_branch_name>    # create your own branch from it

The branch is synchronized with master so everything else there is already up to date.

*Note*:
 If new unrelated urgent features need to be implmented for a scraper, they should probably be pushed to your regular branch and then merged into master, so they can be used right away; then we'll take care of synchronizing with `sc_restructure_output` as well.

#### 2. Revise returned fields supported in the old scrapers to match the new spec

2.1. Rename fields where name has been changed

Example: `nr_reviews` => `review_count`

2.2. Make sure they all return the correct types according to the spec

Example: `price` must be string; `image_urls` must be list

2.3. Make sure that when certain info is not found, `None` is returned, instead of an empty object (like `""` or `[]`)

For example, if no video was found for a product, `video_urls` should return `None`

2.4. Remove from the code deprecated methods.

If there were methods used to extract data types that are not needed anymore, remove the from the restructured code, and the corresponding fields from `DATA_TYPES`/`DATA_TYPES_SPECIAL`.

For example, extraction of anchors is deprecated.

2.5. Implement special behavior for unavailable products (see spec)

*Note*: Will add more info on this soon. Leave it for now.

2.6. `DATA_TYPES` and `DATA_TYPES_SPECIAL` format remains unchanged.

Unsupported fields don't need to be added to `DATA_TYPES` . Just continue to keep only supported fields there.
It also doesn't need to (shouldn't) be nested according to the containers in the spec. It should be left as a flat dictionary, and the base class will handle packing the data into the containers.

2.7. `date`, `loaded_in_seconds` and `status` don't need to be implemented nor added in the `DATA_TYPES` structure, they will be handled by the base class.

`url` is also handled in the base class and can be left unimplemented.

If you add any of these to `DATA_TYPES`/`DATA_TYPES_SPECIAL` though, please don't return `None`, because it will overwrite the implementation from the base class.

2.8. Return `image_count` `0` if the image on the site was a picture with "no image" text on it.

Before restructuring, there was a field called `no_image` that indicated whether product image was an actual image or a placeholder stating that there's no image available.

Now the `no_image` field is not returned anymore, but if a "no image" picture is found, this info should be used to set `image_count` to `0`.

For this, the `no_image` function in the base scraper class (in `extract_data.py`) can be used (called with the appropriate image url parameter)

#### 3. New fields

If new fields need to be implemented, the procedure remains the same of adding them to `DATA_TYPES`/`DATA_TYPES_SPECIAL`.

From now on they should also be added to `BASE_DATA_TYPES_LIST` in the base class. (`extract_data.py`). If you do the merge yourself, you should add any new data type here as well or it will be ignored.

For an example of a revised scraper you can see the walmart scraper for which this was already implemented. (`special_crawler/extract_walmart_data.py`)

Git workflow
-----------------

https://bitbucket.org/dfeinleib/tmtext/wiki/Git%20workflow