class JcpenneyValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = []
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'description', 'special_pricing',
        'bestseller_rank', 'model', 'ranking',
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'sdfsdgdf': 0,  #+ should return 'no products' or just 0 products
        'benny benassi': 0,
        'green skirt': [10, 60],
        'peace': [10, 70],
        'hot': [100, 300],
        'drink': [30, 130],
        'term': [30, 130],
        'tiny': [10, 80],
        'golden': [20, 100],
        'night': [40, 190],
    }

    test_urls = {
        'http://www.jcpenney.com/levis-560-comfort-fit-jeans/prod.jump?ppId=17b993c&searchTerm=jeans&catId=SearchResults&_dyncharset=UTF-8&colorizedImg=0900631B8171BF44M.tif',
        'http://www.jcpenney.com/levis-515-bootcut-jeans/prod.jump?ppId=pp5001450019&searchTerm=jeans&catId=SearchResults&_dyncharset=UTF-8&colorizedImg=DP0326201517013016M.tif',
        'http://www.jcpenney.com/arizona-basic-slim-straight-jeans/prod.jump?ppId=pp5001340400&searchTerm=jeans&catId=SearchResults&_dyncharset=UTF-8&colorizedImg=DP0213201523431382M.tif',
        'http://www.jcpenney.com/studio-1-34-sleeve-striped-sweater-dress/prod.jump?ppId=pp5006120073&N=4294966491&searchTerm=dresses&N=4294966491&catId=SearchResults&_dyncharset=UTF-8&colorizedImg=DP0918201517011052M.tif',
        'http://www.jcpenney.com/studio-1-34-sleeve-striped-sweater-dress/prod.jump?ppId=pp5006120070&N=4294966491&searchTerm=dresses&N=4294966491&catId=SearchResults&_dyncharset=UTF-8&colorizedImg=DP0921201517044857M.tif',
        'http://www.jcpenney.com/jessica-howard-long-sleeve-striped-sweater-dress-petite/prod.jump?ppId=pp5005940585&cmvc=JCP|SearchResults|RICHREL&grView=&eventRootCatId=&currentTabCatId=&regId=&rrplacementtype=item_page.dpcontent3',
        'http://www.jcpenney.com/rn-studio-by-ronni-nicole-34-sleeve-striped-shift-dress/prod.jump?ppId=pp5005960464&cmvc=JCP|SearchResults|RICHREL&grView=&eventRootCatId=&currentTabCatId=&regId=&rrplacementtype=item_page.dpcontent3',
        'http://www.jcpenney.com/danny-nicole-elbow-sleeve-print-scuba-sheath-dress/prod.jump?ppId=pp5005940455&cmvc=JCP|SearchResults|RICHREL&grView=&eventRootCatId=&currentTabCatId=&regId=&rrplacementtype=item_page.dpcontent3',
    }