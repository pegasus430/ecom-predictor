# -*- coding: utf-8 -*-
import csv
import re

file_csv = file('bjs_merged.csv', 'r+')
reader = csv.DictReader(file_csv)
file_output = file('bjs_output.csv', 'w+')
writer = csv.writer(file_output)

writer.writerow(['category', 'title', 'locale', 'price', 'priceCurrency',
                 'no_longer_available', 'available_online',
                 'shipping_included', 'url',
                 'buyer_reviews', 'image_url', 'is_single_result',
                 'is_out_of_stock', 'given_url', 'model', 'brand',
                 'available_store', 'discount_price',
                 'discount_priceCurrency', 'search_term',
                 'categories', 'last_buyer_review_date', 'ranking',
                 'search_term_in_title_exactly',
                 'search_term_in_title_partial', 'total_matches', 'site',
                 'results_per_page', 'scraped_results_per_page',
                 'shelf_path', 'search_term_in_title_interleaved',
                 'shelf_name', 'is_mobile_agent', 'variants',
                 'minimum_order_quantity', 'description'])

for row in reader:
    category = row.get('\xef\xbb\xbfcategory')
    title = row.get('title')
    locale = row.get('locale')
    price = row.get('price')
    priceCurrency = ""
    if price:
            price_searched = re.search(
                'priceCurrency=(\w+), price=([\d\.]+)', price)
            if price_searched:
                    price = price_searched.group(2)
                    priceCurrency = price_searched.group(1)

    no_longer_available = row.get('no_longer_available')
    available_online = row.get('available_online')
    shipping_included = row.get('shipping_included')
    url = row.get('url')
    buyer_reviews = row.get('buyer_reviews')
    image_url = row.get('image_url')
    is_single_result = row.get('is_single_result')
    is_out_of_stock = row.get('is_out_of_stock')
    given_url = row.get('given_url')
    model = row.get('model')
    brand = row.get('brand')
    available_store = row.get('\xef\xbb\xbfavailable_store')
    discount_price = row.get("price_with_discount")
    discount_priceCurrency = ""
    if discount_price:
            discount_price_searched = re.search(
                'priceCurrency=(\w+), price=([\d\.]+)', discount_price)
            if discount_price_searched:
                    discount_price = discount_price_searched.group(2)
                    discount_priceCurrency = discount_price_searched.group(1)

    search_term = row.get('search_term')
    categories = row.get('categories')
    if categories:
        categories = '/'.join(re.findall("u'(.*?)'", categories))

    last_buyer_review_date = row.get('last_buyer_review_date')
    ranking = row.get('ranking')
    search_term_in_title_exactly = row.get('search_term_in_title_exactly')
    search_term_in_title_partial = row.get(
        '\xef\xbb\xbfsearch_term_in_title_partial')
    total_matches = row.get('total_matches')
    site = row.get('site')
    results_per_page = row.get('results_per_page')
    scraped_results_per_page = row.get('scraped_results_per_page')
    shelf_path = row.get('shelf_path')
    search_term_in_title_interleaved = row.get(
        'search_term_in_title_interleaved')
    shelf_name = row.get('shelf_name')
    is_mobile_agent = row.get('is_mobile_agent')
    variants = row.get('variants')
    minimum_order_quantity = row.get('minimum_order_quantity')
    description = row.get('description')

    writer.writerow([category, title, locale, price, priceCurrency,
                     no_longer_available, available_online,
                     shipping_included, url,
                     buyer_reviews, image_url, is_single_result,
                     is_out_of_stock, given_url, model, brand,
                     available_store, discount_price,
                     discount_priceCurrency, search_term,
                     categories, last_buyer_review_date, ranking,
                     search_term_in_title_exactly,
                     search_term_in_title_partial, total_matches, site,
                     results_per_page, scraped_results_per_page,
                     shelf_path, search_term_in_title_interleaved,
                     shelf_name, is_mobile_agent, variants,
                     minimum_order_quantity, description])

file_csv.close()
file_output.close()
