Extracting URLs of all products on a given site in a given category.

# Preparation #
```
sudo easy_install Scrapy
sudo easy_install selenium
```

# Usage #

Enter the directory `Caturls`. Run the crawler giving as an argument the page with the list of products in a certain category on a site; with the following command:

    scrapy crawl producturls -a cat_page="<url>" [-a outfile="<filename>"]

* cat_page - URL of the category page to extract products from

* outfile - optional argument: name of the output file. default name is "product_urls.txt"

To enable debug messages, add option `-s LOG_ENABLED=1`

**Sites** for which this works (given the category pages are all similar on one site)

* Staples
* Bloomingdales
* Walmart
* Amazon
* Bestbuy
* Nordstrom
* Macy's
* Williams-Sonoma

**Examples** (for which it was tested):

* Staples Televisions

    `scrapy crawl producturls -a cat_page="http://www.staples.com/Televisions/cat_CL142471"`

* Bloomingdales Sneakers

    `scrapy crawl producturls -a cat_page="http://www1.bloomingdales.com/shop/shoes/sneakers?id=17400"`

* Walmart Televisions

    `scrapy crawl producturls -a cat_page="http://www.walmart.com/cp/televisions-video/1060825?povid=P1171-C1110.2784+1455.2776+1115.2956-L13"`

* Amazon Televisions

    `scrapy crawl producturls -a cat_page="http://www.amazon.com/Televisions-Video/b/ref=sa_menu_tv?ie=UTF8&node=1266092011"`

* Bestbuy Televisions

    `scrapy crawl producturls -a cat_page="http://www.bestbuy.com/site/Electronics/Televisions/pcmcat307800050023.c?id=pcmcat307800050023&abtest=tv_cat_page_redirect"`

* Nordstrom Sneakers

    `scrapy crawl producturls -a cat_page="http://shop.nordstrom.com/c/womens-sneakers?dept=8000001&origin=topnav"`

* Macy's Sneakers

    `scrapy crawl producturls -a cat_page="http://www1.macys.com/shop/shoes/sneakers?id=26499&edge=hybrid"`

* Macy's Blenders

    `scrapy crawl producturls -a cat_page="http://www1.macys.com/shop/kitchen/blenders?id=46710&edge=hybrid"`

* Macy's Coffee Makers

    `scrapy crawl producturls -a cat_page="http://www1.macys.com/shop/kitchen/coffee-makers?id=24733&edge=hybrid"`

* Macy's Mixers

    `scrapy crawl producturls -a cat_page="http://www1.macys.com/shop/kitchen/mixers-accessories?id=46705&edge=hybrid"`

* Williams-Sonoma Blenders

    `scrapy crawl producturls -a cat_page="http://www.williams-sonoma.com/products/cuisinart-soup-maker-blender-sbc-1000/?pkey=cblenders&"`

* Williams-Sonoma Coffee Makers

    `scrapy crawl producturls -a cat_page="http://www.williams-sonoma.com/shop/electrics/coffee-makers/?cm_type=gnav"`

* Williams-Sonoma Mixers

    `scrapy crawl producturls -a cat_page="http://www.williams-sonoma.com/shop/electrics/mixers-attachments/?cm_type=gnav"`

# Tools #

The spider uses:

* the [scrapy](http://scrapy.org/) framework for python; installation guide: http://doc.scrapy.org/en/latest/intro/install.html
* the [selenium](http://selenium-python.readthedocs.org/en/latest/) library for python; installation guide: http://selenium-python.readthedocs.org/en/latest/installation.html#downloading-python-bindings-for-selenium (no need for selenium server)

## Observations ##

For some sites (staples, bloomingdales), the crawler will need to open a browser window - when the crawler is run, a Firefox window will open and navigate through the needed pages until the crawling is complete.

# Output #

The crawler will generate a file called `product_urls.txt` (or with the name specified as an option) which will contain the products URLs, each on a separate line.

**Example** output fragment:

    http://www.amazon.com/Sceptre-Inc-E478BV-FMDU-47-Inch-LED-Lit/dp/B00ANJRWYU/ref=sr_1_4274?s=tv&ie=UTF8&qid=1376261207&sr=1-4274
    http://www.amazon.com/FrameTheTV-610395123736-Frame-Toshiba-40E200U/dp/B0083JD250/ref=sr_1_4275?s=tv&ie=UTF8&qid=1376261207&sr=1-4275
    http://www.amazon.com/Ocosmo-CE3270-31-5-Inch-LED-Lit-Glossy/dp/B00A7BGOTI/ref=sr_1_4276?s=tv&ie=UTF8&qid=1376261207&sr=1-4276
    http://www.amazon.com/FrameTheTV-610395123651-Frame-Toshiba-46SL412U/dp/B0083JD084/ref=sr_1_4277?s=tv&ie=UTF8&qid=1376261207&sr=1-4277