class AsdaValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['brand', 'image_url']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'description', 'special_pricing',
        'bestseller_rank',
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'qlkjwehjqwdfahsdfh': 0,  # should return 'no products' or just 0 products
        '!': 0,
        'eat': [20, 150],
        'dress': [2, 40],
        'red pepper': [10, 80],
        'chilly pepper': [5, 130],
        'breakfast': [70, 1000],
        'vodka': [30, 150],
        'water proof': [10, 100],
        'sillver': [70, 190],
    }

    test_urls = {
        'http://groceries.asda.com/product/semi-skimmed-milk/asda-fresh-milk-semi-skimmed/20504',
        'http://groceries.asda.com/product/semi-skimmed-milk/asda-fresh-milk-semi-skimmed/23423',
        'http://groceries.asda.com/product/thin-pizza/asda-chosen-by-you-extra-thin-crispy-ham-pineapple-pizza/910001906209',
        'http://groceries.asda.com/product/thin-pizza/goodfellas-stonebaked-thin-meatball-marinara-pizza/910001904475',
        'http://groceries.asda.com/product/thin-pizza/goodfellas-stonebaked-extra-thin-vegetable-goats-cheese-pizza/910001174716',
        'http://groceries.asda.com/product/canned-ciders/strongbow-cloudy-apple-cider/910002079201',
        'http://groceries.asda.com/product/canned-ciders/blackthorn-cider/910001158269',
        'http://groceries.asda.com/product/canned-ciders/hawksridge-cider/910001801592',
    }