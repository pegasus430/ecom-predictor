class AmazoncaValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['model', 'brand', 'description', 'price', 'bestseller_rank']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'buyer_reviews', 'google_source_site', 'special_pricing',
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = False  # ... duplicated requests?
    ignore_log_filtered = False  # ... filtered requests?
    test_requests = {
        'abrakadabrasdafsdfsdf': 0,  # should return 'no products' or just 0 products
        'nothing_found_1234654654': 0,
        'yellow toaster 2 slice': [2, 10],
        'kaspersky total': [3, 50],
        'learn python the hard way': [2, 10],
        'yamaha drums midi': [5, 100],
        'black men shoes size 8 red': [5, 300],
        'yellow laptop case 10': [100, 500],
        'apple ipod nano gold': [50, 300],
        'programming product best': [5, 100],
    }

test_urls = {
    'http://www.amazon.ca/Vince-Camuto-Womens-Sleeve-Organza/dp/B00WMERBOA/ref=sr_1_4?ie=UTF8&qid=1444651527&sr=8-4&keywords=dress',
    'http://www.amazon.ca/Clean-Expanded-Alejandro-Junger-ebook/dp/B007MAU5UG/ref=sr_1_3?ie=UTF8&qid=1446197943&sr=8-3&keywords=clean',
    'http://www.amazon.ca/Red-Blu-ray-Digital-Copy-Bilingual/dp/B00F41OB5A/ref=sr_1_3?ie=UTF8&qid=1446198440&sr=8-3&keywords=red',
    'http://www.amazon.ca/Pura-dor-Prevention-Premium-Organic/dp/B0079R6BD2/ref=sr_1_2?ie=UTF8&qid=1446198963&sr=8-2&keywords=shampoo',
    'http://www.amazon.ca/MKM-APPS-Wifi-Password-Hacker/dp/B00KJNKRS8/ref=sr_1_2?ie=UTF8&qid=1446198494&sr=8-2&keywords=wifi',
    'http://www.amazon.ca/Levis-Womens-Perfectly-Slimming-Straight/dp/B00W6WOTW0/ref=sr_1_sc_2?ie=UTF8&qid=1446199052&sr=8-2-spell&keywords=jeanse',
    'http://www.amazon.ca/Opteka-OSG14-Universal-Honeycomb-External/dp/B004BFXBXI/ref=sr_1_4?ie=UTF8&qid=1446199112&sr=8-4&keywords=grid',
    'http://www.amazon.ca/CRF-950Z-2-Stage-Pitcher-Replacement-Filter/dp/B000067DZX/ref=sr_1_3?ie=UTF8&qid=1446199161&sr=8-3&keywords=pur',

}