# Specification #

Given a list of URLs from Site A, get a list back of corresponding URLs from Site B.

Example:
````
Staples: http://www.staples.com/Naxa-320-x-240-NT-301-3-1-2-inch-Digital-LCD/product_137679
Amazon: http://www.amazon.com/Naxa-NT-301-3-5-Inch-Digital-Television/dp/B003IKGMVK
````
For some reason we don't have this in the Amazon Televisions list, but if we had the ability to find corresponding TVs from, e.g. Staples on the other sites, that would be sufficient.

In this way, longer term, for a given category, we could take all the TV lists for each site and make sure we have as comprehensive a list of all TVs as possible from all the sites.

But for now I just need this for Staples and Amazon. Idea would be to supply as input staples_televisions_urls and get as output a list of corresponding amazon URLs

It should support 2 forms of output:
a) Just the Site B URLs that match the Site A URLs (more urgent) -- if no match is found, just exclude it
b) The URL from Site A, followed by matching URL from Site B, one per line: SiteA_URL,SiteB_URL -- if no match is found, second item is blank, e.g.:

```
"http://www.staples.com/Naxa-320-x-240-NT-301-3-1-2-inch-Digital-LCD/product_137679","http://www.amazon.com/Naxa-NT-301-3-5-Inch-Digital-Television/dp/B003IKGMVK"


# Usage #

Go to the `search` directory, and run the spider using one of the following command formats:

    scrapy crawl <site> -a product_name="<name>" [-a output="<option(1/2/3)>"] [-a threshold=<value>] [-a outfile="<filename>"] [-a fast=0] [-s LOG_ENABLED=1]

    scrapy crawl <site> -a product_url="<url>" [-a output="<option(1/2/3)>"] [-a threshold=<value>] [-a outfile="<filename>"] [-a fast=0] [-s LOG_ENABLED=1]

    scrapy crawl <site> -a product_urls_file="<filename>" [-a output="<option(1/2/3)>"] [-a threshold=value] [-a outfile="<filename>"] [-a fast=0] [-s LOG_ENABLED=1]

* `site` - the target site to search on. e.g. "amazon", "ebay" etc; or "manufacturer" for searching on the manufacturer site (specific to each product in the list, will be extracted automatically)

* `product_name` - search by product name: a string representing the name of the product to search for.

* `product_url` - search by product URL: a URL of the page of the product to be searched on another site.

* `product_urls_file` - search for multiple products, provided as a file of product page URLs (each URL on one line, format similar to `sample_output/staples_televisions_urls.txt`)

* `output` - optional argument (1/2/3), sets the format of the output. 1 corresponds to a) in the specification, and 2 corresponds to b). Default is 1. 3 is extended output, including product name, model and confidence score

* `threshold` - optional argument (0-1), a float used as a parameter in filtering search results. The higher the threshold, the fewer results will be accepted as valid matches.

* `outfile` - optional argument: output file name. default name is "search_results.csv"

* `fast` - optional argument: set to 1 to run a faster version of the crawler (with risk of lower accuracy). Default is 1 (true) - fast option has good enough accuracy

Debug info is disabled by default, to include it you need to add `-s LOG_ENABLED=1` to the command.

**Examples**

`scrapy crawl amazon -a product_urls_file="../sample_output/walmart_televisions_urls.txt"

* Search for Walmart blenders on Bestbuy (output url of products even if no match was found, option 2):

    `scrapy crawl bestbuy -a product_urls_file="../sample_output/walmart_blenders.txt" -a output=2`

* Search for products in `../sample_output/staples_televisions_urls.txt` on Amazon, using output format 2 and a threshold parameter of 0.4 and debug info enabled:

    `scrapy crawl amazon -a product_urls_file="../sample_output/staples_televisions_urls.txt" -a output=2 -a threshold=0.4 -s LOG_ENABLED=1`

# Supported sites #

Currently search by product URL (or list of URLs) supports product URLs from 

* Walmart
* Staples
* Newegg
* Boots
* Ocado
* Tesco

* Amazon
* Maplin

Target sites that were tested:

* Amazon
* Bestbuy
* Target
* Boots
* Tesco
* Ocado

* Walmart
* amazon.co.uk
* currys.co.uk
* Ebay
* ebay.co.uk
* pcworld.co.uk

Other target sites (with incomplete support): Walmart, Bloomingdales, Wayfair, Overstock, ToysRUs, Ebay. To be implemented for: BJs, Sears, manufacturer site.


# Output #

The spider generates a files `search_results.csv` (or the name specified as an argument), in one of the 2 supported formats (which can be set with the `output` argument):

a) 
- option 1: Just the Site B URLs that match the Site A URLs (more urgent) -- if no match is found, just exclude it

b)

- option 2: The URL from Site A, followed by matching URL from Site B, one per line: SiteA_URL,SiteB_URL -- if no match is found, second item is blank

- option 3: Same as 2 but with match confidence score on last column: SiteA_URL,SiteB_URL,Confidence

- option 4: Same as 3 but with origin products represented by UPC instead of URL, and with product name:
Origin_UPC,Product_Name,SiteB_URL,Confidence

- option 5: Same as 3 but with product name as well on first column (as found on source site): Product_Name,SiteA_URL,SiteB_URL,Confidence 

# Dependencies #

The spider uses the scrapy framework and the following libraries:
 
* nltk
* opencv
* selenium

To install these, you can run:

    pip install --user nltk
    pip install --user selenium
    sudo apt-get install python-opencv

The program also uses the following resources from nltk, that you need to download to be able to run it:

* stopwords
* wordnet

To download them, you need nltk installed, then:

    python -m nltk.downloader wordnet
    python -m nltk.downloader stopwords
