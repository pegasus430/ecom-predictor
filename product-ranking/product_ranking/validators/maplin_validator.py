class MaplinValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['brand', 'limited_stock']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'special_pricing',
        'bestseller_rank', 'model', 'description'
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'sdfsdgdf': 0,  # should return 'no products' or just 0 products
        'benny benassi': 0,
        'red car': [20, 200],
        'stone': [50, 120],
        'ball': [5, 280],
        'rose': [10, 70],
        'long term black': [1, 12],
        'selling': [15, 50],
        'water proof': [50, 108],
        'long night': [30, 200],
    }

    test_urls = {

        'http://www.maplin.co.uk/p/nilfisk-multi-20t-1400w-20l-wet-and-dry-vacuum-cleaner-230v-n46qh',
        'http://www.maplin.co.uk/p/car-vacuum-12v-wet-and-dry-r01wl',
        'http://www.maplin.co.uk/p/telescopic-window-cleaner-n57df',
        'http://www.maplin.co.uk/p/kitsound-evoke-21-wireless-bluetooth-speaker-n08eb',
        'http://www.maplin.co.uk/p/dewalt-d21570k-127mm-dry-diamond-drill-2-speed-1300-watt-230-volt-r37hh',
        'http://www.maplin.co.uk/p/first-alert-600g-dry-powder-fire-extinguisher-n27qg',
        'http://www.maplin.co.uk/p/marcrist-pg750x-dry-diamond-tile-drill-8mm-r31gq',
        'http://www.maplin.co.uk/p/milwaukee-dd-2-160xe-diamond-drill-162mm-capacity-dry-1500-watt-240-volt-r37hk',
    }