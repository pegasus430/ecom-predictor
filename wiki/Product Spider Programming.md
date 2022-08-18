*(All  development of new spiders must be done on dev branch, not `master`. For example `CON-XXXXFixTitleAmazon`, where XXXX is number of ticket from Jira. )*


# Overview #

This document contains guidelines and checklists to follow and perform when developing a product ranking spider.

# Requirements #

Install packages:

sudo apt-get install python-dev python-pip libxml2-dev libxslt1-dev zlib1g-dev libffi-dev libssl-dev

sudo apt-get install tesseract-ocr xvfb wget chromium-browser python-setuptools python-distutils-extra python-apt python-lxml python-requests

Create new virtualenv and install requirements from following files:

install aerospike package in virtualenv:

pip install aerospike --install-option="--lua-system-path=/opt/aerospike/lua"
You can use any folder - make sure you grant permissions on it first like sudo chmod 777 /path/to/folder

/tmtext/product-ranking/requirements.txt

/tmtext/nutrition_info_images/requirements.txt

/tmtext/workbench_matching/requirements.txt

/tmtext/deploy/requirements.txt

/tmtext/insights_api/requirements.txt

/tmtext/special_crawler/requirements.txt

/tmtext/web_runner/requirements.txt


depending on a spider you work on, you might need to install opencv 2, you may refer to docs or use one of the scripts from this repo: 
```
#!python

https://github.com/jayrambhia/Install-OpenCV
```

## Some Errors when install requirements ##
	
-pg_config executable not found error: 

If you are getting errors like the above when install requirements packages, then please run the following before install requirements..

sudo yum install postgresql postgresql-devel python-devel (CentOS)

sudo apt-get install postgresql postgresql-dev python-dev  (Ubuntu)



## Problems solving ##

If you are getting errors like `[<twisted.python.failure.Failure <class 'OpenSSL.SSL.Error'>>]` add in `settings_local.py`

```
from OpenSSL import SSL
from twisted.internet.ssl import ClientContextFactory
from twisted.internet._sslverify import ClientTLSOptions
from scrapy.core.downloader.contextfactory import ScrapyClientContextFactory

class CustomClientContextFactory(ScrapyClientContextFactory):
    def getContext(self, hostname=None, port=None):
        ctx = ClientContextFactory.getContext(self)
        ctx.set_options(SSL.OP_ALL)
        if hostname:
            ClientTLSOptions(hostname, ctx)
        return ctx

DOWNLOADER_CLIENTCONTEXTFACTORY = 'product_ranking.settings_local.CustomClientContextFactory'
```

# Code Convention #

