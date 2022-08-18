[TOC]

## Overview ##

This project consists of crawlers and post-processing scripts.

The product crawler is a collection of spiders that scrape products from listing sites.

If you are a developer, please read [the development guidelines](Product Spider Programming) for these project.

The objective of this project is to extend the product item so that a single collection of spiders has all the know-how on how to fetch product information for all sites.


Currently, there are the following spiders (keep sorted alphabetically):

* 10dollarmall_products: 10dollarmall.com
* amazon_products: amazon.com
* amazonfresh_products: amazonfresh.com
* argos_uk_products: argos.co.uk
* asda_products: asda.com
* babysecurity_products: babysecurity.co.uk
* bedbathandbeyond_products: bedbathandbeyond.com
* bestbuy_products: bestbuy.com
* bhinneka_products: bhinneka.com
* bigbasket_products: bigbasket.com
* biglots_products: biglots.com
* bitikla_products: bitikla.com
* boohoo_products: boohoo.com
* bol_products: bol.com
* bonton_products: bonton.com
* boots_products: boots.com
* boscovs_products: boscovs.com
* bradfordexchange_products: bradfordexchange.com
* carrefoures_products: carrefour.es
* canadiantire_products: camadiantire.ca
* costco_products: costco.com
* currys_uk_products: currys.co.uk
* cvs_products: cvs.com
* debshops_products: debshops.com
* dollartree_products: dollartree.com
* drugstore_products: drugstore.com
* ebay_uk_products: ebay.co.uk
* eddiebauer_products: eddiebauer.com
* famousfootwear_products: famousfootwear.com
* famousfootwearau_products: famousfootwear.com.au
* fatbraintoys_products: fatbraintoys.com
* forever21_products: forever21.com
* freshdirect_products: freshdirect.com
* gap_products: gap.com
* gizoouk_products: gizoo.co.uk
* hammacher_products: hammacher.com
* harrietcarter_products: harrietcarter.com
* hawkin_products: hawkin.com
* hm_products: hm.com
* hollisterco_products: hollisterco.com
* homedepot_products: homedepot.com
* iherb_products: iherb.com
* iwoot_products: iwoot.com
* jcpenney_products: jcpenney.com
* jcpenney_checkout_products: jcpenney.com
* jcrew_products: jcrew.com
* jimshore_products: jimshore.com
* johnlewis_products: johnlewis.com
* kruidvat_products: kruidvat.nl
* lazada_products: lazada.com.ph
* lladro_products: lladro.com
* lillianvernon_products: lillianvernon.com
* londondrugs_products: londondrugs.com
* luckyvitamin_products: luckyvitamin.com
* macys_products: macys.com
* mihaelkors_products: michaelkors.com
* modcloth_products: modcloth.com
* morrisons_products: morrisons.com
* musiciansfriend_products: musiciansfriend.com
* mothercare_products: mothercare.com
* ocado_products: ocado.com
* oldnavy_products: oldnavy.com
* orientaltrading_products: orientaltrading.com
* riverisland_products: riverisland.com
* papayaclothing_products: papayaclothing.com
* payless_products: payless.com
* pgestore_products: pgestore.com
* pcworldcouk_products: pcworld.co.uk
* proswimwear_co_uk_products: proswimwear.co.uk
* sainsburys_uk_products: sainsburys.co.uk
* sallybeauty_products: sallybeauty.com
* samsclub_products: samsclub.com
* screwfix_products: screwfix.com
* souq_products: souq.com
* shoezen_products: shoezen.com
* shophq_products: shophq.com
* shoporganic_products: shoporganic.com
* spiegel_products: spiegel.com
* staples_products: staples.com
* staplesadvantage_products: staplesadvantage.com
* swansonvitamins_products: swansonvitamins.com
* target_products: target.com
* tesco_products: tesco.com
* victoriassecret_products: victoriassecret.com
* vitacost_products: vitacost.com
* vitadepot_products: vitadepot.com
* walgreens_products: walgreens.com
* walmart_products: Walmart.com
* well_products: well.ca
* wetseal_products: wetseal.com
* wowhd_products: wowhd.us
* yankeecandle_products: yankeecandle.com
*zappos_products: zappos.com
*zavvi_products: zavvi.com

All spiders accept the following parameters:

* searchterms_str: The search term. (mandatory)
* quantity: The number of products to return. If not provided, it will return all matches.


The product item in these spiders has the following fields:

