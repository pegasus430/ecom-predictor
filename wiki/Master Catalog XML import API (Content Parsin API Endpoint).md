# Workflow:
## 1. Case: User Upload
* User uploads xml file from Master Catalog UI.
* New import process with status "Pending" is created.
* Submitting request to Python API, Example:

### HTTP METHOD GET
**Url: https://bulk-import.contentanalyticsinc.com:8888/parse**

Sample request:

```
{
    "token": "9fd1964dc4c983",
    "url": "http://sbohr.com/attachment.xml",
    "callback": "https://elsa4.contentanalyticsinc.com/api/import/products"
}
```

* Send request to MC API to move import process from "Pending" to "In Progress", example:

### HTTP METHOD PUT
**Url: https://elsa4.contentanalyticsinc.com/api/import**

Sample request:

```
{
    "token": "9fd1964dc4c983",
    "api_key": "810464318eb368cc707d0fb4f1113756111dab96",
    "status": 2
}
```

* Python parse file.
* Python send request to MC API, example:

### HTTP METHOD PUT
**Url: https://elsa4.contentanalyticsinc.com/api/import/products**

Sample request:

```
{
    "token": "9fd1964dc4c983",
    "api_key": "810464318eb368cc707d0fb4f1113756111dab96",
    "products": [
        {
            "id_type": "upc",
            "id_value": "022700097746",
            "product_name": "Test Product Name Updated From API",
            "description": "Test Description Updated From API",
            "long_description": "Test Long Description Updated From API",
            "shelf_description": "Test Shelf Description Updated From API",
            "category" : {
                "name": "animal",
                "attributes" : {
                    "brand": "TestBrandNameUpdatedFromAPI"
                }
            },
            "common" : {
                "unitsPerConsumerUnit": "10",
                "countryOfOriginAssembly": "AM",
            },
            "images": {
                "https://images-na.ssl-images-amazon.com/images/I/71zvV6uibTL._SL1300_.jpg": 1,
                "https://images-na.ssl-images-amazon.com/images/I/61%2BtYhgtgwL._SX522_.jpg": 4
            }
        }
    ]
}
```

Sample response:

```
    {
        "total": 1,
        "failed": 0,
        "error_log": [],
        "token": "b1c2a5680c95c7f"
    }
```

// Please pay attention, new token is generated after each request, you should use newly generated token for multiple updates for same file and any other future actions on import processes.

* Once all import actions completed, Python API send request to mark import process as "Complete", example:

### HTTP METHOD PUT
**Url: https://elsa4.contentanalyticsinc.com/api/import**

Sample request:

```
{
    "token": "9fd1964dc4c983",
    "api_key": "810464318eb368cc707d0fb4f1113756111dab96",
    "status": 3
}
```

## 2. Case: Upload From FTP

* Send request to MC API to init new import process

### HTTP METHOD POST
**Url: https://elsa4.contentanalyticsinc.com/api/import**

Sample request:

```
{
    "api_key": "810464318eb368cc707d0fb4f1113756111dab96",
    "file_name": "http://sbohr.com/attachment.xml"
    "customer": "Master Data"
}
```

Sample response:
```
{
    "token": "9fd1964dc4c983"
}
```

* Python send request to MC API, example:

### HTTP METHOD PUT
**Url: https://elsa4.contentanalyticsinc.com/api/import/products**

Sample request:

```
{
    "token": "9fd1964dc4c983",
    "api_key": "810464318eb368cc707d0fb4f1113756111dab96",
    "products": [
        {
            "id_type": "upc",
            "id_value": "022700097746",
            "product_name": "Test Product Name Updated From API",
            "description": "Test Description Updated From API",
            "long_description": "Test Long Description Updated From API",
            "shelf_description": "Test Shelf Description Updated From API",
            "category" : {
                "name": "animal",
                "attributes" : {
                    "brand": "TestBrandNameUpdatedFromAPI"
                }
            }
        }
    ]
}
```

Sample response:

```
    {
        "total": 1,
        "failed": 0,
        "error_log": [],
        "token": "b1c2a5680c95c7f"
    }
```

// Please pay attention, new token is generated after each request, you should use newly generated token for multiple updates for same file and any other future actions on import processes.

* Once all import actions completed, send request to mark import process as "Complete", example:

### HTTP METHOD PUT
**Url: https://elsa4.contentanalyticsinc.com/api/import**

Sample request:

```
{
    "token": "9fd1964dc4c983",
    "api_key": "810464318eb368cc707d0fb4f1113756111dab96",
    "status": 3
}
```

## 3. Available statuses

1. PENDING
2. IN_PROGRESS
3. SUCCESS
4. FAILED