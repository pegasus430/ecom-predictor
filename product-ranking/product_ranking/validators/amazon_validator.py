class AmazonValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['model', 'brand', 'price', 'bestseller_rank',
                       'buyer_reviews']

    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'description', 'special_pricing'
    ]
    # these fields will be ignored (in addition) when the scraper runs
    # in the product url mode
    extra_ignore_fields_for_product_urls = [
        'model', 'bestseller_rank'
    ]

    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'abrakadabrasdafsdfsdf': 0,  # should return 'no products' or just 0 products
        'nothing_found_1234654654': 0,
        'zollinger atlas of surgical operations': [10, 50],
        'assassins creed golden edition': [40, 380],
        'ceiling fan industrial white system': [100, 400],
        'kaspersky total': [20, 150],
        'car navigator garmin maps 44LM': [1, 20],
        'yamaha drums midi': [50, 300],
        'black men shoes size 8  red stripes': [150, 500],
        'equalizer pioneer': [100, 400]
    }

    test_urls = [
        'https://www.amazon.com/Pioneer-TSW311S4-12-Inch-Champion-Equalizer/dp/B00O8B7BAO/',
        'http://www.amazon.com/pediped-Flex-Ann-Mary-Jane/dp/B00RY8466U/',
        'http://www.amazon.com/gp/product/B0083KGXGY/',
        'https://www.amazon.com/LG-Electronics-55LB6300-55-Inch-1080p/dp/B00II6VW3M/',
        'http://www.amazon.com/Sierra-Tools-Battery-Operated-Liquid-Transfer/dp/B000HEBR3I/ref=lp_15707701_1_20?s=automotive&ie=UTF8&qid=1439192599&sr=1-20',
        'http://www.amazon.com/Toddler-Pillow-13-Hypoallergenic-Guarantee/dp/B00KDKKD1I/ref=lp_1057794_1_20?s=furniture&ie=UTF8&qid=1439193230&sr=1-20',
        'http://www.amazon.com/gp/product/B00PHNE4X4/',
        'http://www.amazon.com/Calvin-Klein-Jeans-Medium-30x32/dp/B014EEIHPC',
        'http://www.amazon.com/gp/product/B00BXKET7Q/',
        'https://www.amazon.com/dp/B00MJMV0GU/'
    ]

    def __init__(self, *args, **kwargs):
        # if we're in "product_url" mode - exclude "model" and "bestseller_rank" from
        product_url = getattr(kwargs['spider_class'], 'product_url', None)
        if product_url:
            self.ignore_fields.extend(self.extra_ignore_fields_for_product_urls)
