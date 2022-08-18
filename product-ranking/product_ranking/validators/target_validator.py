class TargetValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['brand', 'price']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'description', 'special_pricing', "model",
        "bestseller_rank",
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'abrakadabrasdafsdfsdf': 0,  # should return 'no products' or just 0 products
        'nothing_found_1234654654': 0,
        'red stone': [15, 150],
        'cola': [60, 210],
        'vacation': [50, 175],
        'search book': [7, 170],
        'navigator': [10, 110],
        'manager': [15, 130],
        'IPhone-6': [1, 50],
        'air conditioner': [5, 170],
    }

    test_urls = {
        'http://intl.target.com/p/crafted-by-lee-men-s-slim-fit-jeans-medium-blue-stretch/-/A-50193843#prodSlot=large_1_1',
        'http://www.target.com/p/oster-microwave-oven-red/-/A-17279251#prodSlot=medium_1_16',
        'http://www.target.com/p/panasonic-silver-1-2-cu-ft-microwave-oven/-/A-14045881#prodSlot=medium_1_25',
        'http://www.target.com/p/sunbeam-microwave-0-9-cu-ft-black/-/A-13288321#prodSlot=medium_1_6',
        'http://www.target.com/p/women-s-sleeveless-easy-waist-dress-mossimo-supply-co-junior-s/-/A-16716172?lnk=rec|pdp|viewed_bought|pdp404h2',
        'http://www.target.com/p/women-s-woven-skater-dress-mossimo-supply-co/-/A-21442655?lnk=rec|pdp|viewed_bought|pdp404h2'

    }