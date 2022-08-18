## Purpose ##

The validation mechanism is supposed to

- save the developer's time, [partially] replacing the manual spider testing,

- reduce the number of errors mislooked during the manual spider testing,

- help with automated tests

One of the requirements is to make as little changes to the `BaseProductsSpider` as possible.

## Development ##

The development is being made in the `products_ranking_validation` branch.

## Usage ##

#### Command line ####

Just add `-a validate=1` to the command line. Do not add any `-o` or `-s LOG_FILE` options. Additional spider arguments (starting with `-a`), such as ordering options etc., are allowed.

Example: `scrapy crawl costco_products -a searchterms_str="orange"  -a validate=1`

If you don't add `-a validate=1` then the spider should work as before - the validation mechanism will not be switched on and you'll be able to add any command-line option you want.

#### Spider code ####

There are some settings used to validate the output. They should be stored in a special class. Then you have to link to that class using the `settings` variable located in your spider's class. Also you should add the BaseValidator mixin as the parent class going _before_ the BaseProductsSpider class. So, if you have a `costco_products` spider, then you want to

1) create a new settings class called `CostcoValidatorSettings` or similar,

2) add `BaseValidator` **before** `BaseProductsSpider` to `CostcoProductsSpider` class:

```
class CostcoProductsSpider(BaseValidator, BaseProductsSpider):
...
```

3) add the `settings` member:
```
class CostcoProductsSpider(BaseValidator, BaseProductsSpider):
    settings = CostcoValidatorSettings
...
```

4) redefine `optional_fields`, `ignore_fields`, `ignore_log_errors`, and the other validation settings. Please have a look into `BaseValidatorSettings` class, there are helpful (I hope so) comments there.

These options will be different for every spider. Some spiders can't scrape, say, `model` field (and that's okay). Other spiders scrape `model` but don't always scrape `price`. Anyway, please add the field to `ignore_fields` only if it is never scraped; if it is scraped sometimes, then it should go to `optional_fields`.

5) define `test_requests` - put at least 2 requests that never return products (0 products found), and at least 8 requests that would return some products (specify the range; so if the site returns 71 product then you want a range equal to something like [40, 120]). That option is not used (yet) but it'll surely be soon.

6) [optionally] re-define the validation methods, if you have some exceptions to the rules. For example, if the website returns very long image URLs (say, 1000 chars), then you may want to re-define the `_validate_image_url` method right in your spider class. `description` field is checked by the `_validate_description` method; and so on. Look into `BaseValidator` class to see the complete list of methods. Remember: validation methods always receive `unicode`, not `str`.

## Output ##

Run the crawler then and check the last 20-50 lines. You should see something like

```
Found 52 products
VALIDATION RESULTS:
NO ISSUES FOUND
```

... if everthing is ok. If not ok - then you'll see the list of issues (field names and\or log-related issues, such as some exceptions, errors, duplicated requests etc.):

```
Found 52 products
VALIDATION RESULTS:
ISSUES FOUND!
[('description', ' | ROW: 11'), ('price', ' | ROW: 19')]
```

(the thing above means that there are empty `description` and `price` fields; the issue with the 1st one occured firstly at the row number 11, the issue with the 2nd one - at the row number 19).

### Low-level CSV output and logs ###

You may want to open the validation CSV output to see what's happening there. Take a look into the /tmp/ dir; for `costco_products` you'll want `/tmp/costco_products_output.csv` and `/tmp/costco_products_output.log` files.

Remember - the CSV field separator is the [Grave accent](http://en.wikipedia.org/wiki/Grave_accent) symbol. It's not commonly used. However, if it, then we might change it to any other thing.


## Example ##

Below is a copy-pasted part of the `costco_products` spider. Only new\changed code is displayed. The code is fully usable and working, except the field `test_requests` which is (yet) filled with temporary random data.

```
from product_ranking.validation import BaseValidator


class CostcoValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['model', 'brand', 'description', 'price']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'buyer_reviews'
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = False  # ... duplicated requests?
    ignore_log_filtered = False  # ... filtered requests?
    test_requests = {
        'abrakadabra': 0,  # should return 'no products' or just 0 products
        'nothing_found_123': 0,
        'iphone 9': [200, 800],  # spider should return from 200 to 800 products
        'a': [200, 800], 'b': [200, 800], 'c': [200, 800], 'd': [200, 800],
        'e': [200, 800], 'f': [200, 800], 'g': [200, 800],
    }


class CostcoProductsSpider(BaseValidator, BaseProductsSpider):
    name = "costco_products"
    allowed_domains = ["costco.com"]
    start_urls = []

    SEARCH_URL = "http://www.costco.com/CatalogSearch?pageSize=96" \
        "&catalogId=10701&langId=-1&storeId=10301" \
        "&currentPage=1&keyword={search_term}"

    settings = CostcoValidatorSettings

    def parse_product(self, response):
        ...
``` 