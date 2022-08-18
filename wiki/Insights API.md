# Content Analytics Insights API #

Last updated Oct 5, 2016

# Authentication #
This API require auth by default. Each client has an access key they must include in the API call.

For example, in the test api: [http://test.contentanalyticsinc.com](http://test.contentanalyticsinc.com)

The test user has this token assigned: ```329b026885f6f82b74727ffe33b3e3d86a7fb4d1```

The token must be included in the http requests headers, using the Authentication field and with the following format: ```Token {token}```. 

For Example:

```
!#HTTP
GET /restapi HTTP/1.1
Host: test.contentanalyticsinc.com
Authorization: Token 329b026885f6f82b74727ffe33b3e3d86a7fb4d1
``` 

or with CURL sintax:

```
curl -X GET -H "Authorization: Token 329b026885f6f82b74727ffe33b3e3d86a7fb4d1" "http://test.contentanalyticsinc.com/restapi/product_lists/"
```



# API Endpoints #

API endpoint is "https://<server-name>.contentanalyticsinc.com/restapi/"

# Lists and Ranges #

Where indicated, you can use a comma-separated list of values (e.g id=1,2,3)

Anywhere you can use a list of values, you can also use a range, (e.g. id=1-3)

## Product Lists ##
* Example Output:

```
#!JSON
{
  "id": 1,
  "user_id": 7,
  "name": "First Test Here",
  "crawl": false,
  "created_at": "2015-03-15T05:57:07.829910",
  "is_public": null,
  "with_price": null,
  "urgent": null,
  "is_custom_filter": false,
  "crawl_frequency": null,
  "type": "regular",
  "ignore_variant_data": false
}
```

* List all ProductList: ```{endpoint_url}/product_lists/```
* Get ProductList by ID(s): ```{endpoint_url}/product_lists/?id={id[,id2,...]}```
,
## Search Term Groups ##

* Example Output:

```
#!JSON
{
  "id": 4,
  "name": "Customer_Pilot's Group",
  "created_at": "2015-01-14T17:43:36.475308",
  "enabled": true
}
```

* List all Search Term Groups: ```{endpoint_url}/search_terms_groups/```
* Get Search Term Groups by ID(s): ```{endpoint_url}/search_terms_groups/?id={id[,id2,...]}```

## Search Terms ##

* Example Output:

```
#!JSON
{
  "id": 3,
  "title": "ultrabook",
  "group_id": 2
}
```

* List all Search Terms: ```{endpoint_url}/search_terms/```
* Get Search Term by ID(s): ```{endpoint_url}/search_terms/?id={id[,id2,...]}```


## Sites ##

* Example Output:

```
#!JSON
{
  "id": 2,
  "name": "Sears.com",
  "url": "http://sears.com",
  "image_url": "Sears-logo.png",
  "site_type": 0,
  "results_per_page": null,
  "zip_code": null,
  "traffic_upload": false,
  "crawler_name": null,
  "location": null,
  "user_agent": null
}
```
* Get all sites:  ```{endpoint_url}/sites/```
* Get Sites by ProductList ID(s): ```{endpoint_url}/sites/?product_list_id={id[,id2,...]}```
* Get Sites by Search Term ID(s): ```{endpoint_url}/sites/?search_term_id={id[,id2,...]}```
* Get Sites by Search Term Group ID(s):  ````{endpoint_url}/sites/?search_term_group_id={id[,id2,...]}```

* Get Sites by ProductList ID(s) and Date(s): ```{endpoint_url}/sites/?product_list_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Sites by Search Term ID(s) and Date(s): **Not implemented**
* Get Sites by Search Term Group ID(s) and Date(s):  ````{endpoint_url}/sites/?search_term_group_id={id[,id2,...]}&date={date[,date2,...]}```

* Get Sites by Search Term Group ID(s) and waiting to be crawled:  ````{endpoint_url}/sites/?search_term_group_id={id[,id2,...]}&waiting```




## Brands ##

* Example Output:

```
#!JSON
{
  "id": 1,
  "name": "Ace",
  "created": "2013-08-08T22:04:12",
  "company_id": 0,
  "brand_type": {
    "id": 2,
    "name": "CPG"
  },
  "parent_id": 0
}
```
* Get all brands:  ```{endpoint_url}/brands/```
* Get Brands by ProductList ID(s) and Site ID(s): ```{endpoint_url}/brands/?product_list_id={id[,id2,...]}&site_id={id[,id2,...]}```
* Get Brands by Search Term and Site ID(s): ```{endpoint_url}/brands/?search_term_id={id[,id2,...]}&site_id={id[,id2,...]}```

## Date(s)s ##

* Example Output:

```
#!JSON
{
  "date": "2015-03-17"
}
```
* Get Date(s)s by ProductList ID(s), Brand ID(s) and Site ID(s): ```{endpoint_url}/dates/?product_list_id={id[,id2,...]}&site_id={id[,id2,...]}&brand_id={id[,id2,...]}```
* Get Last Date(s) by ProductList ID(s): ```{endpoint_url}/dates/?product_list_id={id[,id2,...]}&last_time ```

* Get Date(s)s by Search Term Group ID(s): ```{endpoint_url}/dates/?search_term_group_id={id[,id2,...]}```
* Get Last Date(s) by Search Term Group ID(s): ```{endpoint_url}/dates/?search_term_group_id={id[,id2,...]}&last_time```

* Get Date(s)s  by Search Term, Brand ID(s) and Site ID(s): ```{endpoint_url}/dates/?search_term_id={id[,id2,...]}&site_id={id[,id2,...]}&brand_id={id[,id2,...]}```

## Price Data ##

* Example Output:

```
#!JSON
{
  "url": "http://www.walmart.com/ip/Samsung-50-Class-LED-1080p-60Hz-HDTV-3.7-ultra-slim-UN50EH5000/21081389",
  "title": "Samsung 50\" Class LED 1080p 60Hz HDTV, (3.7\" ultra-slim), UN50EH5000",
  "currency": "USD",
  "price": "697.99"
}
```
* Get Prices by Search Term Group ID(s) and Date(s): ```{endpoint_url}/price_data/?search_term_group_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Prices by Search Term ID(s) and Date(s): ``` {endpoint_url}/price_data/?search_term_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Prices by Product List ID(s) and Date(s): ``` {endpoint_url}/price_data/?product_list_id={id[,id2,...]}&date={date[,date2,...]}```


## Ranking Data ##

* Example Output:

```
#!JSON
{
  "search_term": "laptop",
  "site_id": 7,
  "title": "Acer Aspire E 11 ES1-111M-C40S 11.6-Inch Laptop (Diamond Black)",
  "url": "http://www.amazon.com/Acer-Aspire-ES1-111M-C40S-11-6-Inch-Diamond/dp/B00MNOPS1C",
  "ranking": 237
}
```
* Get Rankings by Search Term Group ID(s) and Date(s): ```{endpoint_url}/ranking_data/?search_term_group_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Rankings by Search Term ID(s) and Date(s): ``` {endpoint_url}/ranking_data/?search_term_id={id[,id2,...]}&date={date[,date2,...]}```

* Get Rankings by Product List ID(s) and Date(s): **No ranking data for product lists**

## Out of Stock Data ##

* Example Output:

```
#!JSON
{
  "search_term": "laptop",
  "site_id": 7,
  "title": "Acer Aspire E 11 ES1-111M-C40S 11.6-Inch Laptop (Diamond Black)",
  "url": "http://www.amazon.com/Acer-Aspire-ES1-111M-C40S-11-6-Inch-Diamond/dp/B00MNOPS1C",
  "is_out_of_stock": false,
  "no_longer_available": false
}
```

* Get Out Of Stock Data by Search Term Group ID(s) and Date(s): ```{endpoint_url}/out_of_stock_data/?search_term_group_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Out Of Stock Data by Search Term ID(s) and Date(s): ``` {endpoint_url}/out_of_stock_data/?search_term_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Out Of Stock Data by Product List ID(s) and Date(s): ``` {endpoint_url}/out_of_stock_data/?product_list_id={id[,id2,...]}&date={date[,date2,...]}```

## Buy Box Data ##

* Example Output:

```
#!JSON
{
  "search_term": "laptop",
  "site_id": 7,
  "title": "Acer Aspire E 11 ES1-111M-C40S 11.6-Inch Laptop (Diamond Black)",
  "marketplace": "Buysmart",
  "url": "http://www.amazon.com/Acer-Aspire-ES1-111M-C40S-11-6-Inch-Diamond/dp/B00MNOPS1C",
  "is_out_of_stock": false,
  "no_longer_available": false,
  "first_party_owned": false
}
```

* Get Buy Box Data by Search Term Group ID(s) and Date(s): ```{endpoint_url}/buy_box_data/?search_term_group_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Buy Box Data by Search Term ID(s) and Date(s): ``` {endpoint_url}/buy_box_data/?search_term_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Buy Box Data by Product List ID(s) and Date(s): ``` {endpoint_url}/buy_box_data/?product_list_id={id[,id2,...]}&date={date[,date2,...]}```

## Reviews Data ##

* Example Output:

```
#!JSON
{
  "search_term": "painkiller",
  "site_id": 7,
  "url": "http://www.amazon.com/Painkiller-Hell-Damnation-Playstation-3/dp/B009VURQDE",
  "title": "Painkiller: Hell and Damnation - Playstation 3",
  "total_count": 12,
  "average_num": 4.3,
  "one_star": 0,
  "two_star": 0,
  "three_star": 2,
  "four_star": 5,
  "five_star": 5
}
```

* Get Reviews Data by Search Term Group ID(s) and Date(s): ```{endpoint_url}/reviews_data/?search_term_group_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Reviews Data by Search Term ID(s) and Date(s): ``` {endpoint_url}/reviews_data/?search_term_id={id[,id2,...]}&date={date[,date2,...]}```
* Get Reviews Data by Product List ID(s) and Date(s): ``` {endpoint_url}/reviews_data/?product_list_id={id[,id2,...]}&date={date[,date2,...]}```


# Other Options #

## Paginations ##
All the responses all wrapped with information about pagination for the query. 
The responses will use this format:

```
#!JSON
 {
    "count": 0,
    "next": null,      
    "previous": null,
    "results": []
}
```

* `Count` : Number of results for the query
* `Next` : Link to next page api call, if available
* `Previous` : Link to previous page api call, if available
* `Results` : Results of the query

## Filtering ##
You can also query the name of any field like in ``` ?field=value ``` to get a filter of the results. For example:

``` 
{endpoint}/search_terms/?title=ultrabook
```

```
#!JSON
 {
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 3,
            "title": "ultrabook",
            "group_id": 2
        },
        {
            "id": 40,
            "title": "ultrabook",
            "group_id": 9
        }
    ]
}
```


# Common Scenarios #

## How to get a list of search term groups (group name, ID(s)) ##

Use this endpoint to get the list of search terms groups: ```{endpoint_url}/search_term_groups/```
Example of response:

```
#!JSON
{
    "count": 7,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 4,
            "name": "Customer_Pilot's Group",
            "created_at": "2015-01-14T17:43:36.475308",
            "enabled": true
        },
        {
            "id": 6,
            "name": "Baby Products",
            "created_at": "2015-03-11T23:06:29.582375",
            "enabled": true
        },
        {
            "id": 5,
            "name": "Pilot Two's Test Group",
            "created_at": "2015-01-14T17:49:45.638852",
            "enabled": true
        },
        {
            "id": 3,
            "name": "Macbooks",
            "created_at": "2014-12-23T21:58:21.852726",
            "enabled": true
        },
        {
            "id": 9,
            "name": "Electronics",
            "created_at": "2015-05-25T20:46:50.940247",
            "enabled": true
        },
        {
            "id": 10,
            "name": "Group for Testing",
            "created_at": "2015-05-26T23:27:20.089222",
            "enabled": true
        },
        {
            "id": 2,
            "name": "Laptops",
            "created_at": "2014-12-23T19:52:49.528125",
            "enabled": true
        }
    ]
}
```

## How can I tell, for a given search term or search term group, which sites there are data for? ##
### Using Search Term ###
* First, you need to find out what the Search Term ID(s) is (Skip this step if you previously knew it):
```
  * You can list all the results: {endpoint}/search_terms/ 
  * Or, you can filter it by name: {endpoint}/search_terms/?title={title}
```
* Then you have to call the sites endpoint using the previous ID(s) as a query param: ``` {endpoint}/sites/?search_term_id={id[,id2,...]} ```

Output example for ```{endpoint}/sites/?search_term_id=3 ```:
```
#!JSON
{
    "count": 7,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 112,
            "name": "amazon.ca",
            "url": "http://www.amazon.ca/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 17,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazonca",
            "location": null,
            "user_agent": null
        },
        {
            "id": 97,
            "name": "google.co.uk",
            "url": "https://www.google.co.uk/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 99,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "google_couk",
            "location": null,
            "user_agent": null
        },
        {
            "id": 75,
            "name": "google.com",
            "url": "http://www.google.com/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 9,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "google",
            "location": null,
            "user_agent": null
        },
        {
            "id": 1,
            "name": "Walmart.com",
            "url": "http://walmart.com",
            "image_url": "walmart-logo.png",
            "site_type": 1,
            "results_per_page": 20,
            "zip_code": null,
            "traffic_upload": true,
            "crawler_name": "walmart",
            "location": null,
            "user_agent": null
        },
        {
            "id": 10,
            "name": "bestbuy.com",
            "url": "http://bestbuy.com",
            "image_url": "bestbuy-logo.jpg",
            "site_type": 1,
            "results_per_page": 3,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "bestbuy",
            "location": null,
            "user_agent": null
        },
        {
            "id": 84,
            "name": "amazon.co.uk",
            "url": "http://www.amazon.co.uk/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 18,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazoncouk",
            "location": null,
            "user_agent": null
        },
        {
            "id": 7,
            "name": "Amazon.com",
            "url": "http://amazon.com",
            "image_url": "Amazon.png",
            "site_type": 1,
            "results_per_page": 24,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazon",
            "location": null,
            "user_agent": null
        }
    ]
}
```

### Using Search Terms Groups ###
* First, you need to find out what the Search Terms Groups ID(s) is (Skip this step if you previously knew it):
```
  * You can list all the results:  {endpoint}/search_term_groups/ 
  * Or, you can filter it by name:  {endpoint}/search_term_groups/?name={name} 
```
* Then you have to call the sites endpoint using the previous ID(s) as a query param: ``` {endpoint}/sites/?search_term_group_id={id[,id2,...]} ```

Output example for ```{endpoint}/sites/?search_term_group_id=2 ```:

```
#!JSON
{
    "count": 7,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 112,
            "name": "amazon.ca",
            "url": "http://www.amazon.ca/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 17,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazonca",
            "location": null,
            "user_agent": null
        },
        {
            "id": 97,
            "name": "google.co.uk",
            "url": "https://www.google.co.uk/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 99,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "google_couk",
            "location": null,
            "user_agent": null
        },
        {
            "id": 75,
            "name": "google.com",
            "url": "http://www.google.com/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 9,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "google",
            "location": null,
            "user_agent": null
        },
        {
            "id": 1,
            "name": "Walmart.com",
            "url": "http://walmart.com",
            "image_url": "walmart-logo.png",
            "site_type": 1,
            "results_per_page": 20,
            "zip_code": null,
            "traffic_upload": true,
            "crawler_name": "walmart",
            "location": null,
            "user_agent": null
        },
        {
            "id": 10,
            "name": "bestbuy.com",
            "url": "http://bestbuy.com",
            "image_url": "bestbuy-logo.jpg",
            "site_type": 1,
            "results_per_page": 3,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "bestbuy",
            "location": null,
            "user_agent": null
        },
        {
            "id": 84,
            "name": "amazon.co.uk",
            "url": "http://www.amazon.co.uk/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 18,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazoncouk",
            "location": null,
            "user_agent": null
        },
        {
            "id": 7,
            "name": "Amazon.com",
            "url": "http://amazon.com",
            "image_url": "Amazon.png",
            "site_type": 1,
            "results_per_page": 24,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazon",
            "location": null,
            "user_agent": null
        }
    ]
}
```

## Need a way to get the list of URLs for a specific ProductListID(s) ##

* First, you need to find out what the Product List ID(s) is (Skip this step if you previously knew it):
```
  * You can list all the results:  {endpoint}/product_lists/ 
  * Or, you can filter it by name:  {endpoint}/product_lists/?name={name} 
```
* Then you have to call the sites endpoint using the previous ID(s) as a query param: ``` {endpoint}/sites/?product_list_id={id[,id2,...]} ``

* Iterate over the results objects to read each URL field.

Output example for ``` {endpoint}/sites/?product_list_id=3 ```:

```
#!JSON
{
    "count": 3,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 108,
            "name": "Amazon.com - iPhone",
            "url": "http://www.amazon.com/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": null,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazon",
            "location": null,
            "user_agent": "iphone_ipad"
        },
        {
            "id": 54,
            "name": "AmazonFresh - NoCal",
            "url": "http://fresh.amazon.com",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 50,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazonfresh",
            "location": "northern_cali",
            "user_agent": null
        },
        {
            "id": 7,
            "name": "Amazon.com",
            "url": "http://amazon.com",
            "image_url": "Amazon.png",
            "site_type": 1,
            "results_per_page": 24,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazon",
            "location": null,
            "user_agent": null
        }
    ]
}
```

## For a given product list ID(s), need a way to tell which sites are currently set to crawl ##
We have no such info, we don't tie product list(s) with site(s).

## For a given product list ID(s), need a way to tell which sites were crawled on a given date ##

Use this endpoint: ```{endpoint}/sites/?product_list_id={id[,id2,...]}&date={date[,date2,...]}

