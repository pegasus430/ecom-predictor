class AmazoncnValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['model', 'brand', 'price',
                       'buyer_reviews']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'description', 'special_pricing', 'category',
        'bestseller_rank',
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = True  # ... duplicated requests?
    ignore_log_filtered = True  # ... filtered requests?
    test_requests = {
        'abrakadabrasdafsdfsdf': 0,  # should return 'no products' or just 0 products
        'adfhsadifgewrtgujoc2': 0,
        'iphone duos': [5, 175],
        'gold shell': [50, 200],
        'Led Tv screen': [20, 200],
        'told help': [5, 150],
        'crawl': [50, 400],
        'sony playstation 4': [50, 200],
        'store data all': [20, 300],
        'iphone stone': [40, 250]
    }

test_urls = {
    'http://www.amazon.cn/P-Young-%E6%9D%A8%E5%9F%94-%E9%9F%A9%E7%89%88%E6%97%B6%E5%B0%9A%E4%BF%AE%E8%BA%AB%E7%BA%AF%E8%89%B2%E6%89%93%E5%BA%95%E8%A3%99%E5%AD%90-%E5%9C%86%E9%A2%86%E5%A5%B3%E5%BC%8FA%E5%AD%97%E8%A3%99%E9%95%BF%E8%A2%96%E4%BC%91%E9%97%B2%E8%BF%9E%E8%A1%A3%E8%A3%99-2262-%E7%8E%AB%E7%BA%A2%E8%89%B2-XL%E7%A0%81/dp/B015MLR3ME/ref=sr_1_14?ie=UTF8&qid=1444398901&sr=8-14&keywords=dress'
    'http://www.amazon.cn/CLEAR%E6%B8%85%E6%89%AC%E7%94%B7%E5%A3%AB%E5%A5%97%E8%A3%85/dp/B00JP8GVWE/ref=sr_1_1?ie=UTF8&qid=1444637856&sr=8-1&keywords=clear',
    'http://www.amazon.cn/Helen-Harper-%E6%B5%B7%E4%BC%A6%E5%93%88%E4%BC%AF%E5%B9%B2%E7%88%BD-4-9KG-%E8%B6%85%E8%96%84%E6%97%A5%E7%94%A8%E7%BA%B8%E5%B0%BF%E8%A3%A4M%E7%A0%8114%E7%89%87%E8%A3%85/dp/B00IQNXT1U/ref=pd_sim_sbs_75_4?ie=UTF8&refRID=1S2JF6MBX80DM2HK659A&dpID=41%2Byzz%2BSzPL&dpSrc=sims&preST=_AC_UL160_SR160%2C160_',
    'http://www.amazon.cn/DRESS-%E5%90%89%E6%B0%8F-%E8%B6%85%E8%96%84%E8%B6%85%E6%9F%94%E8%BD%AF%E5%A9%B4%E5%84%BF%E7%BA%B8%E5%B0%BF%E7%89%87S%E5%8F%B766%E7%89%87/dp/B00VR64EU8/ref=sr_1_22?ie=UTF8&qid=1444645492&sr=8-22&keywords=dress',
    'http://www.amazon.cn/ZtuntZ-Skateboards-Texas-License-Plate-Grom-Park-Skateboard-Deck-Black-White/dp/B00MGJVE1W/ref=sr_1_5?ie=UTF8&qid=1446199538&sr=8-5&keywords=grom',
    'http://www.amazon.cn/%E6%B3%B0%E5%8B%92%E2%80%A2%E5%8F%B2%E8%96%87%E8%8A%99%E7%89%B9-1989/dp/B00QWC2HB0/ref=sr_1_5?ie=UTF8&qid=1446199581&sr=8-5&keywords=red',
    'http://www.amazon.cn/Fekkai-Full-Blown-Volume-Shampoo-16-Fluid-Ounce/dp/B00OE34Q5Y/ref=sr_1_9?ie=UTF8&qid=1446199629&sr=8-9&keywords=shampoo',
    'http://www.amazon.cn/%E5%A4%A7%E6%B4%97%E7%89%8C-%E5%85%A8%E7%90%83%E9%87%91%E8%9E%8D%E7%A7%A9%E5%BA%8F%E6%9C%80%E5%90%8E%E8%A7%92%E5%8A%9B-%E8%8D%B7-%E7%B1%B3%E5%8D%AB%E5%87%8C/dp/B016HUEJJY/ref=sr_1_11?ie=UTF8&qid=1446199680&sr=8-11&keywords=big',
}