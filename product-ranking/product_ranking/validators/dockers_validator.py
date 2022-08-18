class DockersValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['brand', 'price']
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
        'jeans': [20, 150],
        'red': [20, 150],
        'black': [50, 300],
        'green': [10, 110],
        'blue jeans': [5, 150],
        'black shoes': [10, 100],
        'black fit': [20, 150],
        'leather': [20, 200],
    }

test_urls = {
        'http://www.dockers.com/US/en_US/mens-pants/p/471870008',
        'http://www.dockers.com/US/en_US/mens-pants/p/469650006',
        'http://www.dockers.com/US/en_US/mens-pants/p/469670006',
        'http://www.dockers.com/US/en_US/mens-pants/p/478600005',
        'http://www.dockers.com/US/en_US/mens-pants/p/462350002'

    }