Code must follow the standard [PEP8](http://legacy.python.org/dev/peps/pep-0008/) coding convention. Please remember that the maximum allowed line length is 79 symbols.

Code must use spaces exclusively for indentation.

Both this criterias can be easily configured in regular code editors so there's no need to waste time going over the code to review coding convention. Just configure the editor correctly once. (Addition: PyCharm IDE is recommended since it highlights all possible errors, warnings and even PEP8 issues by default; there is a free Community Edition available - Andrey).

# Code quality #

Don't forget to check the code for the standard issues: outer\inner scope names clash, dangerous conditions with chance of uninitialized variable etc. Use pylint or similar tool (PyCharm IDE does this automatically).

Don't forget to remove unnecessary or unused code, such as `__init__` override if you don't really need it.

Check for TODO and FIXME comments.

# Commits #

If you fix something, please describe in short what you have fixed. For example, if you fixed the `brand` field which hasn't been scraped, commit message should be something like `Fix: brand field not scraped` or similar, not just `Extra fixes`.

Separate commits logically - thus, if you fix something and reformat the file to comply with PEP8, make 2 separate commits - one for fix, another for PEP8.

# Dependencies #

The requirements.txt file lists dependencies.

Do not add new dependencies without consulting the tech lead.

# Imports #

Please remove any unused imports. Performance is important here; unused imports cause unnecessary RAM usage.

# Testing #

## Automated ##

Currently we do not have an automated testing framework for this group of spiders.

## Manual ##

The following cases are the minimum that must be tested before a spider can be considered tested.

These tests are not the ones performed during development, they must be performed when the code is considered ready and redone after changes (they can be performed concurrently in different terminals).

* First of all you need to see, what fields spider is collects and compare it with full list of fields (items.py). You need to open different products links, and look if there is a field that does not collect the spider, but are available in the full list of fields. Spider must scrape as much as possible fields.
* You can import results in CSV file and check, that there are no empty fields in the results.
* Open product link from results and compare data from result with data that you see on web-page.
* A search that matches 0 items: it should not fail or cause retries.
* A search limited by `quantity` for less than a page of results.
* A search limited by `quantity` for more than a page of results.
* For shelf spiders, `num_pages` limits number of pages to scrape.
* A search for the entire result set. This will find problems as a large number of products are processed. Redirect the output to a file and look for problems.
* Try several very different search terms. This depend on the site. Choose the search terms with single word as well as multiple words (to test if spaces work well): not only _orange_ but also _orange juice_. Choose search terms that return multiple pages to check how pagination works. Don't use too broad search terms (those that return too many products, say, more than thousand) - otherwise you may wait for too long until the scraper finishes.
* Check that the spider allows sorting items if the source website provides some mechanism to order search results by various params (relevance, price asc\desc, rating etc.). If this feature exists, re-run the spider and check the CSV output
at least twice, with the default ordering and with another one.
* Every time you find an error or suspicious thing, write it down somewhere immediately so you won't forget about it in the end.
* An example command to run the crawlers: `scrapy crawl amazonca_products -a searchterms_str="annie sloan"   -o /tmp/output.csv -s LOG_FILE=/tmp/output.log`
* Remember that Scrapy appends the output (not overwrites it), so don't forget to remove those 2 output files above: `rm /tmp/output.*`
* Scrape the biggest image available.
* Don't turn UPCs into int. Treat them as strings. The leading zero (which will be stipped) might be important. Don't also mix together UPCs and SKUs, these are 2 different things.
* Scrape descriptions with HTML tags.
* Do some more research if needed, and try to find out-of-stock products and products with discounts, and make sure is_out_of_stock is populated, and the price you scrape is the final price, not the price before discount.

Things to watch out for:

* Filtered (offsite, duplicated) requests.
* ERROR or WARNING log messages.
* Redirects (302). Sometimes these point to the site not liking the load or the way it is being traversed.
* An item count smaller than the `total_matches`. Some sites do this but sometimes it's a problem. Manually verify it once.
* Important fields missing. Some types of products will have slighlty or radically different pages, try to get information from reliable sources.

# Tips #

## CSV output ##

CSV output is more convenient for debugging purposes than JSON. However, the standard field separator - comma - may break the formatting since it's often used in titles or descriptions.

To avoid it, use vertical line (|) as the separator, or any other very uncommon symbol. For that, create *settings_local.py* file in the folder with the *settings.py* settings file. I've pushed a commit which forces Scrapy to override settings with your local_settings. The attached file changes the default CSV separator, so you won't have a messy file because of commas in titles\descriptions. The separator there is symbol |  (you may use OpenOffice or LibreOffice to check such a file, not sure if MS office supports custom separators).

settings_local.py content is below

```
from scrapy.contrib.exporter import CsvItemExporter


class MyProjectCsvItemExporter(CsvItemExporter):

    def __init__(self, *args, **kwargs):
        delimiter = '|'
        kwargs['delimiter'] = delimiter
        super(MyProjectCsvItemExporter, self).__init__(*args, **kwargs)


FEED_EXPORTERS = {
    'csv': 'product_ranking.settings.MyProjectCsvItemExporter',
}
```

(In Scrapy master there's an unreleased change to allow to specify the separator as a setting. Let's keep an eye on that. https://github.com/scrapy/scrapy/pull/279/files)

## Redundant Sources ##

When you find many sources for information (for example, Javascript, Open Graph and HTML), use them all. They will provide redundancy in case of a change that breaks one of them.

Use `cond_set` and `cond_set_value` and sort the sources from most to least reliable.

Don't make additional requests to get a redundant source. Requests are very expensive.

## Finding data in the page ##

### HTML ###

In a given product page, open the source and search for the value. Don't be satisfied with the first match, a juicy JSON block might be waiting further ahead.

Regarding tools:

* Firefox has [Firebug](http://getfirebug.com/). This is the recommended thing since it's quite advanced and powerful. For example, it discriminates XHR requests (AJAX). [A comparison with the standard inspector](http://stackoverflow.com/questions/18862874/firefox-firebug-vs-inspect-element). There is also an excellent FirePath extension available; useful for testing XPaths or CSS paths.

* Firefox has a [Page Inspector](https://developer.mozilla.org/en-US/docs/Tools/Page_Inspector) which shows HTML, network activity and more.

* Chrome has the [Web Inspector](https://chrome.google.com/webstore/detail/web-inspector/enibedkmbpadhfofcgjcphipflcbpelf) which is similar to the other two.

When using this tools to get an [XPath](http://www.w3schools.com/xpath/), try not to use the entire expression but an Id or Class to make the rule more resilient.

### AJAX ###

Use Firebug or similar to catch AJAX (aka XHR) requests and check them out. Sometimes they give away useful services.

### Javascript imports ###

Sometimes instead of an AJAX request, a normal looking Javascript file will contain dynamic data.

This are harder to catch because they are mixed with other static files.


## Semantic Web ##

Look for standard semantic web vocabularies like [Open Graph](http://ogp.me/) or [Schema.org](schema.org).

There is a standard function that will populate a product from [Open Graph](http://ogp.me/) metadata: product_ranking.spiders.populate_from_open_graph

A function for [Schema.org](schema.org) is upcoming.

## JSON ##

Try to find blocks of JSON with the product data. This is easy to parse and, usually, more stable.

Try to catch AJAX requests as they sometimes contain redundant JSON data which will be easier to parse.

Wrap json.loads code into try-except block.

## Javascript blocks (that are not proper JSON) ##

Javascript allows to define data structures that are not valid JSON.

There's no way to parse this with the standard library `json` module.

Sometime it's possible to fix the data structure easily:

```
keys = ((k, "'%s':" % k[:-1].strip()) for m in re.finditer(r'[[{,](\s*\w+\s*:)', text) for k in m.groups())
json_text = reduce(lambda t, (old, new): t.replace(old, new), keys, text)  
```

Another possible solution, might be to parse the invalid jason structure with YAML, that one should work (at least for the quotes issues)


XXX Complete.

## Monitoring ##

There are some graphs to monitor spider's performance. These graps are located at http://54.174.165.160 (TODO: add login/password?). One of the most important params is the time a spider takes to complete the task. It's called `working time` and measured in seconds. If any spider becomes too slow or too fast, then it means there are issues with the spider itself or with the server(s).

# Crawlera #

[Documentation](https://doc.scrapinghub.com/crawlera.html)

Note important documentation about passing user agents / headers: X-Crawlera-UA