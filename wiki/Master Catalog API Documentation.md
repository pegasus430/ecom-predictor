## Rest API Server

### API Client
Api should not be used as controller, all requests should go through API client. API client allows for cross server functionality.

### Python Developers
Most likely you should be using the "api/products" call, and not the "api/product". This will allow you to:

1. Use filters
2. Use the "apply_product_changes=true" to get all content with updates applied
3. product_id = CAI internal product id (This is the id or mcp.id which is specific to each product. It will be listed in imports, exports and UI as CAID)

### Good to know

1. Authentication uses the API key (recommended) or Username + Password
2. API uses standard HTTP methods (https://en.wikipedia.org/wiki/Hypertext_Transfer_Protocol)
3. All parameters in bellow specification will be represented as JSON object, please make sure you know how HTTP works and you know how to send requests for each method (GET, POST etc).

### API Tutorial

Each endpoint bellow will have following options:

1. **Title** - _The name of API call, Example : Show All Users_
2. **Description** - _Additional info here_
3. **URL** - _The URL structure (path only, no root url) , Example: '/users' or '/users/:id'_
4. **Method** - _The request type (GET | POST | DELETE | PUT)_
5. **URL Params** - _If URL params exist, their specification in accordance with name mentioned in URL section._
6. **Data Params** - _What should the body payload look like._
7. **Sample Call** - _Just a sample call to endpoint._
8. **Success Response** - _What should the status code be on success and is there any returned data._
9. **Error Response** - _Most endpoints will have many ways they can fail. From unauthorized access, to wrongful parameters etc._
10. **Notes** - _This is where all uncertainties, commentary, discussion etc. can go._

# API Endpoints

## Token (API Key)

* **Title**: Get Auth token (API Key)
* **Description**: Returns users API (Each user has its own API Key)
* **Url**: api/token
* **Method**: GET
* **URL Params**: username, password
* **Sample Call**: 
```
api/token?username=USER_EMAIL&password=PASSWORD
```
* **Response**: 
```
{
    "api_key" : "a876cde90ac315e1111111111d429bf1ec0246c4"
}
```

* **Notes**: _Same user will have different API Key on each server, it's generated for each server._

## Product

* **Title**: Get Product (MC developers only)
* **Description**: Returns product object with all fields as they originally were in the MC when the product was last matched, as well as all of the updates and changes that have been made to the product. This call cannot be used with any other filters, and should generally not be used unless you are trying to get all info returned for 1 item. 
* **Url**: api/product/(:product_id)
* **Method**: GET
* **URL Params**: product_id (_CAID, internal product ID_)
* **Sample Call**: 
```
api/product/(:product_id)?api_key=d28ab4cd79d9cbb75467c267614f0266d2220b4f
```
* **Success Response**: 
```
{
    "id":"2495",
    "imported_data_id":"491",
    "product_list_id":"7",
    "product_name":"Diet Mountain Dew Soda, 12 fl oz, 8 pack",
    "url":"http:\/\/grocery.walmart.com\/usd-estore\/m\/product-detail.jsp?skuId=3000183547",
    "price":"3.98",
    "currency":"USD",
    "description":"<B>Diet Mountain Dew Soda:<\/b><ul><li>All the great taste and intensity of Dew without the calories<li>Diet tastes better on the mountain<li>Very low sodium<li>Visit mountaindew.com<\/ul>",
    "long_description":null,
    "shelf_description":null,
    "upc":null,
    "tool_id":null,
    ...
}
```

* **Error Response**: 
```
{"status": 404, "type": "no_product", "message": "No product found"}
```

* **Notes**: _This endpoint has no other applicable filters._

## Products

* **Title**: Get Products
* **Description**: This method returns the list of all products and and their changes separately, you can use any of the filters to narrow down the results.
* **Apply Changes**: By default products and their changes are returned separately, unless "product: {apply_product_changes: true}" filter is applied
* **Url**: api/products
* **Method**: GET
* **Data Params**: 
```
api_key: (string), Example: d28ab4cd79d9cbb75467c267614f0266d2220b4f,
```
```
"filter": {
        "customer": (integer),
        "customer_name": (string),
        "field_filters": (array),
        "changed": (boolean),
        "status": (integer),
        "changes_status": (array),
        "no_longer_available": (integer),
        "image_status": (integer),
        "with_category": (boolean),
        "product_list": (array),
        "exclude_product_list": (array),
        "products": (array),
        "supplier": (integer),
        "ownership": (array),
        "compare_image_off": (boolean),
        "low_res_image": (boolean),
        "urls": (array),
        "start_date": (string),
        "end_date": (string),
        "media_count": (array),
        "count": (integer),
        "search": (array),
        "last_edit": (string),
        "completed_attributes": (integer),
        "columns": (integer),
        "categories_filter": (string),
        "category_id": (array),
        "attribute": (array),
        "visible_only_category": (boolean),
        "warnings": (string),
        "extra_review": (integer),
        "exclude_inla": (integer),
        "change_type": (integer),
        "changed_since_last_crawl": (string),
        "user_id": (integer),
        "brand": (array),
        "brand_type": (integer),
        "search": {
            "field": (string),
            "value": (mixed)
        }
    }
```
```
product: {
    apply_product_changes: (boolean)
}
http://elsa5.contentanalyticsinc.com/api/products?api_key=d28ab4cd79d9cbb75467c267614f0266d2220b4f&product[apply_product_changes]=true&limit=10
```

* **Sample Call**: 
```
api/products?api_key=d28ab4cd79d9cbb75467c267614f0266d2220b4f&filter[customer]=1&...
```
```
http://elsa5.contentanalyticsinc.com/api/products?api_key=d28ab4cd79d9cbb75467c267614f0266d2220b4f&filter[products][]=1925
```

* **Success Response**: 
```
{
  "total_products": {
    "count":"3",
    "low_res_images_count":"4",
    "site_owned":["3", "4", "491"],
    "in_store":[],
    "marketplace_owned":[]
  },

  "products":[{
    "id":"17944",
    "imported_data_id":"491",
    "product_list_id":"2",
    "product_name":null,
    "url":null,
    "price":"25.17",
    "currency":"USD",
    "description":null,
    "long_description":null,
    "shelf_description":null,
    "upc":"381371016761",
    "tool_id":null,
    "product_url_id":null,
    "created_date":"2015-02-24 18:27:03",
    "verified_date":"2016-12-19 19:53:51",
    "matched":"t",
    "approved":"f",
    "owned":"t",
    "image_urls": [
        "https:\/\/i5.walmartimages.com\/asr\/21c12827-978b-4745.jpeg",
        "http:\/\/tmeditor.dev\/product_uploaded_images\/4\/68105320995519ab33013e8e1077bdee.jpg"
    ]
    ...
  }],

  "all_products_id": ["3", "4", "491"]
}
```

* **Error Response**: 
```
{"code": 404, "message": "No products found.", "status": "error"}
```

* **Notes**: ***Ryan & Matt*** By default products and their changes are returned separately, unless "product: {apply_product_changes: true}" filter is applied, check 'image_urls' key in response for product images.

## Products Diff 

* **Title**: Get Products Diff
* **Description**: The product diff table is a true/false table that tells us which fields have differences. This call will find the list of all fields where the diff table value is true for each product, and return only the content which is different (submitting changes).
* **Url**: api/products/unmatched
* **Method**: GET
* **Sample Call**: 
```
api/products/unmatched?api_key=d28ab4cd79d9cbb75467c267614f0266d2220b4f
```
* **Success Response**: 
```
[
  {
    "new_images": [
      "http:\/\/tmeditor.loc\/product_uploaded_images\/4\/ebd0bc83b166f4a85143856168bdb5ba.jpg",
      "http:\/\/tmeditor.loc\/product_uploaded_images\/4\/87bf4de996bef9b6a4d787440378ace4.jpg"
    ],
    "product_name": "Product Name",
    "description": "<p><br><\/p><p>The Westboro Collection efdfgsdfgsfdgfortlessly combines modern designer style with superb functionality. Its rich Chestnut lacquered finish is water, stain and scratch resistant. This unit is multi-functional and can serve as a TV stand, coffee table or storage bench. Best of all, it coordinates with the entire Westboro Collection, making it easy to complete your look.<\/p><p>",
    "long_description": "Long Description", 
    "shelf_description": "Shelf Description", 
    "usage_directions": "<strong>9879<\/strong>",
    "ingredients": "<strong>Ingredients  qwerty<\/strong>",
    "url": "http:\/\/www.walmart.com\/ip\/5614471",
    "caution_warnings_allergens": "965465465",
    "bullet_feature": [
      "testOne 1.0 ounce packet of Hidden Valley Original Ranch Salad Dressing Seasoning Mix",
      "Helps you make tasty Original Ranch Salad Dressing in minutes",
      "Mix with black pepper for a pork chop or steak dry rub",
      "Stir into a bowl of mashed potatoes for a fun side dish",
      "Gluten-Free"
    ],
  }
]
```

* **Notes**: _This endpoint has no other applicable filters._

## Image Tags

* **Title**: Get Image Tags (MC developers only)
* **Description**: Returns image tags
* **Url**: api/products/images/tags
* **Method**: GET
* **URL Params**: productId, url
* **Sample Call**: 
```
api/products/images/tags?productId=11111&url=http://ca.com/dd18159afa8a36d19de6750ff1f625e2.jpg&api_key=d28ab4cd79d9cbb75467c267614f0266d2220b
```
* **Success Response**: 
```
{
    "selected": [
        {"name":"Samsung"},
        {"name":"Apple"}
    ],
    "preset": {
        "selected": [
            {"name":"Usage Rights"}
        ],
        "available": [
            {"name":"Drug Facts"},
            {"name":"Ingredients"},
            {"name":"Lifestyle"},
            {"name":"Out of Package"},
            {"name":"Main"},
            {"name":"Nutrition Facts"},
            {"name":"Side Back"},
            {"name":"Side Left"},
            {"name":"Side Right"},
            {"name":"Side Top"},
            {"name":"Side Bottom"},
            {"name":"Supplement Facts"}
        ]
    }
}
```

* **Error Response**: 
```
{"code":404,"message":"Image not found","status":"error"}
```

* **Notes**: _This endpoint has no other applicable filters._


## Image Tags

* **Title**: Get Image Tags (MC developers only)
* **Description**: Returns image tags
* **Url**: api/products/images/tags
* **Method**: POST

* **Request**: 
```
{ 
    "productId": "2528",    
    "imageUrl": "http://tmeditor.dev/product_uploaded_images/4/dd18159afa8a36d19de6750ff1f625e2.jpg",
    "keywordsTags": [
        {"name": "Samsung"}, 
        {"name": "Apple"}
    ],
    "typeTags": [
        {"name": "Usage Rights"}, 
        {"name": "Drug Facts"}
    ]
}
```

* **Error Response**: 
```
{"code":400,"message":"Bad request message","status":"error"}
```

* **Notes**: _This endpoint has no other applicable filters._

# Customer API Endpoints

## Approved Brands

* **Title**: Get customer (retailer) approved brands
* **Description**: Returns list of brands with aliases
* **Url**: api/customers/(:customer_id)/approved-brands
* **Method**: GET
* **URL Params**: customer_id (_CAID, internal customer ID_)
* **Sample Call**: 
```
api/customers/(:customer_id)/approved-brands?api_key=d28ab4cd79d9cbb75467c267614f0266d2220b4f
```
* **Success Response**: 
```
[
    {
        "brand": "Sams",
        "brand_alias": "Samsung"
    },
    {
        "brand": "SMSNG",
        "brand_alias": "Samsung"
    },
    {
        "brand": "Panas",
        "brand_alias": "Panasonic"
    },
    ...
]
```

* **Notes**: _This endpoint has no other applicable filters._

# Icebox

## Upload file by URL

* **Title**: Upload file by URL
* **Description**: Creates Icebox file from URL
* **Url**: api/icebox/file
* **Method**: POST

* **Sample Call**: 
```
api/icebox/file?api_key=d28ab4cd79d9cbb75467c267614f0266d2220b4f
```

* **POST parameters**: 
```
links[]
```

* **Success Response**: 
```
{
   "http://domain.com/611787231601.jpg":"http://ca-media.contentanalyticsinc.com/dev-test1/mc/ice-box/4/611787231601.jpg",
   "http://domain.com/611787231602.jpg":"http://ca-media.contentanalyticsinc.com/dev-test1/mc/ice-box/4/611787231602.jpg"
}
```

* **Error Response**: 
```
{
    "code": 400,
    "message": "Request is empty",
    "status": "error"
}
```