# SC '_variants_' field

# Description
'variants' field is a list of variants of type 'dict' (order doesn't matter)

# Variant fields description
- __in_stock__ -- availability status -> bool or None
    - if variant in stock --> True
    - else --> False
- __price__ -- current price (e.g. discount price) -> float or NoneType
    - if price is undefined --> None
- __url__ -- url address of variant -> str
- __upc__ -- Universal Product Code -> str or NoneType
    - if upc is undefined --> None
- __properties__ -- a dict of variant attributes -> dict
    - keys (lower case) and values -> str
- __selected__ -- indication of selected variant -> bool
     - if variant selected --> True
     - else --> False
- __image_url__ -- url of variant image -> str or NoneType
- __colorid__ -- id of variant color -> str or NoneType
- __unavailable__ -- walmart only -> bool or NoneType
- __skuId__ -- -> bool or NoneType  
- __stock__ -- quantity of variant products in stock -> int


# Variant example
```python
{
    'in_stock': False,
    'price': None,
    'properties': {
        'color': u'Jukebox',
        'length': u'32',
        'waist': u'27'
    },
    'upc': None,
    'url': u'http://www.levi.com/US/en_US/mens-jeans/p/288330040'
}
```