class WalmartValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['model', 'brand', 'description', 'recent_questions',
                       'related_products', 'upc', 'buyer_reviews', 'price']
    ignore_fields = ['google_source_site', 'is_in_store_only', 'bestseller_rank',
                     'is_out_of_stock']
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = False  # ... duplicated requests?
    ignore_log_filtered = False  # ... filtered requests?
    test_requests = {
        'abrakadabrasdafsdfsdf': 0,  # should return 'no products' or just 0 products
        'nothing_found_123': 0,
        'vodka': [50, 600],
        'white lipton tea': [50, 150],
        'trimming cat': [5, 50],
        'waterpik': [10, 150],
        'hexacore video': [5, 100],
        'Midwest Cat': [10, 250],
        'muay pads': [3, 50],
        '14-pack': [1, 100],
        'voltmeter': [50, 250]
    }

    test_urls = {
        'http://www.walmart.com/ip/George-Women-s-Surplice-Long-Sleeve-Wrap-Dress/45456935',
        'http://www.walmart.com/ip/Clean-Clear-R-Foaming-Facial-Cleanser-Sensitive-Skin-Cleansers-8-Fl-Oz/10801463',
        'http://www.walmart.com/ip/Atkins-Endulge-Peanut-Butter-Cups-5ct/11028012?action=product_interest&action_type='
        'title&item_id=11028012&placement_id=irs-2-m3&strategy=PWVUB&visitor_id&category=&client_guid='
        '7a8b77ee-6f4a-48a0-b0b5-4eedc0ce6983&customer_id_enc&config_id=2&parent_item_id=11028011&parent_anchor_item_id='
        '11028011&guid=9e227f42-cb31-4451-85b6-29137ca949f5&bucket_id=irsbucketdefault&beacon_version=1.0.1&findingMethod=p13n',
        'http://www.walmart.com/ip/Atkins-Day-Break-Strawberry-Banana-Shakes-4ct/16401683',
        'http://www.walmart.com/ip/Netgear-N150-Wireless-Router/11084824',
        'http://www.walmart.com/ip/Premiertek-PowerLink-Wireless-802.11b-g-n-USB-2.0-Adapter/16480821',
        'http://www.walmart.com/ip/Edimax-EW-7811Un-150Mbps-Wireless-11n-Nano-Size-USB-Adapter/17419471?action='
        'product_interest&action_type=title&item_id=17419471&placement_id=irs-2-m3&strategy=PWVUB&visitor_id&category=&'
        'client_guid=09497ab6-94be-49b9-bceb-9d767cae8a55&customer_id_enc&config_id=2&'
        'parent_item_id=16480821&parent_anchor_item_id=16480821&guid=4456fc5b-0c63-41e1-be48-00ec0385c791&bucket_id=irsbucketdefault&beacon_version=1.0.1&findingMethod=p13n',


    }