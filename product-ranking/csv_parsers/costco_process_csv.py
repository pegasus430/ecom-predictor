# -*- coding: utf-8 -*-

import csv
import re

file_csv = file('costco_merged.csv', 'r+')
reader = csv.DictReader(file_csv)
file_output = file('costco_output.csv', 'w+')
writer = csv.writer(file_output)

writer.writerow(['category', 'description', 'title', 'locale', 'brand',
                 'no_longer_available', 'available_online',
                 'shipping_included', 'url', 'buyer_reviews', 'image_url',
                 'shipping_cost_price', 'shipping_cost_priceCurrency',
                 'is_single_result', 'price', 'priceCurrency',
                 'given_url', 'search_term', 'categories',
                 'last_buyer_review_date', 'discount_price',
                 'discount_priceCurrency', 'model', 'minimum_order_quantity',
                 '﻿available_store'])

for row in reader:
    category = row.get('category')
    description = row.get('description')
    title = row.get('title')
    locale = row.get('locale')
    brand = row.get('brand')
    no_longer_available = row.get('no_longer_available')
    available_online = row.get('available_online')
    shipping_included = row.get('shipping_included')
    url = row.get('url')
    buyer_reviews = row.get('buyer_reviews')
    image_url = row.get('image_url')
    shipping_cost_price = row.get('shipping_cost')
    shipping_cost_priceCurrency = ""
    if shipping_cost_price:
            ship_cost_pr_search = re.search(
                'priceCurrency=(\w+), price=([\d\.]+)', shipping_cost_price)
            if ship_cost_pr_search:
                    shipping_cost_price = ship_cost_pr_search.group(2)
                    shipping_cost_priceCurrency = ship_cost_pr_search.group(1)

    is_single_result = row.get('is_single_result')
    price = row.get('price')
    priceCurrency = ""
    if price:
            price_searched = re.search(
                'priceCurrency=(\w+), price=([\d\.]+)', price)
            if price_searched:
                    price = price_searched.group(2)
                    priceCurrency = price_searched.group(1)

    given_url = row.get('given_url')
    search_term = row.get('search_term')
    categories = row.get('categories')
    if categories:
        categories = '/'.join(re.findall("u'(.*?)'", categories))

    last_buyer_review_date = row.get('last_buyer_review_date')
    discount_price = row.get("price_with_discount")
    discount_priceCurrency = ""
    if discount_price:
            discount_price_searched = re.search(
                'priceCurrency=(\w+), price=([\d\.]+)', discount_price)
            if discount_price_searched:
                    discount_price = discount_price_searched.group(2)
                    discount_priceCurrency = discount_price_searched.group(1)
    model = row.get('model')
    minimum_order_quantity = row.get('minimum_order_quantity')
    available_store = row.get('﻿available_store')

    writer.writerow([category, description, title, locale, brand,
                     no_longer_available, available_online,
                     shipping_included, url, buyer_reviews, image_url,
                     shipping_cost_price, shipping_cost_priceCurrency,
                     is_single_result, price, priceCurrency,
                     given_url, search_term, categories,
                     last_buyer_review_date, discount_price,
                     discount_priceCurrency, model, minimum_order_quantity,
                     available_store])

file_csv.close()
file_output.close()
