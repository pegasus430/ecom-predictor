class KohlsValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['brand', 'description']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'special_pricing', 'ranking',
        'bestseller_rank', 'model', 'image_url'
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'sdfsdgdf': 0,  # should return 'no products' or just 0 products
        'benny benassi': 0,
        'red jeans': [30, 100],
        'black stone': [50, 250],
        'red ball': [100, 300],
        'green jersey': [10, 130],
        'long term red': [1, 80],
        'yellow ion': [15, 100],
        'water ball': [1, 85],
        'levis 511': [10, 100],
    }

    test_urls = {

        'http://www.kohls.com/product/prd-2201224/chaps-surplice-faux-wrap-dress-womens.jsp?color=Heirloom%20Teal',
        'http://www.kohls.com/product/prd-2244381/chaps-georgette-empire-evening-gown-womens.jsp?color=Black',
        'http://www.kohls.com/product/prd-1992187/Plus-Size-Tek-Gear--Shirred-Fitness-Dress.jsp?pfm=bd-productnotavailable',
        'http://www.kohls.com/product/prd-2206901/simply-vera-vera-wang-print-shift-dress-womens.jsp?color=Diva%20A',
        'http://www.kohls.com/product/prd-2040118/chaps-surplice-drape-front-full-length-dress-womens.jsp?color=Lakehouse%20Red',
        'http://www.kohls.com/product/prd-2154997/tek-gear-womens-puff-winter-boots.jsp?color=Fuchsia',
        'http://www.kohls.com/product/prd-2213360/urban-pipeline-solid-thermal-tee-men.jsp?color=Charcoal%20Heather',
    }