*    site: The site the item was taken from.
*    search_term: The search term used to get the product.
*    results_per_page: The number of results in the first page.
*    ranking: The place of the product in the list of results.
*    total_matches: The total number of matches in the result.
*    title: The title of the product in the site.
*    upc: The [Universal Product Code](http://en.wikipedia.org/wiki/Universal_Product_Code) of the product.
*    url: The URL of the product for the site.
*    image_url: The URL of an image for the product.
*    description: A description of the product.
*    brand: The brand of the product.
*    price: The price of the product as text, optionally with currency sign.
*    locale: The locale of the scraped values (currency, language, etc).
*    is_out_of_stock: The product is out of stock.
*    is_in_store_only: The product is available in store only.
*    search_term_in_title_exactly: The search term is in the product name exactly as searched.
*    search_term_in_title_interleaved: All the words of the search term appear in the title although they may have other words interleaved search_term_in_title_exactly is False.
*    search_term_in_title_partial: All the words of the search term are in the title in any order and the other two search_term_in_title_* fields are False.
*    related_products: Dict of relations to other products. The structure is as follows:

    ```
    {"relation name": [ ("product title", "product url"), ... ], "other relation": [...], ...}
    ```

    Existing `related_products` keys are:  

    * buyers_also_bought: Products also purchased by buyers of the current product.
    * recommended: Products recommended by the store.

## Testing the spiders ##

Auto-tests are described here: https://bitbucket.org/dfeinleib/tmtext/wiki/Auto-tests%20for%20ranking%20spiders.

Manual testing: [tips & tricks](https://bitbucket.org/dfeinleib/tmtext/wiki/Product%20Spider%20Programming), section `Testing`.

## Server space cleanup ##

In case of emergency, you can clean up the spiders' logs and free some extra HDD space (sometimes up to 30G). Please use it only when the situation is critical; the logs are useful and are used for debugging purposes.

```
find /home/web_runner/virtual-environments/scrapyd/logs/product_ranking/  -type f -name "*.log" -delete
```

## Site Specific Comments (keep sorted alphabetically) ##

### 10dollarmall.com ###

Spider takes `search_sort` argument with following possible sort modes:

* `rating`: average product rating, descending
* `new_arrivals`:  new arrivals, descending
* `best_sellers`: best seller products, descending
* `price_asc`: price, ascending
* `price_desc`: price, descending
* `name_asc`: title, ascending
* `name_desc`: title, descending
* `discount_amount`: discount amount, desc
* `brand_name`: brand name, ascending
* `average_review`: Average reviews
* `default`: relevance

If no `search_sort` value is given, relevance is used.

There are following caveats:

* `model`, `upc`, `related_products`, `is_in_store_only` were not retrieved.

### ah.nl ###

The spider has an extra param `order` which can be *relevance* or *name* - this parameter allows to sort the data.

Not scraped fields:

* related_products
* is_out_of_stock
* upc
* is_in_store_only
* model

A thing to note. `results_per_page` param may be less than the actual pagination result. That means, there might be, say, 58  items at the first page, but all the next pages return 60.

### amazon.com ###

This spider has an additional parameter, captcha_retries, with a default value of 10 which specifies the number of time to try to break a captcha.

There are the following caveats:

* Captcha solving was not tested as I could not get Amazon to challenge the spider.
* CaptchaBreaker requires numpy. If it is not present, the spider will still work but will never solve captchas. A message is printed to warn about this.
* Amazon only provides 20 pages of results so not all declared matches are accessible (max, 16x20=320). Usually, only 306 results are provided, for some reason. I manually checked this.
* The number of total matches changes as you navigate over the result pages so the value from the first page is used.
* The number of total matches is looked for in 2 places but it sometimes doesn't appear in either. An error is then logged.
* The `UPC` is taken from almost free form text so it's not super reliable. Also, some products have several and only the first one is retrieved.
* The `description` is sometimes empty or missing.
* The `title` is not parsed correctly for games.
* `related_products` is not implemented.

### amazonfresh.com ###

This spider has an additional parameter `location` which indicates location (market place) of the products on amazonfresh.com. Currently, amazonfresh.com has three locations: Southern California, Northern California, Seattle Area and the `location` parameter takes correlative values: southern_cali, northern_cali, seattle. Default value is "southern_cali". New locations can be added by adding its names and its market place IDs to AMAZONFRESH_LOCATION parameter in product_ranking/settings.py.

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is ASIN code
* The `description` is sometimes empty or missing.
* `related_products` is not implemented.

### argos_uk_products ###

There is an additional boolean parameter: fetch_related_products. The spider won't scrape `related_products` if this set to False, reducing the number of requests, thus speeding the overall process up.

Known problems:

* Some items might not be scraped because of a server-side error. (Like this one: http://www.argos.co.uk/static/Search/fs/0/p/51/pp/50/q/car/s/Relevance.htm)
* `model` and `UPC` fields are not retrieved.

### asda.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is not implemented.

### auchandirect.fr ###

The following fields are not scraped (no information provided):

* related_products
* is_in_store_only
* upc
* model

Other issues:

* `results_per_page` might be invalid (for some reasons it's 2 times more than the number of results)
* the site allows some search ordering to be performed but I did not implement it since the ordering is performed by POST requests and the result data is in JSON so it would take much more time to parse it, the same as the amount of time spent for writing a new crawler)

### babysecurity.co.uk ###

Spider takes `search_sort`  and `direction` argument with following modes:

`search_sort`:

* `best_sellers`: best seller products
* `price`: sort by price
* `name`: sort by name
* `recommended`: sort by position

If no `search_sort` value is given, `best_sellers` is used.

`direction`:

* `asc`: sort ascending
* `desc`: sort descending

If no `direction` value is given, `asc` is used

There are following caveats:

* `upc`, `model`, and `is_in_store_only` fields are not retreived.

### bedbathandbeyond.com ###

Sort modes defined (use -a sort_mode): relevance(default), price_asc, price_desc, rating, brand, new, best_sellers

`brand` and `model` fields are missing.

### bestbuy.com ###

There are the following caveats:

* The `description` is sometimes empty or missing.
* `related_products` is not implemented.

### bhinneka.com ###

Spider takes additional "order" argument. Availible sort orders are: relevance (default), brand, brand_desc, price_asc, price_desc, rating, rating_desc.

Following fields are not scraped: UPC, is_out_of_stock, is_in_store_only, related_products.
Sometimes a product might be scraped several times, and all duplicates will get filtered. This is a website issue. 

### bigbasket.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

Sample usage: `scrapy crawl bigbasket_products -a searchterms_str="tea" -a quantity=1 -s USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120 Safari/537.36" `

### biglots.com ###

`UPC`, `model`, and `brand` fields are not scraped.

### bitikla.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is not implemented.

### boohoo.com ###

Spider takes `order` and `direction` parameter. Availible sort modes (`order`) are:

* `relevance` (default)
* `best`
* `new`
* `price`.

`direction` parameter can take `asc` or `desc` (default) values, indicating ascending or descending sorting order, respectively.

`currency` parameter can be used to change currency, `GBP` is default.

Following fields are not scraped:

* `buyer_reviews`, `is_out_of_stock`, `upc`, `is_in_store_only`, `model`, `brand`.

### bol.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.

### bonton.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevance
    * bestsellers
    * newarrivals
    * rating
    * pricelh
    * pricehl
    * az
    * za

### boots.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is implemented.
This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * bestmatch
    * pricelh
    * pricehl
    * azbybrand
    * zabybrand
    * bestsellers
    * toprated
    * newest
    * onpromotion

### boscovs.com ###

There are the following caveats:
* `related_products` is not implemented.
This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * default
    * pricehl
    * pricelh
    * newestfirst
    * topsellers
    * toprated
 
### canadiantire.ca ###

There are the following caveats:

* The `UPC` may not be correct.

### bradfordexchange.com ###

Following fields are not scraped: `buyer_reviews`, `is_in_store_only`, `model`

### carrefour.es ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is implemented.

### carrefour.fr ###

Not scraped:

* upc
* is_in_store_only
* model

Other issues:

* brand is not scraped sometimes
* when checking the website in browser, sometimes you'll see a blank page - make sure the *body* tag is located properly (due to some JS issues, it's often moved to 1000% to the left which is obviously out of screen)

Related products feature is implemented.

### costco.com ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is sometimes empty or missing.
* The `description` is sometimes empty or missing.
* `related_products` is not implemented.
* The `price` is sometimes not available

### crs-online.ca ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is  not retrieved.
* The `brand` is  not retrieved.

Spider can often stop because of losing connection.

### currys.co.uk ###

Spider takes `order` argument with possible sorting modes:

* `relevance` (default)
* `brand_asc`, `brand_desc`
* `price_asc`, `price_desc`
* `rating`

Following fields are not scraped:

* `model`, `upc`, `related_products`, `buyer_reviews`

### cvs.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is not implemented.

### debshops.com ###

Following fields are not scraped:

* `model`, `buyer_reviews`, `is_in_store_only`

### dollartree.com ###

The spider takes an additional `order` argument: relevance (default), availible, rating, name_asc, name_desc, new, limited.

Known problems:

* Sometimes there is no description availible.
* `brand` not scraped.

### drugstore.com ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is not retrieved.
* The `Brand` is guessed from the product title on the search result page. Usually it is the first bold phrase   in the pruduct title, but it is right not for all products. So `Brand` is not allways guessed correct.
* `related_products` is not implemented.

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * best_match' (default)
    * best_sellers
    * new_to_store
    * a-z
    * z-a
    * customer_rating
    * price_low
    * price_high
    * saving_dollars
    * saving_percent

### flipkart.com ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is not retrieved.
* The `Brand` is not retrieved
* `related_products` is implemented. Makes 4 additional request for 'buyers_also_bought' and 'recommended' related products

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * best_match' (default)
    * best_sellers
    * price_asc
    * price_desc

### ebay.co.uk ###

Spider takes `order` argument with possible sort modes:

* `relevance`
* `old`, `new`
* `price_pp_asc`, `price_pp_desc`
* `price_asc`, `price_desc`
* `condition_new`, `condition_used`
* `distance_asc`

Following fields are not scraped:

*  `is_out_of_stock`, `is_in_store_only`, `upc`, `buyer_reviews

### eddiebauer.com ###

Takes `order` argument with following possible values:

* `relevance` (default)
* `recommend` - recommended items first
* `new` - new items first
* `price_asc`, `price_desc` - sort by price (alphabetical/reversed)
* `rating` - average reviewers rating

There are the following caveats:

* `umc`, `model`, `is_in_store_only` are not scraped
* ordering by price doesn't take sales price in an account, that is the website issue

### famousfootwear.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is not implemented.
* `sort_mode`: Changes the order of the results. Its values can be:
    * bestmatch -default sorting
    * arrival
    * rated
    * brand
    * style
    * percent
    * pricelh
    * pricehl
    * topsellers

### famousfootwear.com.au ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

### fatbraintoys.com ###

Takes `order` argument. Allowed sort modes are: `rating` (default),
`sales`, `price_asc`, `price_desc`.

`is_of_stock` and `is_in_store_only` fields are not scraped.

### forever21.com ###

Takes additional `locale` argument, defaults to `en-US`.

`is_in_store_only`, `brand`, `is_out_of_stock`, `model`, and
`related_products` fields are not scraped.

### freshdirect.com ###

There are the following caveats:

* The `UPC` is not retrieved.

### gap.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

### geantonlines.ae ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is not retrieved.
* The `Brand` is not retrieved.
* `related_products` is implemented (only 'buyers_also_bought')

### gizoo.co.uk ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is implemented.

### www.google.com/shopping ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is not retrieved.
* The `total_matches` is not retrieved.
* The `brand` is not allways presented.

Almast all fields can be retrieved from search page ( except `related_products`, and full `description`; breaf `description` is presented on the search page). Google can block the crawler if it does too many and frequent requests. So that we can retrieve info only from search page to reduce total number of requests ( now spider visit detail page also).  

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * default
    * low_price
    * high_price
    * rating

### hammacher.com ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevancy
    * pricelh
    * pricehl
    * nameaz
    * nameza

### iherb.com ###

There are the following caveats:

* `related_products` is implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevance
    * bestrating
    * bestselling
    * highestprice
    * lowestprice
    * onsale
    * heaviesttolightest
    * lightesttoheaviest

### iwoot.com ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is implemented.

### jcpenney.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.
* The `model` contains model name.

* `sort_mode`: Changes the order of the results. Its values can be:
    * bestmatch
    * newarrivals
    * bestsellers
    * pricelowhigh
    * pricehighlow
    * ratinghighlow

### jcpenney.com with checkout process ###

This spider is special and works in a different way than the rest.

Spider takes this obligatory option:

* `product_data` : Json list with all the information about the products to be searches, dumped as text. Each element of the list is a dict with this fields:
     * url : string  -> url of the product
     * FetchAllColors : true or false : optional : default is false -> Create a basket for each available color of the product. 
     * color: string or array of strings: optional -> select only this color variant, if not selected then it gets the first available color

Example:


```
#!json

[
  {
    "url": "http://www.jcpenney.com/bisou-bisou-elbow-sleeve-sweetheart-neck-bodycon-dress/prod.jump?ppId=pp5006310969&catId=cat100210008&deptId=dept20000013&&_dyncharset=UTF-8",
    "FetchAllColors": true
  },
  {
    "url": "http://www.jcpenney.com/st-johns-bay-legacy-pique-polo-shirt/prod.jump?ppId=pp5002260106&catId=cat100240025&deptId=dept20000014&&_dyncharset=UTF-8",
    "color": "Navy"
  }
]
```


Also, Spider takes this optional options:

* `driver` : The driver name for Selenium.
* `proxy` : IP Address of a proxy server to be used. E.g. 192.168.1.42:8080
* `proxy_type` : Proxy type. http|socks5
* 'quantity' : List of integer separated by comas values

It returns to kind of Items:

* `CheckoutProductItem`, with the values:
    * name
    * id
    * color
    * price
    * quantity
    * order_subtotal
    * order_total

### jcrew.com ###

Spider takes `search_sort` argument with following possible sort modes:

* `price_asc`: price, ascending
* `price_desc`: price, descending
* `default`: relevance

If no `search_sort` value is given, relevance is used.

There are following caveats:

* `upc`, `is_out_of_stock`, `model`, `related_products` and `is_in_store_only` fields were not retrieved.

### jimshore.com ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is not implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevance
    * name
    * price
    * releasedate

### johnlewis.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is implemented.
* The `model` contains color:size pair.

* `sort_mode`: Changes the order of the results. Its values can be:
    * default
    * priceHigh
    * priceLow
    * AZ
    * ZA
    * New
    * popularity
    * rating

### harrietcarter.com ###

Spider takes `order` argument with following possible values:

* `best` (default), `price_asc`, `price_desc`, `rating`

Following fields are not scraped:

* `brand`, `model`, `buyer_reviews`, `is_in_store_only

USER-AGENT must be set.

### hawkin.com ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is not implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * popularity
    * price
    * pricerev
    * title
    * titlerev

### hm.com

Spider takes `order` argument with following possible values:

* `relevance` (default)
* `new`
* `price_asc`
* `price_desc`

Following fields are not scraped: `brand`, `is_out_of_stock`, `is_in_store_only`, 'upc'.

### hollisterco.com ###

`order` option availible with following possible values: relevance (default), price_asc, price_desc, new

`brand`, `model`, `upc` and `related_products` are not scraped. 

### homedepot.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is implemented.

### kruidvat.nl ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

### lazada.com.ph ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is not implemented.
This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * relevance (default)
    * pricehigh
    * pricelow
    * rating

### lillianvernon.com ###

Spider takes `search_sort` argument with following possible sort modes:

* `new_arrivals`:  new arrivals, descending
* `best_sellers`: best seller products, descending
* `price_asc`: price, ascending
* `price_desc`: price, descending
* `name_asc`: title, ascending
* `name_desc`: title, descending
* `our_picks`: our picks

If no `search_sort` value is given, `best_sellers` is used.

There are following caveats:

* `brand` is set to "Lillian Vernon"
* `model`, `upc`, `related_products`, `is_in_store_only` were not retrieved.

### lladro.com ###

There are the following caveats:

* `related_products` is implemented.

### londondrugs.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is implemented.
This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * default : Default sorting
    * az : Name  A-Z
    * za : Name Z-A  
    * pricelh : Price Low to High
    * pricehl : Price High to Low
    * brandaz : Brand A-Z 
    * brandza : Brand Z-A
    * bestsellers

### luckyvitamin.com ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevance
    * nameaz
    * nameza
    * highestrating

### macys.com ###

Additional options:

* order - featured, price_asc (default), price_desc, rating, best_sellers, new
* related_products - disabled by default. Is enabled, related_products will be scraped.

Known issues:

* for each item in related_products, an additional request has to be made. 


### Macys.com with checkout process ###

This spider is special and works in a different way than the rest.

Spider takes this obligatory option:

* `product_urls` : List of product urls joined by the simbol "||||"

Also, Spider takes this optional options:

* `driver` : The driver name for Selenium.
* `proxy` : IP Address of a proxy server to be used. E.g. 192.168.1.42:8080
* `proxy_type` : Proxy type. http|socks5

It returns to kind of Items:

* `CheckoutProductItem`, with the values:

    * name
    * id
    * price

* `CheckoutDiscountItem`, with the values:

    * order_subtotal
    * order_total



### michaelkors.com ###

Spider takes `order` argument with following possible values:

* `relevance` (default), `price_asc`, `price_desc`

Following fields are not scraped:

* `is_out_of_stock`, `is_in_store_only`, `buyer_reviews`, `upc`

### modcloth.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

### morrisons.com ###

There are the following caveats:

* `related_products` is implemented.

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * best_match' (default)
    * product_name_ascending
    * product_name_descending
    * high_price
    * low_price
    * best_sellers
    * shortest_shelf_life(ascending order of expiration)

### musiciansfriend.com ###

Takes `order` argument with following possible values:

* `best` - best sellers first
* `relevance`(default)
* `rating` - average user rating
* `saving` - greater discounts first
* `price_desc` - product price, descending
* `price_asc` - product price, ascending
* `new`
* `brand`

It also takes two additional arguments:

* `country` - country code (i.e. US, FR, etc)
* `currency` - currency code (i.e. USD, EUR, etc)

There are following caveats:

* `model`, `upc`, `is_out_of_stock`, `is_in_store_only` are not scraped.
* Not all of `related_products` are scraped (mostly "Similar Products").

### mothercare.com ###

`upc` field is missing

Takes `order` argument with following possible values:

* `rating` (default)
* `best`
* `new`
* `price_asc`, `price_desc`

### ocado.com ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is not retrieved.
* `related_products` is not implemented.

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * default (this is the default)
    * price_asc
    * price_desc
    * name_asc
    * name_desc
    * shelf_life
    * customer_rating

### oldnavy.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

### ooshop.com ###

Not scraped:

* related_products
* is_out_of_stock
* upc
* is_in_store_only

Other issues:

* `brand` might be incorrect and sometimes does not exist
* `model` might be incorrect and sometimes does not exist
* search ordering not implemented (complicated cookies mechanism)
* sometimes, if there are more than ~22 products returned, the remaining are not displayed. Scraping them would require lots of time to be spent because there are forms, POST request with tons of arguments, cookies etc. Not sure if I need to proceed with this website.

### ozon.ru ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is not allways presented.

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * default
    * price
    * best_sellers
    * new
    * rate
    * year

### orientaltrading.com ###

Takes `order` argument with following possible sort ordering values:

* `relevance` (default)
* `best` - best sellers
* `rating` - average review rating
* `new` - new arrivals first
* `price_asc`, `price_desc` - price (alphabetical/reversed)

Following fields are not scraped:

* `is_out_of_stock`, `is_in_store_only`, `upc`

### papayaclothing.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

### payless.com ###

Spider takes `order` argument. Avalible sort modes are:
`relevance` (default), `price_asc`, `price_desc`, `best`, `rating`.

Following fields are not scraped: `is_out_of_stock`, `is_in_store_only`,  `model`, `related_products`.

### pcworld.co.uk ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevance
    * brandaz
    * brandza
    * pricelh
    * pricehl
    * rating

### pgestore.com ###

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * best_match (this is the default)
    * high_price
    * low_price
    * best_sellers
    * newest
    * rating

Sample usage: `scrapy crawl pgestore_products -a searchterms_str="hair and beauty" -a search_sort=best_sellers`

There are the following caveats:

* The `description` is sometimes empty or missing.

### riteaid.com ###

Extra arguments:

* `order`: can be _top_selling, price_asc, price_desc, most_popular_. _top_selling_ is default.
* `items_per_page`: can be _12, 24, 36, 48_. _12_ is default.

Not scrapped (the site does not provide them):

* `related_products`
* `upc`
* `is_in_store_only`
* `model`

### riverisland.com ###

There are the following caveats:

* `related_products` is implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevance
    * latest
    * oldest
    * pricelh
    * pricehl

### proswimwear.co.uk ###

Spider takes `order` argument

Allowed sorting modes are:

* `relevance` (default)
* `price`
* `name`

### sainsburys.co.uk ###

Spider takes `order` argument.

Allowed sorting orders are:

* `relevance`: relevance. This is default.
* `price_asc`: price per unit (ascending).
* `price_desc`: price per unit (descending).
* `name_asc`: product title (ascending).
* `name_desc`: product title (descending).
* `best`: best sellers first.
* `rating`: average user rating (descending).

There are following caveats:

* if price per unit is not found, the spider will try other pricing variants.
* `brand` might not be scraped for some products, or scraped incorrectly, but this is very unlikely.
* `model`, `is_out_of_stock`, `is_in_store_only` and `upc` fields are not scraped

### sallybeauty.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

* `sort_mode`: Changes the order of the results. Its values can be:
    * 'empty' -default sorting
    * bestsellers
    * rating
    * pricelh
    * pricehl

### samsclub.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is not implemented.

This spider has the additional options:

* `clubno`: Changes current samsclub club-no like '4703'.

### screwfix.com ###

There are the following caveats:

* `related_products` is implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevant
    * pricehl
    * pricelh
    * brandaz
    * brandza
    * averagestar

### soap.com ###

There are the following caveats:

* The `description` is sometimes incomplete.
* `related_products` is not implemented.

### souq.com ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is implemented.

* `sort_mode`: Changes the order of the results. Its values can be:
    * 'empty' -default sorting
    * bestmatch
    * popularity
    * pricelh
    * pricehl

### shoezen.com ###

Takes `order` argument with following possible values:

* `new` (default) - newer products first
* `old` - older products first
* `price_asc` - sort by price, ascending
* `prise_desc` - sort by price, descending
* `name_asc` - sort by name in alphabetical order
* `name_desc` - sort by name in reversed alphabetical order
* `best` - best sellers first
* `brand` - sort by brand in alphabetical order
* `availability`

Following fields are not scraped:

* `upc`, `model`, `is_in_store_only`, `buyer_reviews`.

### shophq.com ###

Takes `order` argument with following possible sorting orders:

* `relevance` (default)
* `price_asc`, `price_desc`
* `new`
* `rating`
* `best`

Following fields are not scraped:

* `is_out_of_stock`, `is_in_store_only`, `upc`

### shoporganic.com ###

Spider takes `order` argument with following possible values:

* `relevance` (default)
* `price_asc` - price, low to hight
* `price_desc` - price, hight to low
* `sku`
* `name` - product title in alphabetical order

Following fields are not scraped:

* `is_out_of_stock`, `is_in_store_only`, `model`

### spiegel.com ###

Takes `order` argument with following possible sort ordering values:

* `best` (default), `price_asc`, `price_desc`

Following fields are not scraped:

* `upc`, `is_in_store_only`, `is_out_of_stock`, `related_products`, `buyer_reviews`

### staples.com ###

Spider takes `order` argument with following possible sorting modes:

* `relevance` (default)
* `price_asc`, `price_desc`
* `name_asc`, `name_desc`
* `rating`
* `new`

Following fields are not scraped:

* `is_out_of_stock`.

### staplesadvantage.com ###

Takes `order` argument with following possible values:

* `relevance` (default)
* `rating` - user rating from low to high
* `best` - best sellers

Following fields are not scraped:

* `price`, `is_out_of_stock`, `is_in_store_only`, `upc`

### swansonvitamins.com ###

Spider takes `search_sort` argument with following possible sort modes:

* `brand_name`:  brand name, ascending
* `price_asc`: price, ascending
* `price_desc`: price, descending
* `product_name`: title, ascending
* `rating`: product rating, asc
* `on_sale_now`: sale off products, desc
* `default`: relevance

If no `search_sort` value is given, relevance is used.

There are following caveats:

* `model`, `upc`, `related_products`, `is_in_store_only` and `is_out_of_stock` were not retrieved.

### target.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.

Extra options:

* `sort_mode` - item ordering:
    * `relevance` - default
    * `featured`
    * `pricelow`
    * `pricehigh`
    * `newest`

### tesco.com ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `Brand` is guessed and removed from the product title.
    * There is a list of known brands. This list should include all more than one word brands.
    * If the title begins with "dr " or "dr. ", the first two words of the title are considered the brand.
    * If " method " is in the title, the brand is considered to be Method.
    * Otherwise, the first word of the title is considered the brand.
* `related_products` is not implemented.
* `description` is not retrieved.

### trolley.ae ###

Not retrieved fields\features:

* `related_products`
* `description`
* `brand`
* `is_out_of_stock`
* `url` (all the product details are at the search result pages)
* `upc`
* `is_in_store_only`
* `model`

Extra options:

* `order` - item ordering:
    * `default` - seems to be unordered one
    * `name`
    * `price`
    * `rating`
    * `model`
*  `direction` - sort direction, can be one of the following:
    * asc (default)
    * desc

Sample usage: `scrapy crawl trolley_products -a searchterms_str="apple" -a limit=100 -a order="name" -a direction=desc`

### victoriassecret.com ###

* `UPC` and `is_out_of_stock` are not scraped
* Most prices are in min-max format, like "$25 - $35"
* use "-a theme='pink'" to scrape victoriassecret.com/pink

### vitacost.com ###

Spider takes `order` argument with following possible values:

* `relevance` (default)
* `price_asc` - price, low to high
* `price_desc` - price, high to low
* `name` - product name (A-Z)
* `name_desc` - product name (Z-A)
* `best` - best sellers first
* `rating` - average rating, high to low
* `new` - newer products first

Following fields are not scraped: `upc`, `is_in_store_only`, `model`.

### vitadepot.com ###

The spider takes three additional optional arguments:

* `sort` - sort order. Can be `name`, `relevance` (default), or `price`.
* `direction` - sort direction. Can be `asc` (default) for ascending order or `desc` for descending order.
* `cat` - category id or alias.

List of category aliases defined: `brand`, `health_concern`, `vitamins_and_supplements`, `herbs_and_homeopathics`, `sports_and_fitness`, `diet_and_weight_loss`, `superfoods_and_tea`, `babies_and_kids`, `personal_care_and_home`, `men_and_women`, `pets`.

There are the following caveats:

* `relevance` sort order will, in most cases, not scrape some items. `name` doesn't have that problem. `price` might have the problem as well, but it's very unlikely for most cases.
* `model` and `UPC` are not retrieved.
* `related_products` not scraped.
 
### walgreens.com ###

There are the following caveats:

* The `UPC` is not retrieved.
* `related_products` is not implemented.

### walmart.com ###

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * best_match (this is the default)
    * high_price
    * low_price
    * best_sellers
    * newest
    * rating

Sample usage: `scrapy crawl walmart_products -a searchterms_str="dry hair shampoo" -a search_sort=newest`


There are the following caveats:

* Product variants are ignored.
* If a product is not available on-line, the price is not available.


### well.ca ###

There are the following caveats:

* The `UPC` may not be correct. I found no way to verify it.
* `related_products` is implemented.

### wetseal.com ###

There are the following caveats:

* The `UPC` may not be correct.
* `related_products` is implemented.
This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * default
    * newarrivals
    * bestsellers
    * pricelh
    * pricehl

### wowhd.us ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is not implemented.

This spider has the additional options:

* `sort_mode`: Changes the order of the results. Its values can be:
    * relevance
    * bestseller
    * price
    * release

### yankeecandle.com ###

Spider takes `order` argument with following possible sort modes:

* `rating`: average product rating
* `name_asc`: product name, ascending
* `name_desc`: product name, descending
* `price_asc`: price, ascending
* `price_desc`: price, descending

If no order is given, relevance is assumed.

There are following caveats:

* `UPC`, `model`, and `is_in_store_only` fields are not retreived.
* An additional request is required to scrape `related_products`.
* `brand` field is hardcoded to "Yankee Candle"
* `locale` field is hardcoded to `en_US`

### zalora.com.ph ###

There are the following caveats:

* The `UPC` is not retrieved.
* The `model` is not retrieved.

This spider has the additional options:

* `search_sort`: Changes the order of the results. Its values can be:
    * popularity (this is the default)
    * low_price
    * high_price
    * latest_arrival
    * discount

### zappos.com ###

Spider takes `search_sort` argument with following possible sort modes:

* `rating`: average product rating, descending
* `new_arrivals`:  new arrivals, descending
* `best_sellers`: best seller products, descending
* `price_asc`: price, ascending
* `price_desc`: price, descending
* `brand_name`: brand name, ascending
* `default`: relevance

If no `search_sort` value is given, relevance is used.

There are following caveats:

* `is_out_of_stock`, `model`, and `is_in_store_only` fields are not retreived.
* There are recommended products and also-bought products showed, but can't retreived. The site technique caused this.

### zavvi.com ###

There are the following caveats:

* `related_products` is implemented.
* `buyer_reviews` is not implemented.


## Coupon scrappers ##

Currently there are 3 sites, which can be scrapped for coupons (kohls - `http://www.kohls.com/sale-event/coupons-deals.jsp`, jcpenney - `http://www.jcpenney.com/jsp/browse/marketing/promotion.jsp?pageId=pg40027800029#`, macys - `http://www1.macys.com/shop/coupons-deals`). When sending such kind of tasks to SQS, message must contain next parameters: 

* `task_id` - as usual
* `site` - must be one of the following: `kohls_coupons`, `jcpenney_coupons`, `macys_coupons`
* `url` (optional) - url of the page, which should be crapped for variants on the selected site. If not set, default url for the current site will be taken.


## Usage ##

### Crawler ###

The crawler is a typical Scrapy app with the following additional parameters:

* quantity: The number of results to return. By default will return all results.
* searchterms_str: A search term.
* searchterms_fn: A path to a file with search terms, one per line.

For example, to scrape Walmart.com for the top 20 "laundry detergent" matching products and output the result to a jsonlines file:

    scrapy crawl walmart_products -a searchterms_str="laundry detergent" -a quantity=20 -o "laundry detergent.jl" -t jsonlines


### Data summary ###

To summarize the results of the above search filtering results by brand Tide:

    python summarize-search.py --filter brand=Tide "tide summary.csv" "laundry detergent.jl"

In the example, the output file is first because you can specify several input files. For example, the output from several sites or several search terms.

```
usage: summarize-search.py [-h] [-v] [-f FILTER] output inputs [inputs ...]

Summarize search data.

positional arguments:
  output                the CSV output file.
  inputs                the JSON line input files.

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -f FILTER, --filter FILTER
                        filter on <property>=<value>
```


### Additional ranking fields (Best sellers ranking) ###

Sometimes it's useful to have in a dataset the ranking of a product on several sort orders. Unfortunately, there's no way to get this information directly from a spider so it must be post-processing.

To achieve this, a special purpose tool was created to add the best sellers ranking to an existing one. The tool is `add-best-seller.py` and it's used as follows:

```
usage: add-best-seller.py [-h] [-v] ranking best_seller_ranking

Merge spider outputs to populate best seller ranking as an additional field.

positional arguments:
  ranking              a JSONLines file.
  best_seller_ranking  a JSONLines file ranked by best seller.

optional arguments:
  -h, --help           show this help message and exit
  -v, --version        show program's version number and exit
```

The resulting dataset will be output to stdout so it can be captured like this:

```
add-best-seller.py walmart_tide.jl walmart_tide-by_best_seller.jl >walmart_tide-with_seller_ranking.jl
```

## TOR proxies ##

You can make any spider to use [TOR proxies](https://bitbucket.org/dfeinleib/tmtext/wiki/TOR%20proxies). Add this to the spider class: 

```
use_proxies = True
```

Example:

```
class AmazonCoUkProductsSpider(AmazonTests, BaseProductsSpider):
    name = "amazoncouk_products"
    allowed_domains = ["www.amazon.co.uk"]
    start_urls = []
    ...
    use_proxies = True
```

Proxies will ONLY be used if they are working. To check if they are working or not, every spider sends 4 test requests through random ports. If all of them fail, the proxies are considered to be non-working. If at least one request passed then the proxies are considered to be working.

## Environment Setup ##

The detailed instructions to setup the environment to test the server are:

1. [Setup VirtualEnv](VirtualEnv Setup)
1. [Setup Git](Git Setup)
1. Clone the git repository: `git clone git@bitbucket.org:dfeinleib/tmtext.git`
1. Change dir to the project's directory: `cd tmtext/product-ranking`
1. Create a virtual environment: `virtualenv --no-site-packages .`
1. Activate the virtual environment: `source bin/activate`
1. Install dependencies: `pip install scrapy==0.24` (Scrapy 0.24 is needed)

On Mac: sudo python setup.py install (?)