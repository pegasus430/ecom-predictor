class AmazonDeValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['model', 'brand', 'price', 'buyer_reviews', 'image_url']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'description', 'special_pricing', 'bestseller_rank'
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = False  # ... duplicated requests?
    ignore_log_filtered = False  # ... filtered requests?
    test_requests = {
        'abrakadabrasdafsdfsdf': 0,  # should return 'no products' or just 0 products
        'nothing_found_1234654654': 0,
        'dress code style all': [5, 70],
        'water pump bronze': [2, 70],
        'ceiling fan industrial': [5, 90],
        'kaspersky total': [30, 250],
        'car navigator garmin': [5, 100],
        'yamaha drums midi': [2, 50],
        'black men shoes size 8 red': [5, 70],
        'car audio equalizer pioneer': [100, 600]
    }

    test_urls = {
        'http://www.amazon.de/gp/product/B0013PUS26/ref=s9_simh_gw_p241_d9_i2?pf_rd_m=A3JWKAKR8XB7XF&pf_rd_s=desktop-1&pf_rd_r=0SZC4ZDZKMNPNBFK95TA&pf_rd_t=36701&pf_rd_p=585296347&pf_rd_i=desktop',
        'http://www.amazon.de/TOSKANA-BRAUT-Brautjungfern-Abendkleider-Ballkleider-36-Silber/dp/B00UOSDZUU/ref=sr_1_4?s=apparel&ie=UTF8&qid=1446202127&sr=1-4&keywords=dress',
        'http://www.amazon.de/TRIXES-3mm-10-schwarzer-Ohrdehner-Set-Dehnstab/dp/B00DGRG5JE/ref=sr_1_4?s=apparel&ie=UTF8&qid=1446202197&sr=1-4&keywords=digi',
        'http://www.amazon.de/Levis-Herren-Original-Straight-Carson/dp/B00LPGAV0M/ref=sr_1_2?s=apparel&ie=UTF8&qid=1446202245&sr=1-2&keywords=jeans',
        'http://www.amazon.de/GOGGLE-BRILLE-SCHWARZ-OFFROAD-MOTOCROSS/dp/B00M9LE04K/ref=sr_1_19?s=apparel&ie=UTF8&qid=1446202291&sr=1-19&keywords=cross',
        'http://www.amazon.de/Maxomorra-Fleece-Winterm%C3%BCtze-Apple-Tree/dp/B013UQXE8A/ref=sr_1_2?s=apparel&ie=UTF8&qid=1446202339&sr=1-2&keywords=tree',
        'http://www.amazon.de/BOSS-Hugo-Boss-Herren-Geschenkset/dp/B00XJU9PYK/ref=sr_1_10?m=A3JWKAKR8XB7XF&s=apparel&ie=UTF8&qid=1446202398&sr=1-10',

    }