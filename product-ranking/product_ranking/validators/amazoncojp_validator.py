class AmazoncojpValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['model', 'brand', 'price', 'bestseller_rank',
                       'buyer_reviews']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'description', 'special_pricing'
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'abrakadabrasdafsdfsdf': 0,  # should return 'no products' or just 0 products
        'alhpa beta vinigretto': 0,
        'dandy united': [30, 300],
        'magi yellow': [5, 150],
        'Led Tv screen': [40, 300],
        'red ship coat': [10, 150],
        'trash smash': [20, 250],
        'all for PC now': [15, 150],
        'iphone blast': [10, 200],
        'genius electronics black': [5, 120],
        'batteries 330v': [40, 270]
    }

    test_urls = {

        'http://www.amazon.co.jp/DRESS-%E3%83%89%E3%83%AC%E3%82%B9-2015%E5%B9%B4-11-%E6%9C%88%E5%8F%B7/dp/B014TC1J4A/ref=sr_1_2?ie=UTF8&qid=1446199786&sr=8-2&keywords=dress',
        'http://www.amazon.co.jp/RED%E3%83%AA%E3%82%BF%E3%83%BC%E3%83%B3%E3%82%BA-DVD-%E3%83%96%E3%83%AB%E3%83%BC%E3%82%B9%E3%83%BB%E3%82%A6%E3%82%A3%E3%83%AA%E3%82%B9/dp/B00S5E5W0G/ref=sr_1_6?ie=UTF8&qid=1446199854&sr=8-6&keywords=red',
        'http://www.amazon.co.jp/HISTORY-ALBUM-1989-2014~25-PEACETIME-BOOM~%E3%80%90%E3%83%97%E3%83%AC%E3%83%9F%E3%82%A2%E3%83%A0%E7%9B%A4%E3%80%91/dp/B00M0FK7W4/ref=sr_1_2?ie=UTF8&qid=1446199917&sr=8-2&keywords=boom',
        'http://www.amazon.co.jp/BELL-%E3%83%99%E3%83%AB-ZOOM-%E3%82%BA%E3%83%BC%E3%83%A0-%E3%83%96%E3%83%AB%E3%83%BC%E3%83%88%E3%83%A9%E3%83%83%E3%82%AF%E3%82%B9/dp/B001FSKT3E/ref=sr_1_2?ie=UTF8&qid=1446200050&sr=8-2&keywords=bell',
        'http://www.amazon.co.jp/%E3%82%A4%E3%83%B3%E3%82%B5%E3%82%A4%E3%83%89%E3%83%98%E3%83%83%E3%83%89-%E3%83%98%E3%83%83%E3%83%89%E3%83%93%E3%83%B3%E3%83%9C%E3%83%B3-Funko-Disney-Pixar/dp/B0100QF9YK/ref=sr_1_12?ie=UTF8&qid=1446200143&sr=8-12&keywords=bong',
        'http://www.amazon.co.jp/%E7%86%8A%E9%87%8E%E6%B2%B9%E8%84%82-%E9%A6%AC%E6%B2%B9%E3%82%B7%E3%83%A3%E3%83%B3%E3%83%97%E3%83%BC-%E8%A9%B0%E3%82%81%E6%9B%BF%E3%81%88%E7%94%A8-500ml/dp/B00812NK0G/ref=sr_1_4?ie=UTF8&qid=1446200595&sr=8-4&keywords=shampoo',
        'http://www.amazon.co.jp/Nudie-Jeans-BLACK-28inch-%E3%83%80%E3%83%BC%E3%82%AF%E3%82%B0%E3%83%AC%E3%83%BC/dp/B00W104IFK/ref=sr_1_4?ie=UTF8&qid=1446201095&sr=8-4&keywords=jeanse',
    }