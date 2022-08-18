class MacysValidatorSettings(object):  # do NOT set BaseValidatorSettings as parent
    optional_fields = ['buyer_reviews']
    ignore_fields = [
        'is_in_store_only', 'is_out_of_stock', 'related_products', 'upc',
        'google_source_site', 'description', 'special_pricing', 'model',
        'bestseller_rank', 'brand'
    ]
    ignore_log_errors = False  # don't check logs for errors?
    ignore_log_duplications = False
    ignore_log_filtered = False
    test_requests = {
        'abrakadabrasdafsdfsdf': 0,  # should return 'no products' or just 0 products
        'nothing_found_1234654654': 0,
        'men green shirt': [50, 600],
        'extra large': [10, 100],
        'long sleeve red dress': [20, 300],
        'green socks': [20, 100],
        'levi white': [10, 100],
        'kid black shoes': [50, 300],
        'green men jeans': [5, 50],
        'red carpet': [50, 300]
    }

    test_urls = [
        'http://www1.macys.com/shop/product/e-live-from-the-red-carpet-e0045-evening-sandals?ID=770652&CategoryID=17570&LinkType=#fn=sp%3D1%26spc%3D202%26slotId%3D3%26kws%3Dred%20carpet',
        'http://www1.macys.com/shop/product/kenneth-mink-area-rug-set-roma-collection-3-piece-set-kerman-red?ID=657298&CategoryID=16905&LinkType=#fn=sp%3D1%26spc%3D202%26slotId%3D8%26kws%3Dred%20carpet',
        'http://www1.macys.com/shop/product/style-co.-curvy-fit-skinny-jeans-black-wash-only-at-macys?ID=2351352&CategoryID=3111&LinkType=#fn=sp%3D1%26spc%3D2731%26slotId%3D2%26kws%3Djeans',
        'http://www1.macys.com/shop/product/levis-541-athletic-fit-jeans?ID=1656539&CategoryID=11221&LinkType=#fn=sp%3D1%26spc%3D2731%26slotId%3D4%26kws%3Djeans',
        'http://www1.macys.com/shop/product/levis-541-athletic-fit-jeans?ID=1656539&CategoryID=11221&LinkType=#fn=sp%3D1%26spc%3D2762%26slotId%3D6%26kws%3Djeans',
        'http://www1.macys.com/shop/product/style-co.-skinny-leg-curvy-fit-jeans?ID=2132416&CategoryID=3111&LinkType=#fn=sp%3D1%26spc%3D2731%26slotId%3D18%26kws%3Djeans',
        'http://www1.macys.com/shop/product/charter-club-lexington-straight-leg-jeans-black-wash?ID=2147715&CategoryID=3111&LinkType=#fn=sp%3D1%26spc%3D2762%26slotId%3D20%26kws%3Djeans',
        'http://www1.macys.com/shop/product/style-co.-slim-leg-tummy-control-jeans-colored-wash?ID=1377210&CategoryID=3111&LinkType=#fn=sp%3D1%26spc%3D2762%26slotId%3D27%26kws%3Djeans',
        'http://www1.macys.com/shop/product/jessica-simpson-juniors-kiss-me-super-skinny-jeggings?ID=740695&CategoryID=28754&LinkType=#fn=sp%3D1%26spc%3D2762%26slotId%3D41%26kws%3Djeans',
        'http://www1.macys.com/shop/product/levis-511-line-8-slim-fit-black-3d-jeans?ID=1326541&CategoryID=11221&LinkType=#fn=sp%3D1%26spc%3D2762%26slotId%3D53%26kws%3Djeans',
        'http://www1.macys.com/shop/product/calvin-klein-solid-dress-shirt?ID=2640393&CategoryID=20635&LinkType=#fn=sp%3D1%26spc%3D3636%26slotId%3D2%26kws%3Dshirt',
        'http://www1.macys.com/shop/product/hurley-one-only-short-sleeve-shirt?ID=2677290&CategoryID=20627&LinkType=#fn=sp%3D1%26spc%3D3636%26slotId%3D10%26kws%3Dshirt',
        'http://www1.macys.com/shop/product/bar-iii-slim-fit-city-lights-print-dress-shirt-only-at-macys?ID=2243591&CategoryID=20635&LinkType=#fn=sp%3D1%26spc%3D3636%26slotId%3D27%26kws%3Dshirt',
        'http://www1.macys.com/shop/product/polo-ralph-lauren-plaid-twill-western-shirt?ID=2435464&CategoryID=20627&LinkType=#fn=sp%3D1%26spc%3D3636%26slotId%3D43%26kws%3Dshirt',
        'http://www1.macys.com/shop/product/polo-ralph-lauren-knit-estate-dress-shirt?ID=2435757&CategoryID=20627&LinkType=#fn=sp%3D1%26spc%3D3636%26slotId%3D59%26kws%3Dshirt',
        'http://www1.macys.com/shop/product/tommy-hilfiger-new-england-stripe-long-sleeve-custom-fit-oxford-shirt?ID=2255249&CategoryID=20627&LinkType=#fn=PAGEINDEX%3D2%26sp%3D2%26spc%3D3636%26slotId%3D61%26kws%3Dshirt'
    ]