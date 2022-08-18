[This page was created as draft for [Bug 1868](https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=1868)]

[TOC]

# General info #

### Server Url ###
Server can be accessed with the [url](http://rankings.contentanalyticsinc.com/). Admin panel is available by [this url](http://rankings.contentanalyticsinc.com/admin/).

### Api calls ###
Logic of the cache server is made in such way, that it expects same input as the [SpyFu api](http://www.spyfu.com/o/spyfu-api/documentation/overview.aspx). 

### Returned data ###
Data will contain different set of varaibles, depending on the successfull of the request.

#### Success requests ####
Each request, that processed properly, will contain `data` field. This is main variable, which contains all, that must be returned from the api. Each request also contains varialbe `cache`. It indicates, weather data was fetched from the cache (`true`), or from the api (`false`). If results returned from the cache, request will also contain additional variable, `last_updated`, the datetime of the last request, made to the api to retrieve this data.

#### Failed requests ####
If request is failed for some reason, it will contain `error` field with the description of the occured error. Failed requests may return different statuses. If status is `400`, this means that error caused by  missing of some of the required parameters to the request. If status is `404`, this means that error occured in the api side. In such case `error` will contain api response body, andadditional variable will appear: `api_status` - api response status code. 

### Usage format ###
Cache server recieves both `GET` and `POST` requests and variables. This means that you can pass api parameters in the request body or straight in the url. 

**When doing `POST` request, make sure that url ends with slash, otherwise it would not work**: `http://1.2.3.4/api/get_groups` - wrong, `http://1.2.3.4/api/get_groups/` - correct.
 
For `GET` requests, slash isn't mandatory, but if it is included, it should appear **before** any url parameters: `http://1.2.3.4/api/get_terms?some_param/` - wrong, `http://1.2.3.4/api/get_terms/?some_param` - correct.

### Known issues ###
General problem, is that SpyFu api may work slow, so requests may take long time. This is related to all requests, but has greatest impact for the `Get Terms` call, as it requires one additional call per keyword to the api to fetch Search Volumes. This may take to 15 minutes, depending on the number of keywords in the group. **UPDATE**: Currently, introduced new logic of retrieving bulk search volumes for a list of keywords. It showed result 12 seconds for 50 keywords and is a best and fastest option. The only issue about this approach, is that search volumes may differ from the ones, which are on the site (for example, 'cctv kits' keyword has value of 70 on the site, but 60 returned with this method).


# Main logic

Variable in the settings, called `KEYWORD_FRESHNESS` indicates, for how long retrieved data from the api should be considered as valid. If requested data is in such time window, response will be returned from the cache, otherwise api call will be initiated.

Client will be available to perform such things:

*  Add search terms to group (Group Name, Term1, Term2...):
*  Get list of search terms in group (Group Name)
*  Delete search term from group (Group Name, Term)
*  Get rankings for a group (Group Name)
*  Get rankings for an individual search term (Term)

# Api usage #

### Get Groups ###
Get list of all available groups and domains.

*  Url: `/api/get_groups/`.
*  Params: not requires any params.
*  Returns: list of all available groups. 

	Each item will contain following fields: 

	*  `DomainId` (string) - id of the domain, string representation of big int
	*  `DomainName` (string) - name of the domain, string representation of the uuid
	*  `ListId` (string) - id of the group
	*  `ListName` (string) - name of the group
	*  `ListType` (string) - type of the group, may be `SEO` or `PPC` (pay per click)

### Add Terms ###
Add search terms to the group. After adding term to the existing group, this group will be marked as 'requires update' and its data will be fetched from the api on the next call of `Get Terms`. If group doesnt exist, then new group will be created, `Get Groups` will be marked as 'requires update' and its data will be fetched from the api on the next call, regardless of the date, it was retrieved last time. There is no possibility to create new group and retrieve its data in one call.

*  Url: `/api/add_terms/`.
*  Params: 

	*  `domainName` (string) - domain, to add new keywords for
	*  `listName` (string) - name of the group, to which keywords will be added
	*  `keywordCsv` (string) - list of keywords to add to the track, separated with the comma, encoded with base64

*  Returns: string, idicating result of the call. If success, should return `Add Successful.`.

### Get Terms ###
Get rankings for a group. If group is not found in the cache db, result will be returned straight from the api and next call to `Get Groups` will fetch data from the api, regardless of the date, when it was fetched last time (even if it was minute ago). This is done to reflect last changes in the cache, even if the api was used by some third party.

*  Url: `/api/get_terms/`.
*  Params:

	*  `listId` (string) - id of the group

*  Returns: list of all search terms in the given group. 

	Each item will contain following fields:

	*  `Keyword` (string) - search phrase
	*  `Term_Id` (int) - id of the given phrase
	*  `Search_Volume` (int) - search volume for the given phrase
	*  `Google_Organic_Position` (int) - phrase position in the google search results, can be negative number, which means it's position is >100 or isn't set yet (if term is new)
	*  `Google_Organic_Position_Change` (int) - change of the position based on two latest checks
	*  `Last_Checked_Google` (datetime) - time of the last check for google
	*  `Google_Search_Date_Id` (int) - integer representation of the previous value, e.g.:20150102 for the 2015-01-02
	*  `Google_Extracted_Hour` (int) - same as above but includes hour, e.g.: 2015010213 for the 2015-01-02 13:00
	*  `Bing_Organic_Position` (int) - same as Google_Organic_Position, but for Bing/Yahoo
	*  `Bing_Organic_Position_Change` (int) - same as Google_Organic_Position_Change, but for Bing/Yahoo
	*  `Last_Checked_Bing` (datetime) - same as Last_Checked_Google, but for Bing/Yahoo
	*  `Bing_Search_Date_Id` (int) - same as Google_Search_Date_Id, but for Bing/Yahoo
	*  `Bing_Extracted_Hour` (int) - same as Google_Extracted_Hour, but for Bing/Yahoo

### Delete Term ###
Delete search term from group. This action will not set `Get Groups` as invalid. If operation succeeded on the api side, same operation will be performed on the cache side.

*  Url: `/api/delete_term/`.
*  Params: 

	*  `domainId` (string) - id of the domain, to delete term from
	*  `listId` (string) - id of the group in the domain, to delete term from
	*  `termId` (string) - id of the term to delete

*  Returns: string, idicating result of the call. If success, should return `Delete Successful.`.

### Get Term Data
Get rankings for an individual search term.

*  Url: `/api/get_term_data/`.
*  Params:

	*  `domainId` (string) - id of the domain, to show data for
	*  `termId` (string) - id of the term, to show data for

*  Returns: following fields:

	*  `Keyword` (string) - search term, represented by the given termId
	*  `TermId` (int) - id of the term
	*  `Last_Checked_Google` (datetime) - time of the last check for the term in the Google
	*  `Last_Checked_Bing` (datetime) - time of the last check for the term in the Bing/Yahoo
	*  `ResultCount` (int) - count of returned historical data elements
	*  `keywords` (list) - list of the historical data for the given term, each item contains:
	*  `Position` (int) - position of term in the search system, if negative then it is >100 or no checks been performed yet
	*  `Search_Engine` (string) - search engine, for which check was made, can be Google or Bing
	*  `Extracted_Hour` (datetime) - time of the last check performed
	*  `Search_Date_Id` (int) - integer representation of the above field, e.g.: 20150102 for the 2015-01-02
	*  `Ad_Url` (string) - seems like this field is always empty
	*  `Body` (string) - same as above
	*  `Title` (string) - same as aboce

# Admin Usage #

### Clear cache ###
When accessing [main admin page](http://rankings.contentanalyticsinc.com/admin/), there is an option to clear the cache. This link will lead to the page, when user can start the process of clearing cache. User also available to choose, should backup be created before clearing database or no. After confirming and finishing the process, use will see alert with result of operation: whether it finished successfully or not. Backup is created on the running server, but uploading it to the s3/elsewhere is also possible.

![admin1.jpg](https://bitbucket.org/repo/e5zMdB/images/3647147047-admin1.jpg)

### Most frequently requested items ###
There is a possibility to view most visited domains/groups/keywords. Counter for domain and group increasing every time someone requests it's data via `get_terms` call. Counter for keyword increasing, when call to `get_term_data` is happening. This data is stored in `requests` field for each domain/group/keyword item and can be accessed via simple admin view. There is also field `last_request`, which indicates, when last request was made to this item. Ordering by this fields available and included by default. 

![admin2.jpg](https://bitbucket.org/repo/e5zMdB/images/359628839-admin2.jpg)

### Cache settings ###
There is currently only one setting (`keyword_freshness` - how many days data is actual and valid after last request). It can be changed in the view of `Cache settings` admin page. **Important**: don't delete this setting, otherwise it can lead to the errors while using cache.

![admin3.jpg](https://bitbucket.org/repo/e5zMdB/images/1920507573-admin3.jpg)

# TODO #
### CORS ###
Need to add CORS support to allow POST requests from another websites.

Code located at the branch `Bug1868_google_ranking`.