Output example for ``` {endpoint}sites/?product_list_id=3&date=2016-05-12 ```:

```
#!JSON
{
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 7,
            "name": "Amazon.com",
            "url": "http://amazon.com",
            "image_url": "Amazon.png",
            "site_type": 1,
            "results_per_page": 24,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazon",
            "location": null,
            "user_agent": null
        }
    ]
}
```

## For a given search term group, need a way to tell which sites were crawled on a given date ##

Use this endpoint: ```{endpoint}/sites/?search_term_group_id={id[,id2,...]}&date={date[,date2,...]}

Output example for ``` {endpoint}sites/?search_term_group_id=3&date=2016-5-6```:

```
#!JSON
{
    "count": 3,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 10,
            "name": "bestbuy.com",
            "url": "http://bestbuy.com",
            "image_url": "bestbuy-logo.jpg",
            "site_type": 1,
            "results_per_page": 3,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "bestbuy",
            "location": null,
            "user_agent": null
        },
        {
            "id": 90,
            "name": "ebay.co.uk",
            "url": "http://www.ebay.co.uk/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 51,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "ebay_uk",
            "location": null,
            "user_agent": null
        },
        {
            "id": 7,
            "name": "Amazon.com",
            "url": "http://amazon.com",
            "image_url": "Amazon.png",
            "site_type": 1,
            "results_per_page": 24,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazon",
            "location": null,
            "user_agent": null
        }
    ]
}
```

## For a given search term group, need a way to tell which sites are currently set to be crawled ##

Use this endpoint: ```{endpoint}/sites/?search_term_group_id={id[,id2,...]}&waiting```

Output example for ``` {endpoint}sites/?search_term_group_id=3&waiting```:

```
#!JSON
{
    "count": 4,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "Walmart.com",
            "url": "http://walmart.com",
            "image_url": "walmart-logo.png",
            "site_type": 1,
            "results_per_page": 20,
            "zip_code": null,
            "traffic_upload": true,
            "crawler_name": "walmart",
            "location": null,
            "user_agent": null
        },
        {
            "id": 10,
            "name": "bestbuy.com",
            "url": "http://bestbuy.com",
            "image_url": "bestbuy-logo.jpg",
            "site_type": 1,
            "results_per_page": 3,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "bestbuy",
            "location": null,
            "user_agent": null
        },
        {
            "id": 90,
            "name": "ebay.co.uk",
            "url": "http://www.ebay.co.uk/",
            "image_url": "",
            "site_type": 1,
            "results_per_page": 51,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "ebay_uk",
            "location": null,
            "user_agent": null
        },
        {
            "id": 7,
            "name": "Amazon.com",
            "url": "http://amazon.com",
            "image_url": "Amazon.png",
            "site_type": 1,
            "results_per_page": 24,
            "zip_code": null,
            "traffic_upload": false,
            "crawler_name": "amazon",
            "location": null,
            "user_agent": null
        }
    ]
}
```

## For a given STG or PL, return the last date for which data was crawled ##

* For PL use this endpoint: ```{endpoint}/dates/?product_list_id={id[,id2,...]}&last_time```

Output example for ``` {endpoint}/dates/?product_list_id=10&last_time```:

```
#!JSON
{
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
        {
            "date": "2016-05-13"
        }
    ]
}
```

* For STG use this endpoint: ```{endpoint}/dates/?search_term_group_id={id[,id2,...]}&last_time```

Output example for ``` {endpoint}/dates/?search_term_group_id=3&last_time```:

```
#!JSON
{
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
        {
            "date": "2016-05-13"
        }
    ]
}
```


### This Space for Additional Non Public Notes ###

[Notes](https://bitbucket.org/dfeinleib/tmtext/wiki/Insights%20API%20Notes)