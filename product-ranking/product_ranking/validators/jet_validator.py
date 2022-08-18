class JetValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['brand', 'price', 'upc']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'model',
        'google_source_site', 'description', 'special_pricing',
        'bestseller_rank', 'img_count', 'video_count',
        'related_products'
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = False  # ... duplicated requests?
    ignore_log_filtered = False  # ... filtered requests?
    test_requests = {
        'sdfsdgdf': 0,  # should return 'no products' or just 0 products
        'benny45984596845benassi': 0,
        'black men long shirt': [50, 400],
        'woman green jacket': [50, 300],
        'sneakers': [10, 300],
        'red jacket': [100, 500],
        'green socks': [50, 300],
        'cotton socks': [50, 300],
        'black women socks': [50, 500],
        'orange hat': [50, 500],
    }

test_urls = {
        'https://jet.com/product/CornerStone-Mens-Enhanced-Visibility-Beanie-OSFA-Safety-Orange-Reflective/56e38f5479cd4ef3aaf4da6b00c7e846',
        'https://jet.com/product/CTMr-Unisex-Cotton-Solid-Unlined-Biker-Riding-Cap-Orange/8c2f430f7feb40f38abac700f4f46b2b',
        'https://jet.com/product/180250-MPH-400-CFM-12-Amp-Electric-High-Performance-Blower-Vacuum-and-Mulcher/08bc5525b95b4173be5b6b67cc503d0f',
        'https://jet.com/product/GreenWorks-25022-12-Amp-Corded-20-Mower/40f9b825d3d54bc4946bb3b46642c041',
        'https://jet.com/product/Karcher-25-QuickConnect-Replacement-Hose/258a74fc5c0f49ada1902968c7464c88'
    }