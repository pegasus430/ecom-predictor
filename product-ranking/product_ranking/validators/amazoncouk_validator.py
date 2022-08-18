class AmazoncoukValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
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
        'msi graphic cards twin': [5, 150],
        'kaspersky total': [5, 70],
        'gold sold fold': [5, 200],  # spider should return from 5 to 200 products
        'yamaha drums midi': [5, 100],
        'black men shoes size 8 red stripes': [5, 80],
        'antoshka': [5, 200],
        'apple ipod nano sold': [100, 300],
        'avira 2': [20, 300],
    }

    test_urls = {

        'http://www.amazon.co.uk/WOMEN-SLEEVE-TARTAN-SWING-FLARED/dp/B00NE6XKC2/ref=sr_1_4?ie=UTF8&qid=1446201186&sr=8-4&keywords=dress',
        'http://www.amazon.co.uk/R%C3%A9my-Martin-Fine-Champagne-Cognac/dp/B003ZINCGS/ref=sr_1_1?ie=UTF8&qid=1446201421&sr=8-1&keywords=brandy',
        'http://www.amazon.co.uk/Lucy-Bee-Virgin-Organic-Coconut/dp/B00BS9JGK2/ref=zg_bs_grocery_3',
        'http://www.amazon.co.uk/Barratt-Original-Milk-Teeth-gram/dp/B005MJX5C4/ref=sr_1_1?s=grocery&ie=UTF8&qid=1446201706&sr=1-1&keywords=teeth',
        'http://www.amazon.co.uk/Vampire-Teeth-1-kilo-bag/dp/B004701W1A/ref=sr_1_5?s=grocery&ie=UTF8&qid=1446201706&sr=1-5&keywords=teeth',
        'http://www.amazon.co.uk/Lilys-Kitchen-Organic-Fish-Dinner/dp/B005VBPA9E/ref=sr_1_1?s=grocery&ie=UTF8&qid=1446201848&sr=1-1&keywords=dinner',
        'http://www.amazon.co.uk/Doves-Farm-Gluten-Brown-Bread/dp/B006MVUP7Y/ref=sr_1_2?s=grocery&ie=UTF8&qid=1446201908&sr=1-2-spons&keywords=bread+flour&psc=1'

    }