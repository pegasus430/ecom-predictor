class BoxedValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = [
        'price', 'related_products', 'price_original'
    ]
    ignore_fields = [
        'no_longer_available', 'is_out_of_stock', 'description', 'model', 'variants'
    ]
    ignore_log_errors = True  # don't check logs for errors?
    ignore_log_duplications = False  # ... duplicated requests?
    ignore_log_filtered = False  # ... filtered requests?
    test_requests = {
        'abrakadabra': 0,  # should return 'no products' or just 0 products
        'santa claus': 0,
        'coffee': [30, 70],
        'water': [20, 70],
        'dish soap': [0, 20],
        'wine': [15, 50]
    }

    test_urls = {
            'https://www.boxed.com/product/1742/strawberries-4-lbs./',
            'https://www.boxed.com/product/199/njoy-coffee-creamer-16-oz./',
            'https://www.boxed.com/products/search/coffee/page/1',
            'https://www.boxed.com/product/2556/dove-cool-moisture-beauty-bar-14-x-4-oz.-cucumber-green-tea/'
    }
