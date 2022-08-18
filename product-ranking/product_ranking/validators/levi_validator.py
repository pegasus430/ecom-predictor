class LeviValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['brand', 'price',
                       'related_products', 'upc']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock',
        'google_source_site', 'description', 'special_pricing',
        'bestseller_rank', 'img_count', 'video_count'
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'sdfsdgdf': 0,  # should return 'no products' or just 0 products
        'benny benassi': 0,
        'make': [50, 300],
        'men tee': [10, 150],
        'green shirt': [10, 60],
        'red jacket': [20, 100],
        'coat': [7, 150],
        'shoes': [1, 100],
        'bool cut': [10, 150],
        'hat': [5, 50],
    }

test_urls = {
        'http://www.levi.com/US/en_US/womens-jeans/p/155160131',
        'http://www.levi.com/US/en_US/womens-jeans/p/198360003',
        'http://www.levi.com/US/en_US/womens-jeans/p/327820001',
        'http://www.levi.com/US/en_US/womens-jeans/p/196320013',
        'http://www.levi.com/US/en_US/mens-jeans/p/055274010'

    }