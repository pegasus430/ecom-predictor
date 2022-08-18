# -*- coding: utf-8 -*-
import csv
import re

file_csv = file('samsclub_merged.csv', 'r+')
reader = csv.DictReader(file_csv)
file_output = file('samsclub_output.csv', 'w+')
writer = csv.writer(file_output)

writer.writerow(['category', 'shipping_included',
                 'title', '﻿locale', 'brand',
                 'no_longer_available', 'available_online',
                 'subscribe_and_save', 'url', 'image_url', 'is_single_result',
                 'available_store', 'price', 'priceCurrency', 'given_url',
                 'model', 'categories', 'delivery_price_standard',
                 'delivery_price_standard_currency', 'delivery_price_premium',
                 'delivery_price_premium_currency', 'delivery_price_express',
                 'delivery_price_express_currency', 'discount_price',
                 'discount_priceCurrency', 'ranking',
                 'search_term_in_title_exactly',
                 'search_term_in_title_partial',
                 'description', 'total_matches', 'site', 'results_per_page',
                 'scraped_results_per_page', 'shelf_path',
                 'search_term_in_title_interleaved',
                 'shelf_name', 'search_term', 'is_mobile_agent', 'variants'])

for row in reader:
    category = row.get('\xef\xbb\xbfcategory')
    shipping_included = row.get('shipping_included')
    title = row.get('title')
    _locale = row.get('\xef\xbb\xbflocale')
    brand = row.get('brand')
    no_longer_available = row.get('\xef\xbb\xbfno_longer_available')
    available_online = row.get('available_online')
    subscribe_and_save = row.get('subscribe_and_save')
    url = row.get('url')
    image_url = row.get('image_url')
    is_single_result = row.get('is_single_result')
    available_store = row.get('available_store')
    price = row.get('price')
    priceCurrency = ""
    if price:
            price_searched = re.search(
                'priceCurrency=(\w+), price=([\d\.]+)', price)
            if price_searched:
                    price = price_searched.group(2)
                    priceCurrency = price_searched.group(1)



    given_url = row.get('given_url')
    model = row.get('model')
    categories = row.get('categories')
    if categories:
        categories = '/'.join(re.findall("u'(.*?)'", categories))

    shipping = row.get('shipping')
    shipping_prices_dict = {}
    if shipping:
        price_shipping = re.findall("u'cost': u'([\d\.]+?)'", shipping)
        name = re.findall("u'name': u'(.*?)'", shipping)

        for (price_shipping, name) in zip(price_shipping, name):
            shipping_prices_dict[name] = price_shipping

    delivery_price_standard = shipping_prices_dict.get('Standard', '')
    delivery_price_standard_currency = priceCurrency if delivery_price_standard else ''
    delivery_price_premium = shipping_prices_dict.get('Premium', '')
    delivery_price_premium_currency = priceCurrency if delivery_price_premium else ''
    delivery_price_express = shipping_prices_dict.get('Express', '')
    delivery_price_express_currency = priceCurrency if delivery_price_express else ''

    discount_price = row.get("price_with_discount")
    discount_priceCurrency = ""
    if discount_price:
            discount_price_searched = re.search(
                'priceCurrency=(\w+), price=([\d\.]+)', discount_price)
            if discount_price_searched:
                    discount_price = discount_price_searched.group(2)
                    discount_priceCurrency = discount_price_searched.group(1)

    ranking = row.get('ranking')
    search_term_in_title_exactly = row.get('search_term_in_title_exactly')
    search_term_in_title_partial = row.get('\xef\xbb\xbfsearch_term_in_title_partial')
    description = row.get('description')
    total_matches = row.get('total_matches')
    site = row.get('site')
    results_per_page = row.get('results_per_page')
    scraped_results_per_page = row.get('scraped_results_per_page')
    shelf_path = row.get('shelf_path')
    search_term_in_title_interleaved = row.get(
        'search_term_in_title_interleaved')
    shelf_name = row.get('shelf_name')
    search_term = row.get('search_term')
    is_mobile_agent = row.get('is_mobile_agent')
    variants = row.get('variants')

    writer.writerow([category, shipping_included, title, _locale, brand,
                     no_longer_available, available_online,
                     subscribe_and_save, url, image_url, is_single_result,
                     available_store, price, priceCurrency, given_url,
                     model, categories, delivery_price_standard,
                     delivery_price_standard_currency, delivery_price_premium,
                     delivery_price_premium_currency, delivery_price_express,
                     delivery_price_express_currency, discount_price,
                     discount_priceCurrency, ranking,
                     search_term_in_title_exactly,
                     search_term_in_title_partial,
                     description, total_matches, site, results_per_page,
                     scraped_results_per_page, shelf_path,
                     search_term_in_title_interleaved,
                     shelf_name, search_term, is_mobile_agent, variants])

file_csv.close()
file_output.close()
