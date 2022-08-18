Matching products across bestsellers lists: script `match_product.py`

Given two sites and respective categories, check for every bestseller product on site1/category1 for matches in site2/category2. Works for all sites and categories for which there are bestsellers.

### Usage ###

    python match_product.py <site1> <category1> <site2> <category2> [<method>] [<param>]

* `site1`, `category1` - match products in category1 of site1
* `site2`, `category2` - search for them in category2 of site2
* `method` - integer (1/2), optional argument: method to use for matching (1 or 2). Default is 1.
* `param` - float (0-1), optional argument: parameter used in matching for narrowing or widening the number of results. Default is 0.65

`category1` and `category2` can be any categories/departments for which bestsellers were extracted on the respective sites. A **list of categories and departments for each site's bestsellers list** can be found in the folder sample_output/bs_departments, in files with names of the form `<site>_depts.txt` or `<site>_cats.txt`.

**Examples:** 

* Match products in Amazon Clothing bestsellers to products in Overstock Clothing bestsellers. Use method 2 and parameter 0.8 (more strict than default)

     `python match_product.py amazon Clothing overstock Clothing 2 0.8`

* Match products in Amazon TV & Home Theater bestsellers to products in Bestbuy Televisions bestsellers. Use default method and matching parameter.

     `python match_product.py amazon "TV & Home Theater" bestbuy Televisions`


### Output ###

Product names for which matches were found, along with their candidate matches (product names) and a score for each, ordered by their score; and the complete info on the matches as found in the bestsellers jl files.

**Example:**

    
```
#!python

PRODUCT:  Ray-Ban RB2132 New Wayfarer Sunglasses
    MATCHES: 
    - Ray-Ban Men's 'RB2132' New Wayfarer Sunglasses ; SCORE: 7
    - Ray-Ban Unisex RB2132 Wayfarer Fashion Sunglasses ; SCORE: 6
    {u'page_title': u"Ray-Ban Men's 'RB2132' New Wayfarer Sunglasses", u'url': u'http://www.overstock.com/Clothing-Shoes/Ray-Ban-Mens-RB2132-New-Wayfarer-Sunglasses/7031048/product.html?IID=prod7031048&sec_iid=78176', u'price': u'$99.99', u'rank': u'6', u'date': u'2013-08-02', u'department': u'Clothing', u'list_name': u"Ray-Ban Men's 'RB2132' New Wayfarer Sunglasses", u'product_name': u"Ray-Ban Men's 'RB2132' New Wayfarer Sunglasses"}
    {u'page_title': u'Ray-Ban Unisex RB2132 Wayfarer Fashion Sunglasses', u'url': u'http://www.overstock.com/Clothing-Shoes/Ray-Ban-Unisex-RB2132-Wayfarer-Fashion-Sunglasses/5173946/product.html?IID=prod5173946&sec_iid=78176', u'price': u'$100.99', u'rank': u'1', u'date': u'2013-08-02', u'department': u'Clothing', u'list_name': u'Ray-Ban Unisex RB2132 Wayfarer Fashion Sunglasses', u'product_name': u'Ray-Ban Unisex RB2132 Wayfarer Fashion Sunglasses'}
    --------------------------------
    results:  1
```

### Tools ###

Python modules: nltk, scikit-learn

