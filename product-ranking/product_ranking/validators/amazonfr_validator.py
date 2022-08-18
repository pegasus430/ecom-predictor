class AmazonfrValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
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
        'nothing_found_1234654654': 0,
        'samsung t9500 battery 2600 li-ion warranty': [5, 175],
        'water pump mini': [5, 150],
        'ceiling fan industrial white system': [5, 50],
        'kaspersky total': [5, 75],
        'car navigator garmin maps 44LM': [1, 30],
        'yamaha drums midi': [1, 300],
        'black men shoes size 8 red': [20, 200],
        'car audio equalizer': [5, 150]
    }

    test_urls = {
        'http://www.amazon.fr/gp/product/B0114DA5XS/ref=s9_simh_gw_p193_d10_i3?pf_rd_m=A1X6FK5RDHNB96&pf_rd_s=desktop-1&pf_rd_r=0P8MKW77PCWS1T8EB5JJ&pf_rd_t=36701&pf_rd_p=577191447&pf_rd_i=desktop',
        'http://www.amazon.fr/CRAVOG-V-Neck-Backless-Evening-Pleated/dp/B00WHJKUN4/ref=sr_1_1?s=apparel&ie=UTF8&qid=1446202565&sr=1-1&keywords=dress',
        'http://www.amazon.fr/Desigual-Malta-Neograb-port%C3%A9-main/dp/B00VCAVO0W/ref=lp_7002798031_1_2?s=shoes&ie=UTF8&qid=1446202630&sr=1-2',
        'http://www.amazon.fr/Desigual-Rotterdam-Neograb-port%C3%A9-%C3%A9paule/dp/B00VEKBSTW/ref=pd_sim_sbs_309_1?ie=UTF8&dpID=51R7EG7G7zL&dpSrc=sims&preST=_AC_UL160_SR160%2C160_&refRID=0W6NPEJ6F81FGJ1ATKKC',
        'http://www.amazon.fr/dp/B00W4ZJEN8/ref=sr_1_1/ref=s9_acss_bw_cg_FRPUMA_5a1?_encoding=UTF8&ie=UTF8&keywords=Puma&qid=1441108714&s=shoes&sr=1-1&pf_rd_m=A1X6FK5RDHNB96&pf_rd_s=merchandised-search-top-2&pf_rd_r=1YGCEQDN312QY2FAY98V&pf_rd_t=101&pf_rd_p=702427967&pf_rd_i=7008270031',
        'http://www.amazon.fr/Bouba-Apple-Chaussures-Premiers-fille/dp/B00ZCPUPKI/ref=sr_1_1?s=shoes&ie=UTF8&qid=1446206671&sr=1-1&keywords=shoo+pom',
        'http://www.amazon.fr/Hom-10155035-Ensemble-Imprim%C3%A9-fabricant/dp/B00VTIJJ5O/ref=sr_1_1?s=apparel&ie=UTF8&qid=1446206841&sr=1-1',
    }