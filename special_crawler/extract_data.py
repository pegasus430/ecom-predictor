#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import sys
import gzip
import json
import time
import shlex
import random
import urllib2
import requests
import cStringIO
import functools
import traceback
import subprocess
import mmh3 as MurmurHash
from socket import timeout
from itertools import chain
from lxml import html, etree
from urlparse import urljoin
from httplib import IncompleteRead
from no_img_hash import fetch_bytes
from dateutil import parser as date_parser
import spiders_shared_code.canonicalize_url
from spiders_shared_code.cacheutils import utils as aerospike_utils


def deep_search(needle, haystack):
    found = []

    if isinstance(haystack, dict):
        if needle in haystack.keys():
            found.append(haystack[needle])

        elif len(haystack.keys()) > 0:
            for key in haystack.keys():
                result = deep_search(needle, haystack[key])
                found.extend(result)

    elif isinstance(haystack, list):
        for node in haystack:
            result = deep_search(needle, node)
            found.extend(result)

    return found


def compress(text):
    if not isinstance(text, unicode):
        raise ValueError('text must be unicode.')

    compressed = cStringIO.StringIO()
    with gzip.GzipFile(fileobj=compressed, mode='w') as gzipf:
        gzipf.write(text.encode('utf8'))
    return compressed.getvalue()


def decompress(text):
    if isinstance(text, unicode):
        raise ValueError('text can\'t be unicode.')

    compressed = cStringIO.StringIO(text)
    with gzip.GzipFile(fileobj=compressed, mode='r') as gzipf:
        decompressed = gzipf.read()
    return decompressed.decode('utf8')


def how_many_bytes(data):
    total_bytes = 0
    for key, value in data.items():
        if isinstance(value, int):
            value = str(value)
        total_bytes += len(key) + len(value)
    return total_bytes


def _cached__extract_page_tree(cache, scraper, func, log_history=None):
    url = scraper.canonicalize_url(scraper._url())
    key = aerospike_utils.request_fingerprint(url, scraper.crawl_date)
    start_time = time.time()
    try:
        row = cache[key]
    except KeyError:
        if scraper.crawl_date != time.strftime("%Y-%m-%d"):
            print 'Cache MISS for KEY:{} URL:{} DATE:{}'.format(key, url, scraper.crawl_date)
            scraper.ERROR_RESPONSE['failure_type'] = 'Not found in cache'
            scraper.is_timeout = True
            return
        time_ = time.time() - start_time
        print 'Cache MISS for KEY:{} URL:{} TIME:{}'.format(key, url, time_)
        if log_history is not None:
            log_history.data['cache']['time'] += time_
            log_history.data['cache']['miss'] += 1
            log_history.data['cache']['miss_time'] += time_
        result = func(scraper)
        if getattr(scraper, 'page_raw_text', False) \
                and getattr(scraper, 'tree_html', False):
            if not isinstance(scraper.page_raw_text, unicode):
                print 'Cache can\'t cache for key {} url {}'.format(key, url)
                return result
            start_time = time.time()
            data = {
                'url': url,
                'body': bytearray(compress(scraper.page_raw_text))
            }
            cache[key] = data
            cache.flush()
            time_ = time.time() - start_time
            total_bytes = how_many_bytes(data)
            print 'Cache UPDATE for KEY:{} URL:{} BYTES:{} TIME:{}'\
                .format(key, url, total_bytes, time_)
            if log_history is not None:
                log_history.data['cache']['time'] += time_
                log_history.data['cache']['update'] += 1
                log_history.data['cache']['update_time'] += time_
                log_history.data['cache']['update_bytes'] += total_bytes
        return result
    else:
        time_ = time.time() - start_time
        total_bytes = how_many_bytes(row)
        print 'Cache HIT for KEY:{} URL:{} BYTES:{} TIME:{}'\
            .format(key, url, total_bytes, time_)
        if log_history is not None:
            log_history.data['cache']['time'] += time_
            log_history.data['cache']['hit'] += 1
            log_history.data['cache']['hit_time'] += time_
            log_history.data['cache']['hit_bytes'] += total_bytes
        scraper.page_raw_text = decompress(row['body'])
        scraper.tree_html = html.fromstring(scraper.page_raw_text)


def _cached_load_page_from_url_with_number_of_retries(
        cache, scraper, func, args, kwargs, log_history=None
):
    url = scraper.canonicalize_url(args[0])
    key = aerospike_utils.request_fingerprint(url, scraper.crawl_date)
    start_time = time.time()
    try:
        row = cache[key]
    except KeyError:
        if scraper.crawl_date != time.strftime("%Y-%m-%d"):
            print 'Cache MISS for KEY:{} URL:{} DATE:{}'.format(key, url, scraper.crawl_date)
            scraper.ERROR_RESPONSE['failure_type'] = 'Not found in cache'
            scraper.is_timeout = True
            return
        time_ = time.time() - start_time
        print 'Cache MISS for KEY:{} URL:{} TIME:{}'.format(key, url, time_)
        if log_history is not None:
            log_history.data['cache']['time'] += time_
            log_history.data['cache']['miss'] += 1
            log_history.data['cache']['miss_time'] += time_
        result = func(scraper, *args, **kwargs)
        if not isinstance(result, unicode):
            print 'Cache can\'t cache for key {} url {}'.format(key, url)
            return result
        start_time = time.time()
        data = {
            'url': url,
            'body': bytearray(compress(result))
        }
        cache[key] = data
        cache.flush()
        time_ = time.time() - start_time
        total_bytes = how_many_bytes(data)
        print 'Cache UPDATE for KEY:{} URL:{} BYTES:{} TIME:{}'\
            .format(key, url, total_bytes, time_)
        if log_history is not None:
            log_history.data['cache']['time'] += time_
            log_history.data['cache']['update'] += 1
            log_history.data['cache']['update_time'] += time_
            log_history.data['cache']['update_bytes'] += total_bytes
        return result
    else:
        time_ = time.time() - start_time
        total_bytes = how_many_bytes(row)
        print 'Cache HIT for key {} url {}'.format(key, url)
        if log_history is not None:
            log_history.data['cache']['time'] += time_
            log_history.data['cache']['hit'] += 1
            log_history.data['cache']['hit_time'] += time_
            log_history.data['cache']['hit_bytes'] += total_bytes
        return decompress(row['body'])


def cached(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # implicit way of disabling the cache for the crawler,
        # should it be explicit?
        if not hasattr(self, 'canonicalize_url'):
            return func(self, *args, **kwargs)

        if getattr(self, 'cache', None) is None:
            if getattr(self, 'crawl_date') != time.strftime("%Y-%m-%d"):
                self.ERROR_RESPONSE['failure_type'] = 'Not found in cache'
                self.is_timeout = True
                return
            return func(self, *args, **kwargs)

        cache, log_history = self.cache, self.lh
        if func.__name__ == '_extract_page_tree':
            return _cached__extract_page_tree(
                cache, self, func, log_history=log_history
            )
        elif func.__name__ == 'load_page_from_url_with_number_of_retries':
            return _cached_load_page_from_url_with_number_of_retries(
                cache, self, func, args, kwargs, log_history=log_history
            )
    return wrapper


class Scraper(object):

    """Base class for scrapers
    Handles incoming requests and calls specific methods from subclasses
    for each requested type of data,
    making sure to minimize number of requests to the site being scraped

    Each subclass must implement:
    - define DATA_TYPES and DATA_TYPES_SPECIAL structures (see subclass docs)
    - implement each method found in the values of the structures above
    - implement checktree_html_format()

    Attributes:
        product_page_url (string): URL of the page of the product being scraped
        tree_html (lxml tree object): html tree of page source. This variable is initialized
        whenever a request is made for a piece of data in DATA_TYPES. So it can be used for methods
        extracting these types of data.
        MAX_RETRIES (int): number of retries before giving up fetching product page soruce (if errors encountered
            - usually IncompleteRead exceptions)
    """
    # Browser agent string list
    BROWSER_AGENT_STRING_LIST = {"Firefox": ["Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1",
                                             "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0",
                                             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10; rv:33.0) Gecko/20100101 Firefox/33.0"],
                                 "Chrome":  ["Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36",
                                             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.1 Safari/537.36",
                                             "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36",
                                             "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.0 Safari/537.36"],
                                 "Safari":  ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/7046A194A",
                                             "Mozilla/5.0 (iPad; CPU OS 6_0 like Mac OS X) AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 Mobile/10A5355d Safari/8536.25",
                                             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.13+ (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2"]
                                 }

    # number of retries for fetching product page source before giving up
    MAX_RETRIES = 3

    # List containing all data types returned by the crawler (that will appear in responses of requests to service in crawler_service.py)
    # In practice, all returned data types for all crawlers should be defined here
    # The final list containing actual implementing methods for each data type will be defined in the constructor
    # using the declarations in the subclasses (for data types that have support in each subclass)

    BASE_DATA_TYPES_LIST = {
            "url", # url of product
            "event",
            "status_code",
            "product_id",
            "site_product_id",
            "site_id",
            "walmart_no",
            "tcin",
            "date",
            "crawl_date", # CON-43392, If this field is present, request data from the cache for this date
            "status",
            "site_version",
            "scraper", # version of scraper in effect. Relevant for Walmart old vs new pages.
                       # Only implemented for walmart. Possible values: "Walmart v1" or "Walmart v2"
            "proxy_service",

            # product_info
            "product_name", # name of product, string
            "product_title", # page title, string
            "product_code", # for wayfairs.com
            "title_seo", # SEO title, string
            "model", # model of product, string
            "upc", # upc of product, string
            "wupc", # implemented for Walmart (different than upc)
            "gtin", # for Walmart
            "asin", # Amazon asin
            "specs", # specifications
            "size", # size information
            "uom", # unit of measurement
            "features", # features of product, string
            "feature_count", # number of features of product, int
            "specs", # specifications
            "full_specs", # grouped keys from specs, dict
            "model_meta", # model from meta, string
            "description", # short description / entire description if no short available, string
            "rich_content", # check if product overview has rich content(images) - 0: not exists, 1:exists
            "seller_ranking",
            "long_description", # long description / null if description above is entire description,
            "shelf_description",
            "shelf_description_bullet_count",
            "sku",
            "apluscontent_desc", #aplus description
            "ingredients", # list of ingredients - list of strings
            "ingredient_count", # number of ingredients - integer
            "nutrition_facts", # nutrition facts - list of tuples ((key,value) pairs, values could be dictionaries)
                               # containing nutrition facts
            "nutrition_fact_count", # number of nutrition facts (of elements in the nutrition_facts list) - integer
            "nutrition_fact_text_health", # indicate nutrition fact text status - 0: not exists, 1: exists, 2: error
            "drug_facts", # drug facts - list of tuples ((key,value) pairs, values could be dictionaries)
                               # containing drug facts
            "drug_fact_count", # number of drug facts (of elements in the drug_facts list) - integer
            "drug_fact_text_health", # indicate drug fact text status - 0: not exists, 1: exists but partially, 2: exists and perfect.
            "supplement_facts",
            "supplement_fact_count",
            "supplement_fact_text_health",
            "rollback", # binary (0/1), whether product is rollback or not
            "free_pickup_today",
            "no_longer_available",
            "assembled_size",
            "item_num",
            "mpn",
            "temporary_unavailable",
            "variants", # list of variants (see VARIANTS STRUCTURE)
            "swatches", # list of swatches (see SWATCHES STRUCTURE)
            "swatch_image_missing",
            "swatch_image_missing", # if any swatches are missing images or not (1/0)
            "bundle",
            "bundle_components",
            "details", # field only for Target scraper, string
            "item_size",
            "mta",
            "bullet_feature_1",
            "bullet_feature_2",
            "bullet_feature_3",
            "bullet_feature_4",
            "bullet_feature_5",
            "bullet_feature_6",
            "bullet_feature_7",
            "bullet_feature_8",
            "bullet_feature_9",
            "bullet_feature_10",
            "bullet_feature_11",
            "bullet_feature_12",
            "bullet_feature_13",
            "bullet_feature_14",
            "bullet_feature_15",
            "bullet_feature_16",
            "bullet_feature_17",
            "bullet_feature_18",
            "bullet_feature_19",
            "bullet_feature_20",
            "bullet_feature_count",
            "bullets",
            "usage",
            "directions",
            "warnings",
            "has_warning", # CON-45722, bool, has 'WARNING'
            "warning_text", # CON-45722, str, text of 'WARNING'
            "indications",
            "has_wwlt", # whether product has Why We Love This section on the page
            "wwlt_text", # Why we love this section text
            "collection_count", # Field for Home Depot scraper
            "accessories_count", # Field for Home Depot scraper
            "coordinating_items_count", # Field for Home Depot scraper
            "has_ppum",  # CON-44924, bool, 1 - if 'Price Per Unit of Measure' is available
            "related_products",  # CON-44924, bool. 1 - if 'related products' section is available
            "parent_id",

            # page_attributes
            "mobile_image_same", # whether mobile image is same as desktop image, 1/0
            "image_count", # number of product images, int
            "image_names", # the names of the images, derived from image_urls, list of strings
            "image_urls", # urls of product images, list of strings
            "image_colors", # background colors of images, list of strings
            "image_alt_text", # alt text for images, list of strings
            "image_alt_text_len",  # lengths of alt text for images, list of integers
            "image_dimensions", # dimensions of product images
            "in_page_360", # binary (0/1), whether 360 images exists or not
            "in_page_360_image_urls",  # urls of 360(spin) images
            "in_page_360_image_count", # number of 360(spin) images, int
            "zoom_image_dimensions", # whether product images are zoomable (2000x2000), 1/0
            "no_image_available", # binary (0/1), whether there is a 'no image available' image
            "image_res", # image size list
            "duplicate_images", # image duplication count
            "video_count", # nr of videos, int
            "video_urls", # urls of product videos, list of strings
            "wc_360", # binary (0/1), whether 360 view exists or not
            "wc_emc", # binary (0/1), whether emc exists or not
            "wc_video", # binary (0/1), whether video exists or not
            "wc_pdf", # binary (0/1), whether pdfexists or not
            "wc_prodtour", # binary (0/1), whether product tour view exists or not
            "flixmedia",
            "pdf_count", # nr of pdfs, string
            "pdf_urls", # urls of product pdfs, list of strings
            "webcollage", # whether page contains webcollage content, 1/0
            "webcollage_image_urls", # images that are referenced on the webcollage.net or webcollage.com sites (urls)
            "webcollage_images_count", # images that are referenced on the webcollage.net or webcollage.com sites (count)
            "webcollage_videos_count", # videos that are referenced on the webcollage.net or webcollage.com sites
            "webcollage_pdfs_count", # pdfs that are referenced on the webcollage.net or webcollage.com sites
            "sellpoints", # whether page contains sellpoint content, 1/0
            "cnet", # whether page contains cnet content, 1/0
            "htags", # h1 and h2 tags, dictionary like: {"h1" : [], "h2": ["text in tag"]}
            "loaded_in_seconds", # load time of product page in seconds, float
            "keywords", # keywords for this product, usually from meta tag, string
            "meta_tags",# a list of pairs of meta tag keys and values
            "meta_tag_count", # the number of meta tags in the source of the page
            "meta_description_count", # char count of meta description field
            "canonical_link", # canoncial link of the page
            "buying_option",
            "image_hashes", # list of hash values of images as returned by _image_hash() function - list of strings (the same order as image_urls)
            "thumbnail", # thumbnail of the main product image on the page - tbd
            "manufacturer", # manufacturer info for this product
            "return_to", # return to for this product
            "comparison_chart", # whether page contains a comparison chart, 1/0
            "btv", # if page has a 'buy together value' offering, 1/0
            "best_seller_category", # name of best seller category (Amazon)
            "meta_description", # 1/0 whether meta description exists on page
            "results_per_page", # number of items on shelf page
            "total_matches", # total number of items in shelf page category
            "lowest_item_price",
            "highest_item_price",
            "num_items_price_displayed",
            "num_items_no_price_displayed",
            "body_copy",
            "body_copy_links",
            "redirect", # 1/0 if page is a redirect
            "size_chart", # 1/0 if there is a size chart link on the page
            "how_to_measure",
            "fit_guide", # 1/0 if there is a fit guide link on the page
            "selected_variant",
            "fresh",   # Scrape if a Fresh URL can be found on Amazon Fresh for amazon.com
            "pantry",   # Scrape if a Amazon URL can be found on Pantry
            "questions_total",
            "questions_unanswered",
            "spec_table", # binary, for Samsclub spec table
            "spec_text", # binary, for Samsclub spec text
            "spec_content", # binary, for Samsclub enhanced table spec
            "spec_word_count", # int, word count of specs for Samsclub
            "document_names", # list, names of pdf documents for homedepot
            "super_enhancement", # 1/0 if there is super enhancement content on the page (Samsclub)
            "marketing_content", # str, actual html of 'From the Manufacturer' (Amazon)

            # reviews
            "review_count", # total number of reviews, int
            "average_review", # average value of review, float
            "max_review", # highest review score, float
            "min_review", # lowest review score, float
            "reviews", # review list
            "ugc", # #TargetStyle images, list (CON-33741)

            # sellers
            "price", # price, string including currency
            "price_amount", # price, float
            "price_currency", # currency for price, string of max 3 chars
            "temp_price_cut", # Temp Price Cut, 1/0
            "subscribe_price", # Subscribe & Save price, float
            "subscribe_discount", # Subscribe & Save discount percent, float
            "web_only", # Web only, 1/0
            "home_delivery", # Home Delivery, 1/0
            "click_and_collect", # Click and Collect, 1/0
            "dsv", # if a page has "Shipped from an alternate warehouse" than it is a DSV, 1/0
            "in_stores", # available to purchase in stores, 1/0
            "in_stores_only", # whether product can be found in stores only, 1/0
            "marketplace", # whether product can be found on marketplace, 1/0
            "marketplace_sellers", # sellers on marketplace (or equivalent) selling item, list of strings
            "marketplace_lowest_price", # string
            "primary_seller", # primary seller
            "seller_id", # for Walmart
            "us_seller_id", # for Walmart
            "in_stock", # binary (0/1), whether product can be bought from the site, from any seller
            "site_online", # the item is sold by the site and delivered directly, irrespective of availability - binary
            "site_online_in_stock", # currently available from the site - binary
            "site_online_out_of_stock", # currently unavailable from the site - binary
            "marketplace_in_stock", # currently available from at least one marketplace seller - binary
            "marketplace_out_of_stock", # currently unavailable from any marketplace seller - binary
            "marketplace_prices", # the list of marketplace prices - list of floating-point numbers ([0.00, 0.00], needs to be in the same order as list of marketplace_sellers)
            "in_stores_in_stock", # currently available for pickup from a physical store - binary (null should be used for items that can not be ordered online and the availability may depend on location of the store)
            "in_stores_out_of_stock", # currently unavailable for pickup from a physical store - binary (null should be used for items that can not be ordered online and the availability may depend on location of the store)
            "online_only", # site_online or marketplace but not in_stores - binary
            # legacy
            "owned", # whether product is owned by site, 1/0
            "owned_out_of_stock", # whether product is owned and out of stock, 1/0

            # classification
            "categories", # full path of categories down to this product's ["full", "path", "to", "product", "category"], list of strings
            "category_name", # category for this product, string
            "shelf_links_by_level", # list of category urls
            "brand", # brand of product, string
            "mfg", # mfg, string, for westmarine.com

            "preparation", # preparation, Binary, for sainsburys.co.uk
            "country_of_origin", # country_of_origin, Binary, for sainsburys.co.uk
            "packaging", # packaging, Binary, for sainsburys.co.uk

            # Deprecated:
            # "anchors", # links found in the description, dictionary like {"links" : [], quantity: 0}
            # "product_id", # product id (usually from page url), string
            # "no_image", # whether product image is a "there is no image" image: 1/0
            # "manufacturer_content_body", # special section of description by the manufacturer, string
            # "asin",
    }

    # VARIANTS STRUCTURE
    """
    {
        "image_url": (str),
        "in_stock": (bool), 
        "price": (float), 
        "properties": {
          <property name> (str) : <property value> (str), 
          <property name> (str) : <property value> (str),
          ...
        }, 
        "selected": (bool),
        "sku_id": (str),
        "unavailable": (bool),
        "upc": (str)
      }
    """

    # SWATCHES STRUCTURE
    """
    {
        "color": <color name> (str),
        "hero": <number of hero images> (int), 
        "hero_image": [
          <swatch image url> (str),
          <swatch image url> (str),
          ...
        ], 
        "swatch_name": "color", 
        "thumb": <number of thumbnail images> (int), 
        "thumb_image": [
          <thumb image url> (str),
          <thumb image url> (str),
          ...
        ]
    }
    """

    # Structure containing data types returned by the crawler as keys
    # and the functions handling extraction of each data type as values
    # There will be dummy implementations for the functions in this base class
    # (to handle subclasses where the extraction is not implemented)
    # and their definition will be overwritten in subclasses where the extraction is implemented;
    # or data types will be added to the structure below
    #
    # "loaded_in_seconds" needs to always have a value of None (no need to implement extraction)
    # TODO: date should be implemented here
    BASE_DATA_TYPES = {
        data_type : lambda x: None for data_type in BASE_DATA_TYPES_LIST # using argument for lambda because it will be used with "self"
    }

    # structure containing subdictionaries of returned object
    # and how they should be grouped.
    # keys are root object keys, values are lists of result object keys that should be nested
    # into these root keys
    # keys that should be left in the root are not included in this structure
    # TODO: make sure this is synchronized somehow with BASE_DATA_TYPES? like there should be no extra data types here
    #       maybe put it as an instance variable
    # TODO: add one for root? to make sure nothing new appears in root either?
    DICT_STRUCTURE = {
        "product_info": ["product_name", "product_title", "product_code", "title_seo", "model", "upc", "size", "uom", "asin", "features", "feature_count",
                        "model_meta", "description", "rich_content", "seller_ranking", "long_description", "shelf_description", "sku", "apluscontent_desc",
                        "ingredients", "ingredient_count", "nutrition_facts", "nutrition_fact_count", "nutrition_fact_text_health",
                        "drug_facts", "drug_fact_count", "drug_fact_text_health", "supplement_facts", "supplement_fact_count",
                        "supplement_fact_text_health", "rollback", "free_pickup_today", "no_longer_available", "manufacturer",
                        "return_to", "details", "mta", "bullet_feature_1", "bullet_feature_2", "bullet_feature_3", "bullet_feature_4",
                        "bullet_feature_5", "bullet_feature_6", "bullet_feature_7", "bullet_feature_8", "bullet_feature_9",
                        "bullet_feature_10", "bullet_feature_11", "bullet_feature_12", "bullet_feature_13", "bullet_feature_14",
                        "bullet_feature_15", "bullet_feature_16", "bullet_feature_17", "bullet_feature_18", "bullet_feature_19",
                        "bullet_feature_20", "bullet_feature_count", "bullets", "usage", "directions", "warnings", "indications",
                        "specs", "temporary_unavailable", "mfg", "assembled_size", "item_num", "mpn", "wupc", "has_wwlt", "wwlt_text",
                        "spec_table", "spec_text", "spec_content", "spec_word_count", "gtin", "ugc", "shelf_description_bullet_count",
                        "parent_id", "has_ppum", "related_products", "preparation", "country_of_origin", "packaging"],
        "page_attributes": ["mobile_image_same", "image_count", "image_urls", "image_alt_text", "image_alt_text_len", "image_dimensions",
                            "zoom_image_dimensions", "no_image_available", "image_res", "video_count", "video_urls", "wc_360", "wc_emc", "wc_video",
                            "wc_pdf", "wc_prodtour", "flixmedia", "pdf_count", "pdf_urls", "htags", "loaded_in_seconds", "keywords",
                            "webcollage", "webcollage_image_urls", "webcollage_images_count", "webcollage_videos_count", "webcollage_pdfs_count",
                            "meta_tags", "meta_tag_count", "meta_description_count", "image_hashes", "thumbnail", "sellpoints", "canonical_link",
                            "buying_option", "variants", "bundle_components", "bundle", "swatches", "swatch_image_missing", "comparison_chart", "btv",
                            "best_seller_category", "results_per_page", "total_matches", "lowest_item_price", "highest_item_price",
                            "num_items_price_displayed", "num_items_no_price_displayed", "body_copy", "body_copy_links", "meta_description",
                            "cnet", "redirect", "size_chart", "how_to_measure", "fit_guide", "selected_variant", "fresh", "pantry",
                            "questions_total", "questions_unanswered", "swatch_image_missing", "image_colors", "in_page_360", "in_page_360_image_urls",
                            "in_page_360_image_count", "document_names", "collection_count", "accessories_count", "coordinating_items_count",
                            "super_enhancement", "duplicate_images", "image_names", "has_warning", "warning_text", "marketing_content"],
        "reviews": ["review_count", "average_review", "max_review", "min_review", "reviews"],
        "sellers": ["price", "price_amount", "price_currency","temp_price_cut", "web_only", "home_delivery", "click_and_collect",
                    "dsv", "in_stores_only", "in_stores", "owned", "owned_out_of_stock", "marketplace", "marketplace_sellers",
                    "marketplace_lowest_price", "primary_seller", "seller_id", "us_seller_id", "in_stock", "site_online", "site_online_in_stock",
                    "site_online_out_of_stock", "marketplace_in_stock", "marketplace_out_of_stock", "marketplace_prices", "in_stores_in_stock",
                    "in_stores_out_of_stock", "online_only", "subscribe_price", "subscribe_discount"],
        "classification": ["categories", "category_name", "brand", "shelf_links_by_level"]
    }

    # response in case of error
    ERROR_RESPONSE = {
        "date": None,
        "event" : None,
        "failure_type": None,
        "product_id": None,
        "status": None,
        "url": None,
    }

    def _extract_webcollage_contents(self, product_id=None):
        try:
            wc_page_contents = None
            webcollage_360 = None

            if self.__class__.__name__ == 'WalmartScraper':
                marketing_description = deep_search('MarketingDescription', self.product_info_json_for_description)

                sellpoints_marketing_content = deep_search('SellPointsMarketingContent', self.product_info_json_for_description)

                if sellpoints_marketing_content:
                    self.sellpoints = 1

                def fix_html_content(html_content):
                    html_content = urllib2.unquote(html_content)

                    html_content = re.sub('\\\\', '', html_content)
                    html_content = re.sub("\\'", '', html_content)

                    return html.fromstring(html_content)

                marketing_content = marketing_description or sellpoints_marketing_content

                if marketing_content:
                    wc_page_contents = marketing_content[0].get('htmlContent')

                    if wc_page_contents:
                        wc_page_contents = fix_html_content(wc_page_contents)

                        if 'richcontext' in html.tostring(wc_page_contents) or \
                                'contentanalytics' in html.tostring(wc_page_contents):
                            self.rich_content = 1

                webcollage_360 = deep_search('Webcollage360View', self.product_info_json_for_description)

                if webcollage_360:
                    webcollage_360 = webcollage_360[0].get('htmlContent')

                    if webcollage_360:
                        webcollage_360 = fix_html_content(webcollage_360)

                webcollage_pdf = deep_search('WebcollageDocuments', self.product_info_json_for_description)

                if webcollage_pdf:
                    urls = deep_search('url', webcollage_pdf[0])

                    if urls:
                        self.wc_pdf = 1
                        self.wc_pdfs = [u['values'][0] for u in urls]

            else:
                wc_page_contents = self._request(self.WEBCOLLAGE_POWER_PAGE.format(product_id or self._product_id()), use_proxies=False).text

                if not "_wccontent" in wc_page_contents:
                    return

                wc_page_contents = self._find_between(wc_page_contents, 'html: "', '"\n').decode('string_escape')
                wc_page_contents = html.fromstring(wc_page_contents.replace('\\', ''))

            if webcollage_360:
                if webcollage_360.xpath('//div[@data-section-tag="360-view"]'):
                    self.wc_360 = 1

            if wc_page_contents:
                # 360
                if wc_page_contents.xpath('//div[@data-section-tag="360-view"]'):
                    self.wc_360 = 1

                # emc
                if wc_page_contents.xpath('//div[contains(@class,"wc-responsive")]'):
                    self.wc_emc = 1

                # images
                wc_images = wc_page_contents.xpath('//img[contains(@class,"wc-image")]/@src') + \
                        wc_page_contents.xpath('//div[contains(@class,"wc-gallery-thumb")]//img/@wcobj')
                if wc_images:
                    self.wc_image = 1
                    self.wc_images = wc_images

                # pdfs
                wc_pdfs = wc_page_contents.xpath('//img[@wcobj-type="application/pdf"]/@wcobj')
                if wc_pdfs:
                    self.wc_pdf = 1
                    self.wc_pdfs = wc_pdfs

                # prod tour
                wc_json_data = wc_page_contents.xpath('//div[@class="wc-json-data"]/text()')
                if wc_json_data:
                    wc_json_data = json.loads(wc_json_data[0])

                    if wc_json_data.get('tourViews'):
                        self.wc_prodtour = 1

                # videos
                wc_video_urls = wc_page_contents.xpath('//div[@itemprop="video"]/meta[@itemprop="contentUrl"]/@content')
                if wc_video_urls:
                    self.wc_video = 1
                    self.wc_videos = wc_video_urls

        except:
            print traceback.format_exc()

    def _extract_webcollage_module_contents(self, product_id=None):
        try:
            wc_page_contents = self._request(self.WEBCOLLAGE_MODULE_PAGE.format(product_id or self._product_id()), use_proxies=False).text
            wc_page_contents = html.fromstring(wc_page_contents)

            videos = []

            video_json = wc_page_contents.xpath('//div[contains(@id,"videoGallery")]//div[@class="wc-json-data"]/text()')
            if video_json:
                video_json = json.loads(video_json[0])

                for video in video_json.get('videos', []):
                    videos.append(video['src']['src'])

            if videos:
                self.wc_videos = 1
                self.wc_videos = ['http://media.webcollage.net/rlfp/wc/live/module/waterpik' + v for v in videos]

        except:
            print traceback.format_exc()

    def _extract_questions_content(self):
        if hasattr(self, 'QUESTIONS_URL'):
            page = 1
            resp = self._request(self.QUESTIONS_URL.format(
                product_id=self._product_id(),
                page=page
            ))
            if resp.status_code == 200:
                # bazaarvoice questions
                total = re.search('BVQANumber\\\\">(\d+)<\\\\/span> Questions', resp.content)
                pages = re.search(r'numPages\":(\d+)', resp.content)
                if total and pages:
                    self.questions_total = int(total.group(1))
                    num_pages = int(pages.group(1))
                    self._count_unanswered_questions(resp.content)
                    for page in range(2, num_pages+1):
                        resp = self._request(self.QUESTIONS_URL.format(
                            product_id=self._product_id(),
                            page=page
                        ))
                        if resp.status_code == 200:
                            self._count_unanswered_questions(resp.content)
        else:
            print('[WARNING] `QUESTIONS_URL` is not set')

    def _count_unanswered_questions(self, data):
        for answers in re.findall('BVQANumber\\\\">(\d+)<\\\\/span> answer', data):
            if answers == '0':
                self.questions_unanswered += 1

    def _questions_total(self):
        return self.questions_total

    def _questions_unanswered(self):
        return self.questions_unanswered

    def canonicalize_url(self, url):
        return spiders_shared_code.canonicalize_url.default(url)

    def select_browser_agents_randomly(self, agent_type=None):
        if agent_type and agent_type in self.BROWSER_AGENT_STRING_LIST:
            return random.choice(self.BROWSER_AGENT_STRING_LIST[agent_type])

        return random.choice(random.choice(self.BROWSER_AGENT_STRING_LIST.values()))

    def load_page_from_url_with_number_of_retries(self, url, max_retries=3, extra_exclude_condition=None):
        for index in range(1, max_retries):
            header = {"User-Agent": self.select_browser_agents_randomly()}
            s = requests.Session()
            a = requests.adapters.HTTPAdapter(max_retries=3)
            b = requests.adapters.HTTPAdapter(max_retries=3)
            s.mount('http://', a)
            s.mount('https://', b)
            contents = s.get(url, headers=header).text

            if not extra_exclude_condition or extra_exclude_condition not in contents:
                return contents

        return None

    def remove_duplication_keeping_order_in_list(self, seq):
        if seq:
            seen = set()
            seen_add = seen.add
            return [x for x in seq if not (x in seen or seen_add(x))]

        return None

    def _exclude_javascript_from_description(self, description):
        description = re.subn(r'<(script).*?</\1>(?s)', '', description)[0]
        description = re.subn(r'<(style).*?</\1>(?s)', '', description)[0]
        description = re.subn("(<!--.*?-->)", "", description)[0]
        return description

    def _clean_text(self, text):
        text = re.sub('&nbsp;', ' ', text)
        text = re.sub('\s+', ' ', text).strip()
        return text

    def load_image_hashes():
        '''Read file with image hashes list
        Return list of image hashes found in file
        '''
        path = os.path.dirname(os.path.realpath(__file__)) + '/no_img_list.json'
        no_img_list = []
        if os.path.isfile(path):
            f = open(path, 'r')
            s = f.read()
            if len(s) > 1:
                no_img_list = json.loads(s)
            f.close()
        return no_img_list

    def _proxy_service(self):
        return self.proxy

    # Only set proxy if the scraper will actually use it
    def _set_proxy(self, to = None, reset_proxies = False, unset = False):
        if unset:
            self.proxy = None
            self.proxy_host = None
            self.proxy_port = None
            self.proxies = {}
            return

        # do not reset proxies if it they already been set
        if self.proxies and not reset_proxies and not to:
            return

        try:
            if to:
                proxy = to
            else:
                proxy = self._weighted_choice(self.proxy_config)
            assert proxy

            proxy_host = proxy.split(':')[0]
            assert proxy_host.endswith('contentanalyticsinc.com') or re.match('^\d+\.\d+\.\d+\.\d+$', proxy_host)

            proxy_port = proxy.split(':')[1]
            assert re.match('\d+', proxy_port)

        except Exception as e:
            print traceback.format_exc(e)

        else:
            self.proxy = proxy
            self.proxy_host = proxy_host
            self.proxy_port = proxy_port
            self.proxies = {"http": "http://{}:{}/".format(proxy_host, proxy_port), \
                        "https": "https://{}:{}/".format(proxy_host, proxy_port)}

            if self.lh:
               self.lh.add_log('proxy_service', self.proxy.replace(':', '_'))

            # include proxy service in error response if there is a failure
            self.ERROR_RESPONSE['proxy_service'] = self.proxy


    def handle_badstatusline(f):
        """https://github.com/mikem23/keepalive-race
        """
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            for _ in range(2):
                try:
                    return f(*args, **kwargs)
                except requests.exceptions.ConnectionError as e:
                    if 'BadStatusLine' in e.message:
                        continue
                    raise
            else:
                raise
        return wrapper

    @staticmethod
    def get_redirect_url(tree_html):
        redirect_url = tree_html.xpath('//meta[@http-equiv="Refresh"]/@content')

        if redirect_url:
            return re.search("URL=(.*)", redirect_url[0]).group(1)

        action = tree_html.xpath('//form/@action')
        redirect_url = tree_html.xpath('//input[@id="targetUrl"]/@value')

        if action and redirect_url:
            return urljoin(action[0], urllib2.unquote(redirect_url[0]))

    @handle_badstatusline
    def _request(self, url,
            cookies = None,
            data = None,
            verb = 'get',
            headers = {},
            session = None,
            timeout = None,
            use_proxies = True,
            use_session = False,
            use_user_agent = True,
            allow_redirects = True,
            log_status_code = False):

        if not headers and hasattr(self, 'HEADERS'):
            headers = self.HEADERS

        if use_user_agent:
            headers = dict({
                'User-Agent': self.USER_AGENT if hasattr(self, 'USER_AGENT') else self.select_browser_agents_randomly(),
            }.items() + headers.items())
        headers = dict({
            'accept-language': 'en-US',
            'x-forwarded-for': '172.0.01',
        }.items() + headers.items())

        s = session or requests

        if use_session:
            s = requests.Session()

        if self.proxies and use_proxies:
            exec('''r = s.{}(url,
                cookies = cookies,
                data = data,
                headers = headers,
                proxies = self.proxies,
                timeout = timeout or 300,
                verify = False,
                allow_redirects = False)'''.format(verb))
        else:
            exec('''r = s.{}(url,
                cookies = cookies,
                data = data,
                headers = headers,
                timeout = timeout or 20,
                verify = False,
                allow_redirects = allow_redirects)'''.format(verb))

        while str(r.status_code).startswith('3'):
            url = urljoin(url, r.headers['location'])

            if r.request.url == url:
                break

            self.is_redirect = 1

            r = Scraper._request(self, url,
                cookies = cookies,
                data = data,
                verb = verb,
                headers = headers,
                session = s,
                timeout = timeout,
                use_proxies = use_proxies,
                use_user_agent = use_user_agent,
                allow_redirects = allow_redirects)

        if use_session:
            s.close()

        if log_status_code:
            self.status_code = r.status_code

            if self.lh:
                self.lh.add_log('status_code', r.status_code)

        return r

    def _extract_page_tree_with_retries(self, session = None, use_session = False, save_session = False, use_user_agent = True, max_retries = 3):
        i = 0

        while True:
            i += 1

            if i > max_retries:
                break

            # reset everything

            self.is_timeout = False

            self.page_raw_text = None
            self.tree_html = None

            if self.lh:
                self.lh.add_log('status_code', None)

            self.ERROR_RESPONSE['failure_type'] = None

            try:
                if session:
                    s = session
                else:
                    s = self.session or requests.Session() if use_session else None

                if self.__class__.__name__ in ['SainsburysScraper', 'MacysScraper']:
                    Scraper._request(self, self.product_page_url, session = s, use_user_agent = use_user_agent)

                r = Scraper._request(self,
                    self.product_page_url,
                    session = s,
                    log_status_code = True,
                    use_user_agent = use_user_agent)

                if s:
                    if save_session:
                        self.session = s
                    else:
                        s.close()

                if r.ok or (r.status_code == 404 and self.__class__.__name__ in ['TescoScraper', 'KohlsScraper']):
                    try:
                        self.page_raw_text = r.content.decode('utf-8')
                    except:
                        self.page_raw_text = r.text
                    self.tree_html = html.fromstring(self.page_raw_text)

                    if self.not_a_product() or (self.__class__.__name__ == 'TargetScraper' and self.no_longer_available):
                        continue

                    return

                self.ERROR_RESPONSE['failure_type'] = r.status_code
                self.is_timeout = True

                if r.status_code == 403:
                    self._set_proxy()

                if r.status_code == 429:
                    time.sleep(10)

                if r.status_code == 404:
                    break

                if r.status_code in [405, 456]:
                    max_retries = 10

            except requests.exceptions.ProxyError as e:
                print 'Proxy error, retrying with curl', self.product_page_url
                time.sleep(10)

                header_string = '"User-Agent: {}"'.format(self.select_browser_agents_randomly())
                cmd = 'curl -H {} --proxy {} {}'.format(header_string, self.proxy, self.product_page_url)

                p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)

                try:
                    self.page_raw_text, err = p.communicate()
                    self.tree_html = html.fromstring(self.page_raw_text)
                except:
                    # TODO: failure_type?
                    continue

                if self.not_a_product():
                    continue

                return

            except Exception as e:
                print traceback.format_exc(e)

                if self.lh and i == max_retries:
                    self.lh.add_list_log('errors', str(e))

    def _weighted_choice(self, choices_dict):
        try:
            choices = [(key, value) for (key, value) in choices_dict.iteritems()]
            r = random.uniform(0, 100)
            upto = 0
            for c, w in choices:
                if upto + w >= r:
                    return c
                upto += w
        except Exception as e:
            print traceback.format_exc(e)

    '''Static class variable that holds list of image hashes
    that are "no image" images.
    Should be loaded once when service is started, and subsequently
    used whenever needed, by _no_image(), in any sub-scraper.
    '''
    NO_IMAGE_HASHES = load_image_hashes()

    def __init__(self, **kwargs):
        self.product_page_url = kwargs['url']
        self.is_timeout = False

        self.lh = kwargs.get('lh')
        self.cache = kwargs.get('cache')
        self.crawl_date = self._get_crawl_date(kwargs.get('crawl_date'))

        # Set generic fields
        # directly (don't need to be computed by the scrapers)

        # Note: This needs to be done before merging with DATA_TYPES, below,
        # so that BASE_DATA_TYPES values can be overwritten by DATA_TYPES values
        # if needed. (more specifically overwrite functions for extracting certain data
        # (especially sellers-related fields))
        self._pre_set_fields()

        self.status_code = None

        self.proxy_config = kwargs.get('proxy_config') or {}
        self.proxy = None
        self.proxy_host = None
        self.proxy_port = None
        self.proxies = {}

        self.is_review_checked = False
        self.reviews = None
        self.review_count = 0
        self.average_review = None
        self.review_json = {}
        self.questions_total = 0
        self.questions_unanswered = 0

        self.sellpoints = 0
        self.rich_content = 0

        self.wc_360 = 0
        self.wc_emc = 0
        self.wc_pdf = 0
        self.wc_prodtour = 0
        self.wc_video = 0
        self.wc_images = []
        self.wc_pdfs = []
        self.wc_videos = []
        self.is_webcollage_checked = False

        self.is_redirect = 0

        self.session = None

        self.sentry_client = kwargs.get('sentry_client')

        # update data types dictionary to overwrite names of implementing methods for each data type
        # with implmenting function from subclass
        # precaution mesaure in case one of the dicts is not defined in a scraper
        if not hasattr(self, "DATA_TYPES"):
            self.DATA_TYPES = {}
        if not hasattr(self, "DATA_TYPES_SPECIAL"):
            self.DATA_TYPES_SPECIAL = {}
        self.ALL_DATA_TYPES = dict(self.BASE_DATA_TYPES.items() + self.DATA_TYPES.items() + self.DATA_TYPES_SPECIAL.items())
        # remove data types that were not declared in this superclass

        # TODO: do this more efficiently?
        for key in list(self.ALL_DATA_TYPES.keys()):
            if key not in self.BASE_DATA_TYPES:
                print "*******EXTRA data type: ", key
                del self.ALL_DATA_TYPES[key]

    def _pre_set_fields(self):
        '''Before the scraping for the particular site is started,
        some general fields are set directly.
        Fields set: date, url, status
        '''

        current_date = time.strftime("%Y-%m-%d %H:%M:%S")

        # Set fields for success respose

        # Generic fields
        self.BASE_DATA_TYPES['date'] = lambda x: current_date
        self.BASE_DATA_TYPES['url'] = lambda x: self._url()
        self.BASE_DATA_TYPES['status'] = lambda x: "success"
        self.BASE_DATA_TYPES['status_code'] = lambda x: self.status_code
        self.BASE_DATA_TYPES['crawl_date'] = lambda x: self.crawl_date

        self.BASE_DATA_TYPES['pl_name'] = lambda x: None
        self.BASE_DATA_TYPES['scraper_type'] = lambda x: None

        # Deprecated fields
        self.BASE_DATA_TYPES['owned'] = lambda x: self._owned()
        self.BASE_DATA_TYPES['owned_out_of_stock'] = lambda x: self._owned_out_of_stock()
        self.BASE_DATA_TYPES['site_product_id'] = lambda x: self._site_product_id()

        # Product title
        self.BASE_DATA_TYPES['product_title'] = lambda x: self._product_title()
        self.BASE_DATA_TYPES['title_seo'] = lambda x: self._product_title()

        # Inferred fields
        self.BASE_DATA_TYPES['in_stores_in_stock'] = lambda x: self._in_stores_in_stock()
        self.BASE_DATA_TYPES['marketplace_in_stock'] = lambda x: self._marketplace_in_stock()
        self.BASE_DATA_TYPES['site_online_in_stock'] = lambda x: self._site_online_in_stock()
        self.BASE_DATA_TYPES['marketplace_lowest_price'] = lambda x: self._marketplace_lowest_price()
        self.BASE_DATA_TYPES['primary_seller'] = lambda x: self._primary_seller()
        self.BASE_DATA_TYPES['selected_variant'] = lambda x: self._selected_variant()
        self.BASE_DATA_TYPES['in_page_360'] = lambda x: self._in_page_360()

        # These should be set after the 3 above, since they use their computed values
        self.BASE_DATA_TYPES['online_only'] = lambda x: self._online_only()
        self.BASE_DATA_TYPES['in_stores_only'] = lambda x: self._in_stores_only()
        self.BASE_DATA_TYPES['in_stock'] = lambda x: self._in_stock()

        # Fields whose implementation don't depend on site
        self.BASE_DATA_TYPES['meta_tags'] = lambda x: self._meta_tags()
        self.BASE_DATA_TYPES['meta_tag_count'] = lambda x: self._meta_tag_count()
        self.BASE_DATA_TYPES['canonical_link'] = lambda x: self._canonical_link()
        self.BASE_DATA_TYPES['proxy_service'] = lambda x: self._proxy_service()
        self.BASE_DATA_TYPES['htags'] = lambda x: self._htags()
        self.BASE_DATA_TYPES['keywords'] = lambda x: self._keywords()

        # Reviews
        self.BASE_DATA_TYPES['reviews'] = lambda x: self._reviews()
        self.BASE_DATA_TYPES['max_review'] = lambda x: self._max_review()
        self.BASE_DATA_TYPES['min_review'] = lambda x: self._min_review()
        self.BASE_DATA_TYPES['average_review'] = lambda x: self._average_review()
        self.BASE_DATA_TYPES['review_count'] = lambda x: self._review_count()

        # Counts
        self.BASE_DATA_TYPES['image_count'] = lambda x: self._image_count()
        self.BASE_DATA_TYPES['video_count'] = lambda x: self._video_count()
        self.BASE_DATA_TYPES['pdf_count'] = lambda x: self._pdf_count()
        self.BASE_DATA_TYPES['feature_count'] = lambda x: self._feature_count()
        self.BASE_DATA_TYPES['ingredient_count'] = lambda x: self._ingredient_count()
        self.BASE_DATA_TYPES['nutrition_fact_count'] = lambda x: self._nutrition_fact_count()
        self.BASE_DATA_TYPES['in_page_360_image_count'] = lambda x: self._in_page_360_image_count()

        # Price (one depends on the other)
        self.BASE_DATA_TYPES['price'] = lambda x: self._price()
        self.BASE_DATA_TYPES['price_amount'] = lambda x: self._price_amount()
        self.BASE_DATA_TYPES['price_currency'] = lambda x: self._price_currency()

        # Category name
        self.BASE_DATA_TYPES['category_name'] = lambda x: self._category_name()

        # Image alt text len
        self.BASE_DATA_TYPES['image_alt_text_len'] = lambda x: self._image_alt_text_len()

        # Sellpoints
        self.BASE_DATA_TYPES['sellpoints'] = lambda x: self._sellpoints()

        # Webcollage
        self.BASE_DATA_TYPES['wc_360'] = lambda x: self._wc_360()
        self.BASE_DATA_TYPES['wc_emc'] = lambda x: self._wc_emc()
        self.BASE_DATA_TYPES['wc_pdf'] = lambda x: self._wc_pdf()
        self.BASE_DATA_TYPES['wc_prodtour'] = lambda x: self._wc_prodtour()
        self.BASE_DATA_TYPES['wc_video'] = lambda x: self._wc_video()
        self.BASE_DATA_TYPES['webcollage_image_urls'] = lambda x: self._webcollage_image_urls()
        self.BASE_DATA_TYPES['webcollage_images_count'] = lambda x: self._webcollage_images_count()
        self.BASE_DATA_TYPES['webcollage_pdfs_count'] = lambda x: self._webcollage_pdfs_count()
        self.BASE_DATA_TYPES['webcollage_videos_count'] = lambda x: self._webcollage_videos_count()
        self.BASE_DATA_TYPES['webcollage'] = lambda x: self._webcollage()

        # Bullets
        self.BASE_DATA_TYPES['bullet_feature_1'] = lambda x: self._bullet_feature_X(1)
        self.BASE_DATA_TYPES['bullet_feature_2'] = lambda x: self._bullet_feature_X(2)
        self.BASE_DATA_TYPES['bullet_feature_3'] = lambda x: self._bullet_feature_X(3)
        self.BASE_DATA_TYPES['bullet_feature_4'] = lambda x: self._bullet_feature_X(4)
        self.BASE_DATA_TYPES['bullet_feature_5'] = lambda x: self._bullet_feature_X(5)
        self.BASE_DATA_TYPES['bullet_feature_6'] = lambda x: self._bullet_feature_X(6)
        self.BASE_DATA_TYPES['bullet_feature_7'] = lambda x: self._bullet_feature_X(7)
        self.BASE_DATA_TYPES['bullet_feature_8'] = lambda x: self._bullet_feature_X(8)
        self.BASE_DATA_TYPES['bullet_feature_9'] = lambda x: self._bullet_feature_X(9)
        self.BASE_DATA_TYPES['bullet_feature_10'] = lambda x: self._bullet_feature_X(10)
        self.BASE_DATA_TYPES['bullet_feature_11'] = lambda x: self._bullet_feature_X(11)
        self.BASE_DATA_TYPES['bullet_feature_12'] = lambda x: self._bullet_feature_X(12)
        self.BASE_DATA_TYPES['bullet_feature_13'] = lambda x: self._bullet_feature_X(13)
        self.BASE_DATA_TYPES['bullet_feature_14'] = lambda x: self._bullet_feature_X(14)
        self.BASE_DATA_TYPES['bullet_feature_15'] = lambda x: self._bullet_feature_X(15)
        self.BASE_DATA_TYPES['bullet_feature_16'] = lambda x: self._bullet_feature_X(16)
        self.BASE_DATA_TYPES['bullet_feature_17'] = lambda x: self._bullet_feature_X(17)
        self.BASE_DATA_TYPES['bullet_feature_18'] = lambda x: self._bullet_feature_X(18)
        self.BASE_DATA_TYPES['bullet_feature_19'] = lambda x: self._bullet_feature_X(19)
        self.BASE_DATA_TYPES['bullet_feature_20'] = lambda x: self._bullet_feature_X(20)
        self.BASE_DATA_TYPES['bullet_feature_count'] = lambda x: self._bullet_feature_count()

        # Questions
        self.BASE_DATA_TYPES['questions_total'] = lambda x: self._questions_total()
        self.BASE_DATA_TYPES['questions_unanswered'] = lambda x: self._questions_unanswered()

        # Set fields for error response
        self.ERROR_RESPONSE['date'] = current_date
        self.ERROR_RESPONSE['url'] = self.product_page_url
        self.ERROR_RESPONSE['status'] = "failure"
        self.ERROR_RESPONSE['crawl_date'] = self.crawl_date

    # extract product info from product page.
    # (note: this is for info that can be extracted directly from the product page, not content generated through javascript)
    # Additionally from extract_product_data(), this method extracts page load time.
    # parameter: types of info to be extracted as a list of strings, or None for all info
    # return: dictionary with type of info as key and extracted info as value
    def product_info(self, info_type_list = None):
        """Extract all requested data for this product, using subclass extractor methods
        Args:
            info_type_list (list of strings) list containing the types of data requested
        Returns:
            dictionary containing the requested data types as keys
            and the scraped data as values
        """

        #TODO: does this make sure page source is not extracted if not necessary?
        #      if so, should all functions returning null (in every case) be in DATA_TYPES_SPECIAL?

        # if no specific data types were requested, assume all data types were requested
        if not info_type_list:
            info_type_list = self.ALL_DATA_TYPES.keys()

        # copy of info list to send to _extract_product_data
        info_type_list_copy = list(info_type_list)

        # build page xml tree. also measure time it took and assume it's page load time (the rest is neglijable)
        time_start = time.time()
        self._extract_page_tree()
        time_end = time.time()

        if self.lh:
            try:
                self.lh.add_log('page_size', len(html.tostring(self.tree_html)))
            except Exception as e:
                print 'Failed to get page size', e

        # don't pass load time as info to be extracted by _extract_product_data
        return_load_time = "loaded_in_seconds" in info_type_list_copy
        if return_load_time:
            info_type_list_copy.remove("loaded_in_seconds")

        # extract product data
        ret_dict = self._extract_product_data(info_type_list_copy)

        if return_load_time:
            ret_dict["loaded_in_seconds"] = round(time_end - time_start, 2)
            if self.lh:
                self.lh.add_log('response_time', ret_dict["loaded_in_seconds"])

        # pack results into nested structure
        nested_results_dict = self._pack_returned_object(ret_dict)

        return nested_results_dict

    @staticmethod
    def _get_crawl_date(crawl_date):
        if crawl_date:
            try:
                crawl_date = date_parser.parse(crawl_date, yearfirst=True).strftime('%Y-%m-%d')
            except ValueError:
                print 'Wrong crawl_date format: {}'.format(crawl_date)
                crawl_date = time.strftime('%Y-%m-%d')
        else:
            crawl_date = time.strftime('%Y-%m-%d')
        return crawl_date

    @cached
    def _extract_page_tree(self):
        """Builds and sets as instance variable the xml tree of the product page

         method that returns xml tree of page, to extract the desired elemets from

        Returns:
            lxml tree object
        """
        if self.proxies:
            footlocker_url = self.__class__.__name__ == 'FootlockerScraper'
            self._extract_page_tree_with_retries(use_user_agent = not footlocker_url)
        else:
            wag_url = self.__class__.__name__ == 'WagScraper'
            jcpenney_url = self.__class__.__name__ == 'JcpenneyScraper'
            walmart_ca_url = self.__class__.__name__ == 'WalmartCAScraper'
            sears_url = self.__class__.__name__ == 'SearsScraper'
            dollargeneral_url = self.__class__.__name__ == 'DollarGeneralScraper'

            request = urllib2.Request(self.product_page_url)
            # set user agent to avoid blocking
            agent = ''
            if wag_url or sears_url:
                agent = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
            else:
                agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:24.0) Gecko/20140319 Firefox/24.0 Iceweasel/24.4.0'
            request.add_header('User-Agent', agent)

            if walmart_ca_url:
                request.add_header('Cookie', 'cookieLanguageType=en; deliveryCatchment=2000; marketCatchment=2001; walmart.shippingPostalCode=V5M2G7; zone=2')

            for i in range(self.MAX_RETRIES):
                try:
                    if jcpenney_url or dollargeneral_url:
                        contents = urllib2.urlopen(request, timeout=30).read()
                    else:
                        contents = urllib2.urlopen(request, timeout=20).read()

                    self.status_code = 200
                    if self.lh:
                        self.lh.add_log('status_code', 200)

                # handle urls with special characters
                except UnicodeEncodeError, e:

                    request = urllib2.Request(self.product_page_url.encode("utf-8"))
                    request.add_header('User-Agent', agent)
                    contents = urllib2.urlopen(request).read()

                except IncompleteRead, e:
                    continue
                except timeout:
                    self.is_timeout = True
                    self.ERROR_RESPONSE["failure_type"] = "Timeout"
                    return
                except urllib2.HTTPError, err:
                    self.status_code = err.code
                    if self.lh:
                        self.lh.add_log('status_code', err.code)
                    if err.code == 404:
                        self.ERROR_RESPONSE["failure_type"] = '404'
                        return
                    else:
                        continue
                try:
                    # replace NULL characters
                    contents = self._clean_null(contents).decode("utf8")
                    self.page_raw_text = contents
                    self.tree_html = html.fromstring(contents)
                except UnicodeError, e:
                    # If not utf8, try latin-1
                    try:
                        contents = self._clean_null(contents).decode("latin-1")
                        self.page_raw_text = contents
                        self.tree_html = html.fromstring(contents)

                    except UnicodeError, e:
                        # if string was neither utf8 or latin-1, don't decode
                        print "Warning creating html tree from page content: ", e.message

                        # replace NULL characters
                        contents = self._clean_null(contents)
                        self.page_raw_text = contents
                        self.tree_html = html.fromstring(contents)

                # if we got it we can exit the loop and stop retrying
                return


    def _clean_null(self, text):
        '''Remove NULL characters from text if any.
        Return text without the NULL characters
        '''
        if text.find('\00') >= 0:
            print "WARNING: page contained NULL characters. Removed"
            text = text.replace('\00','')
        return text

    def _find_between(self, s, first, last, offset=0):
        try:
            start = s.index(first, offset) + len(first)
            end = s.index(last, start)
            return s[start:end]
        except ValueError:
            return ""

    # Extract product info given a list of the type of info needed.
    # Return dictionary containing type of info as keys and extracted info as values.
    # This method is intended to act as a unitary way of getting all data needed,
    # looking to avoid generating the html tree for each kind of data (if there is more than 1 requested).
    def _extract_product_data(self, info_type_list):
        """Extracts data for current product:
        either from page source given its xml tree
        or using other requests defined in each specific function
        Args:
            info_type_list: list of strings containing the requested data
        Returns:
            dictionary containing the requested data types as keys
            and the scraped data as values
        """

        # do anything that needs to be done after page extraction but before other methods
        try:
            self._pre_scrape()
        except:
            print traceback.format_exc()

        results_dict = {}

        # if timeout is set, return error response
        if self.is_timeout:
            return self.ERROR_RESPONSE

        # if it's not a valid product page, abort
        try:
            if self.not_a_product():
                self.ERROR_RESPONSE["failure_type"] = 'Not a product'
                return self.ERROR_RESPONSE
        except:
            self.ERROR_RESPONSE["failure_type"] = 'Not a product'
            return self.ERROR_RESPONSE

        for info in info_type_list:
            try:
                if isinstance(self.ALL_DATA_TYPES[info], (str, unicode)):
                    _method_to_call = getattr(self, self.ALL_DATA_TYPES[info])
                    results = _method_to_call()
                else:  # callable?
                    _method_to_call = self.ALL_DATA_TYPES[info]
                    results = _method_to_call(self)
            except IndexError, e:
                sys.stderr.write("ERROR: No " + info + " for " + self.product_page_url.encode("utf-8") + ":\n" + str(e) + "\n")
                results = None
                if self.sentry_client:
                    self.sentry_client.captureException()
            except Exception, e:
                sys.stderr.write("ERROR: Unknown error extracting " + info + " for " + self.product_page_url.encode("utf-8") + ":\n" + str(e) + "\n")
                results = None
                if self.sentry_client:
                    self.sentry_client.captureException()

            results_dict[info] = results

        if self.sentry_client:
            self.sentry_client.context.clear()

        if not results_dict.get('no_longer_available') and \
                not results_dict.get('temporary_unavailable') and \
                not results_dict.get('product_title') and \
                not results_dict.get('image_urls'):
            self.ERROR_RESPONSE['failure_type'] = 'NullFields'
            return self.ERROR_RESPONSE

        return results_dict

    # pack returned object data types into nested dictionary according to specific format
    # arguments: data_types_dict - contains original flat response dictionary
    # returns: result nested response dictionary
    def _pack_returned_object(self, data_types_dict):

        # pack input object into nested structure according to structure above
        nested_object = {}
        for root_key in self.DICT_STRUCTURE.keys():
            for subkey in self.DICT_STRUCTURE[root_key]:
                # only add this if this data type was requested
                if subkey in data_types_dict:
                    if root_key not in nested_object:
                        nested_object[root_key] = {}

                    nested_object[root_key][subkey] = data_types_dict[subkey]
                    # print subkey
                    # print data_types_dict.keys()
                    del data_types_dict[subkey]
        # now add leftover keys to root level
        nested_object.update(data_types_dict)

        return nested_object

    # base function to test input URL is valid.
    # always returns True, to be used for subclasses where it is not implemented
    # it should be implemented by subclasses with specific code to validate the URL for the specific site
    def check_url_format(self):
        return True

    def _pre_scrape(self):
        pass

    def not_a_product(self):
        """Abstract method.
        Checks if current page is not a valid product page
        (either an unavailable product page, or some other type of content)
        To be implemented by each scraper specifically for its site.
        Returns:
            True if not a product page,
            False otherwise
        """

        return False

    def _site_product_id(self):
        if hasattr(self, '_product_id'):
            return self._product_id()

    def _product_title(self):
        if hasattr(self, '_product_name'):
            return self._product_name()

    def _image_alt_text_len(self):
        if hasattr(self, '_image_alt_text'):
            image_alt_text = self._image_alt_text()
            if image_alt_text:
                return [len(i) for i in image_alt_text]

    def _review_id(self):
        return self._product_id()

    def _reviews(self, review_url = None, review_id = None):
        if self.is_review_checked:
            return self.reviews

        self.is_review_checked = True

        try:
            review_id = review_id or self._review_id()

            if not review_url and hasattr(self, 'REVIEW_URL'):
                review_url = self.REVIEW_URL.format(review_id)

            if review_url:
                if 'batch.json' in review_url:
                    data = self._request(review_url, use_proxies=False).json()
                    self.review_json = data['BatchedResults']['q0']['Results'][0]

                    review_stats = self.review_json.get('FilteredReviewStatistics') or \
                            self.review_json['ReviewStatistics']

                    self.review_count = review_stats['TotalReviewCount']
                    average_review = review_stats['AverageOverallRating']

                    if average_review:
                        self.average_review = round(average_review, 1)

                    if self.review_count:
                        rating_mark_list = [[5, 0], [4, 0], [3, 0], [2, 0], [1, 0]]
                        for item in review_stats['RatingDistribution']:
                            rating_mark_list[5 - item['RatingValue']][1] = item['Count']

                        self.reviews = rating_mark_list

                elif 'powerreviews.com' in review_url:
                    if hasattr(self, '_extract_auth_key'):
                        auth_pwr = self._extract_auth_key()
                        data = self._request(review_url,
                                             headers={'authorization': auth_pwr},
                                             use_proxies=False).json()

                        self.review_json = data.get('results')[0].get('rollup', {})

                        average_review = self.review_json.get('average_rating')
                        self.review_count = self.review_json.get('review_count', 0)

                        if average_review:
                            self.average_review = round(average_review, 1)

                        if self.review_count:
                            reviews = [[5 - i, rating] for i, rating in
                                       enumerate(reversed(self.review_json.get('rating_histogram', [])))]

                            self.reviews = reviews

                else:
                    resp = self._request(review_url, use_proxies=False)

                    try:
                        self.review_json = resp.json()
            
                        products = self.review_json.get("Includes", {}).get("Products", {})

                        if review_id in products:
                            reviews = products[review_id].get("ReviewStatistics", {})
                        else:
                            reviews = products.values()[0].get("ReviewStatistics", {})

                        self.review_count = reviews['TotalReviewCount']

                        if self.review_count:
                            self.average_review = reviews['AverageOverallRating']

                            self.reviews = []

                            for i in range(5, 0, -1):
                                review_found = False

                                for review in reviews['RatingDistribution']:
                                    if review['RatingValue'] == i:
                                        self.reviews.append([i, review['Count']])
                                        review_found = True

                                if not review_found:
                                    self.reviews.append([i, 0])

                    except:
                        contents = resp.content

                        review_html = re.search('"BVRRSecondaryRatingSummarySourceID":" (.+?)"},\ninitializers={', contents)
                        if review_html:
                            review_html = html.fromstring(review_html.group(1))

                            reviews_by_mark = review_html.xpath("//*[contains(@class, 'BVRRHistAbsLabel')]/text()")
                            reviews_by_mark = reviews_by_mark[:5]
                            reviews = [[5 - i, int(re.findall('\d+', mark)[0])] for i, mark in enumerate(reviews_by_mark)]

                            if not reviews:
                                reviews_by_mark = review_html.xpath("//*[contains(@class, 'BVDINumber')]/text()")
                                reviews_by_mark = [re.search('\d+', r).group() for r in reversed(reviews_by_mark[:5])]
                                if len(reviews_by_mark) == 5:
                                    reviews = [[5 - i, int(re.findall('\d+', mark)[0])] for i, mark in enumerate(reviews_by_mark)]
                                else:
                                    reviews_by_mark = review_html.xpath('//span[contains(@itemprop,"ratingValue")]/text()')
                                    if reviews_by_mark:
                                        reviews = [[1,0],[2,0],[3,0],[4,0],[5,0]]
                                        for x in reviews_by_mark:
                                            num = re.search('\d+', x)
                                            if num:
                                                reviews[int(num.group()) - 1][1] += 1

                            if reviews:
                                self.reviews = reviews

                            start_index = contents.find("webAnalyticsConfig:") + len("webAnalyticsConfig:")
                            end_index = contents.find(",\nwidgetInitializers:initializers", start_index)

                            self.review_json = json.loads(contents[start_index:end_index])

                            self.review_count = self.review_json["jsonData"]["attributes"]["numReviews"]
                            average_review = round(self.review_json["jsonData"]["attributes"]["avgRating"], 1)

                            if average_review:
                                self.average_review = average_review

        except:
            print traceback.format_exc()

        return self.reviews

    def _max_review(self):
        reviews = self._reviews()
        if reviews:
            return max([key[0] for key in reviews if key[1] > 0])

    def _min_review(self):
        reviews = self._reviews()
        if reviews:
            return min([key[0] for key in reviews if key[1] > 0])

    def _average_review(self):
        self._reviews()
        if self.average_review:
            return round(self.average_review, 1)
        if self.reviews:
            value = sum(r[0]*r[1] for r in self.reviews)
            count = sum(r[1] for r in self.reviews)
            return round(float(value) / count, 1)

    def _review_count(self):
        self._reviews()
        if self.review_count:
            return self.review_count
        if self.reviews:
            return sum(r[1] for r in self.reviews)
        return 0

    def _image_count(self):
        try:
            return len(self._image_urls())
        except:
            pass
        return 0

    def _video_count(self):
        try:
            return len(self._video_urls())
        except:
            pass
        return 0

    def _pdf_count(self):
        try:
            return len(self._pdf_urls())
        except:
            pass
        return 0

    def _feature_count(self):
        try:
            return len(self._features())
        except:
            pass
        return 0

    def _ingredient_count(self):
        try:
            return len(self._ingredients())
        except:
            pass
        return 0

    def _nutrition_fact_count(self):
        try:
            return len(self._nutrition_facts())
        except:
            pass
        return 0

    def _in_page_360_image_count(self):
        try:
            return len(self._in_page_360_image_urls())
        except:
            pass
        return 0

    def _in_page_360(self):
        if hasattr(self, '_in_page_360_image_urls'):
            try:
                if self._in_page_360_image_urls():
                    return 1
            except:
                pass
        return 0

    def _price(self):
        if hasattr(self, '_price_amount'):
            price = self._price_amount()
            if price:
                try:
                    currency = self._price_currency()
                except:
                    currency == 'USD'
                if currency == 'EUR':
                    return '{}{:2,.2f}'.format('€', price)
                elif currency == 'TL':
                    return '{}{:2,.2f}'.format('TL', price)
                elif currency == 'GBP':
                    return '{}{:2,.2f}'.format('£', price)
                elif currency == 'SGD':
                    return '{}{:2,.2f}'.format('SGD', price)
                return '${:2,.2f}'.format(price)

    def _price_amount(self):
        if hasattr(self, '_price'):
            price = self._price()
            if price:
                price = price.split('-')[0]
                return float(re.search('[\d\.,]+', price).group().replace(',',''))

    def _price_currency(self):
        if hasattr(self, 'tree_html'):
            for xpath in ['//*[@itemprop="priceCurrency"]/@content',
                    '//meta[@property="og:price:currency"]/@content']:
                price_currency = self.tree_html.xpath(xpath)
                if price_currency:
                    return price_currency[0]
        return 'USD'

    def _category_name(self):
        if hasattr(self, '_categories'):
            categories = self._categories()
            if categories:
                return categories[-1]

    def _sellpoints(self):
        return self.sellpoints

    def _wc_360(self):
        return self.wc_360

    def _wc_emc(self):
        return self.wc_emc

    def _wc_pdf(self):
        if self._webcollage_pdfs_count():
            return 1
        return self.wc_pdf

    def _wc_prodtour(self):
        return self.wc_prodtour

    def _wc_video(self):
        if self._webcollage_videos_count():
            return 1
        return self.wc_video

    def _webcollage_image_urls(self):
        return self.wc_images or None

    def _webcollage_images_count(self):
        return len(self.wc_images)

    def _webcollage_pdfs_count(self):
        return len(self.wc_pdfs)

    def _webcollage_videos_count(self):
        return len(self.wc_videos)

    def _webcollage(self):
        if any([self._wc_360(),
                self._wc_emc(),
                self._wc_pdf(),
                self._wc_prodtour(),
                self._wc_video(),
                self._webcollage_images_count(),
                self._webcollage_pdfs_count(),
                self._webcollage_videos_count()]):
            return 1

        return 0

    def _bullet_feature_X(self, i):
        if hasattr(self, '_bullets'):
            try:
                bullets = self._bullets()
                if bullets:
                    bullets = bullets.split('\n')
                    if len(bullets) > i - 1:
                        return bullets[i - 1]
            except:
                pass

    def _bullet_feature_count(self):
        if hasattr(self, '_bullets'):
            try:
                bullets = self._bullets()
                if bullets:
                    return len(bullets.split('\n'))
            except:
                pass
            return 0

    def _image_hash(self, image_url, walmart=None):
        """Computes hash for an image.
        To be used in _no_image, and for value of _image_hashes
        returned by scraper.
        Returns string representing hash of image.

        :param image_url: url of image to be hashed
        """
        return str(MurmurHash.hash(fetch_bytes(image_url, walmart)))

    # Checks if image given as parameter is "no  image" image
    # To be used by subscrapers
    def _no_image(self, image_url, walmart=None):
        """Verifies if image with URL given as argument is
        a "no image" image.

        Certain products have an image that indicates "there is no image available"
        a hash of these "no-images" is saved to a json file
        and new images are compared to see if they're the same.

        Uses "fetch_bytes" function from the script used to compute
        hashes that images here are compard against.

        Returns:
            True if it's a "no image" image, False otherwise
        """
        print "***********test start*************"
        try:
            first_hash = self._image_hash(image_url, walmart)
        except IOError:
            return False
        print first_hash
        print "***********test end*************"

        if first_hash in self.NO_IMAGE_HASHES:
            print "not an image"
            return True
        else:
            return False

    def is_energy_label(self, image_url):
        """Verifies if image with URL given as argument is an
        energy label image.

        Returns:
           True if it's an energy label image, False otherwise
        """

        # TODO: implement
        return False

    def _url(self):
        return self.product_page_url

    def _owned(self):
        '''General function for setting value of legacy field "owned".
        It will be inferred from value of "site_online_in_stock" field.
        Method can be overwritten by scraper class if different implementation
        is available.
        '''

        # extract site_online_in_stock and stores_in_stock
        # owned will be 1 if any of these is 1
        return (self.ALL_DATA_TYPES['site_online'](self) or self.ALL_DATA_TYPES['in_stores'](self))


    def _owned_out_of_stock(self):
        '''General function for setting value of legacy field "owned_out_of_stock".
        It will be inferred from value of "site_online_out_of_stock" field.
        Method can be overwritten by scraper class if different implementation
        is available.
        '''

        # owned_out_of_stock is true if item is out of stock online and in stores
        try:
            site_online = self.ALL_DATA_TYPES['site_online'](self)
        except:
            site_online = None

        try:
            site_online_in_stock = self.ALL_DATA_TYPES['site_online_in_stock'](self)
        except:
            site_online_in_stock = None

        try:
            in_stores = self.ALL_DATA_TYPES['in_stores'](self)
        except:
            in_stores = None

        try:
            in_stores_in_stock = self.ALL_DATA_TYPES['in_stores_in_stock'](self)
        except:
            in_stores_in_stock = None


        if (site_online or in_stores) and (not site_online_in_stock) and (not in_stores_in_stock):
            return 1
        return 0


    def _site_online_in_stock(self):
        '''General function for setting value of field "site_online_in_stock".
        It will be inferred from other sellers fields.
        Method can be overwritten by scraper class if different implementation
        is available.
        '''

        # compute necessary fields
        # Note: might lead to calling these functions twice.
        # But they should be inexpensive
        try:
            site_online = self.ALL_DATA_TYPES['site_online'](self)
        except:
            site_online = None

        try:
            site_online_out_of_stock = self.ALL_DATA_TYPES['site_online_out_of_stock'](self)
        except:
            site_online_out_of_stock = None

        # site_online is 1 and site_online_out_of_stock is 0
        if site_online == 1 and site_online_out_of_stock == 0:
            return 1
        if site_online == 1 and site_online_out_of_stock == 1:
            return 0

        return None

    def _in_stores_in_stock(self):
        '''General function for setting value of field "in_stores_in_stock".
        It will be inferred from other sellers fields.
        Method can be overwritten by scraper class if different implementation
        is available.
        '''

        # compute necessary fields
        # Note: might lead to calling these functions twice.
        # But they should be inexpensive
        try:
            in_stores = self.ALL_DATA_TYPES['in_stores'](self)
        except:
            in_stores = None

        try:
            in_stores_out_of_stock = self.ALL_DATA_TYPES['in_stores_out_of_stock'](self)
        except:
            in_stores_out_of_stock = None

        # in_stores is 1 and in_stores_out_of_stock is 0
        if in_stores == 1 and in_stores_out_of_stock == 0:
            return 1
        if in_stores == 1 and in_stores_out_of_stock == 1:
            return 0

        return None

    def _marketplace_in_stock(self):
        '''General function for setting value of field "in_stores_in_stock".
        It will be inferred from other sellers fields.
        Method can be overwritten by scraper class if different implementation
        is available.
        '''

        # compute necessary fields
        # Note: might lead to calling these functions twice.
        # But they should be inexpensive
        try:
            marketplace = self.ALL_DATA_TYPES['marketplace'](self)
        except:
            marketplace = None

        try:
            marketplace_out_of_stock = self.ALL_DATA_TYPES['marketplace_out_of_stock'](self)
        except:
            marketplace_out_of_stock = None

        # marketplace is 1 and marketplace_out_of_stock is 0
        if marketplace == 1 and marketplace_out_of_stock == 0:
            return 1
        if marketplace == 1 and marketplace_out_of_stock == 1:
            return 0

        return None

    def _get_sellers_types(self):
        '''Uses scraper extractor functions to get values for sellers type:
        in_stores, site_online and marketplace.
        (To be used by other functions that use this info)
        Returns dictionary containing 1/0/None values for these seller fields.
        '''

        # compute necessary fields
        # Note: might lead to calling these functions twice.
        # But they should be inexpensive
        try:
            marketplace = self.ALL_DATA_TYPES['marketplace'](self)
        except:
            marketplace = None

        try:
            site_online = self.ALL_DATA_TYPES['site_online'](self)
        except:
            site_online = None

        try:
            in_stores = self.ALL_DATA_TYPES['in_stores'](self)
        except:
            in_stores = None

        return {'marketplace' : marketplace, 'site_online' : site_online, 'in_stores' : in_stores}

    def _marketplace_lowest_price(self):
        if hasattr(self, '_marketplace_prices'):
            return min(self._marketplace_prices())

    def _primary_seller(self):
        if hasattr(self, '_marketplace_sellers'):
            return self._marketplace_sellers()[0]

    def _selected_variant(self):
        if hasattr(self, '_variants'):
            for variant in self._variants() or [{}]:
                if variant.get('selected'):
                    return ' '.join(variant['properties'].values())

    def _online_only(self):
        '''General function for setting value of field "online_only".
        It will be inferred from other sellers fields.
        Method can be overwritten by scraper class if different implementation is available.
        '''

        # compute necessary fields
        sellers = self._get_sellers_types()
        # if any of the seller types is None, return None (cannot be determined)
        if any(v is None for v in sellers.values()):
            return None

        if (sellers['site_online'] == 1 or sellers['marketplace'] == 1) and \
            sellers['in_stores'] == 0:
            return 1
        return 0

    def _in_stores_only(self):
        '''General function for setting value of field "in_stores_only".
        It will be inferred from other sellers fields.
        Method can be overwritten by scraper class if different implementation is available.
        '''

        # compute necessary fields
        sellers = self._get_sellers_types()
        # if any of the seller types is None, return None (cannot be determined)
        if any(v is None for v in sellers.values()):
            return None

        if (sellers['site_online'] == 0 and sellers['marketplace'] == 0) and \
            sellers['in_stores'] == 1:
            return 1
        return 0

    def _in_stock(self):
        '''General function for setting value of field "in_stores_only".
        It will be inferred from other sellers fields.
        Method can be overwritten by scraper class if different implementation is available.
        '''

        # compute necessary fields
        # Note: might lead to calling these functions twice.
        # But they should be inexpensive
        try:
            marketplace_in_stock = self.ALL_DATA_TYPES['marketplace_in_stock'](self)
        except:
            marketplace_in_stock = None

        try:
            site_online_in_stock = self.ALL_DATA_TYPES['site_online_in_stock'](self)
        except:
            site_online_in_stock = None

        try:
            in_stores_in_stock = self.ALL_DATA_TYPES['in_stores_in_stock'](self)
        except:
            in_stores_in_stock = None

        if any([marketplace_in_stock, site_online_in_stock, in_stores_in_stock]):
            return 1
        if all(v is None for v in [marketplace_in_stock, site_online_in_stock, in_stores_in_stock]):
            return None

        return 0

    def _meta_tags(self):
        if hasattr(self, 'tree_html'):
            return map(lambda x:x.values(), self.tree_html.xpath('//meta[not(@http-equiv)]'))

    def _meta_tag_count(self):
        meta_tags = self._meta_tags()
        return len(meta_tags) if meta_tags else 0

    def _canonical_link(self):
        if hasattr(self, 'tree_html'):
            canonical = self.tree_html.xpath('//link[@rel="canonical"]/@href')
            return canonical[0] if canonical else None

    def _htags(self):
        if hasattr(self, 'tree_html'):
            htags_dict = {}
            htags_dict["h1"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h1//text()[normalize-space()!='']"))
            htags_dict["h2"] = map(lambda t: self._clean_text(t), self.tree_html.xpath("//h2//text()[normalize-space()!='']"))
            return htags_dict

    def _keywords(self):
        if hasattr(self, 'tree_html'):
            keywords = self.tree_html.xpath('//meta[@name="keywords"]/@content')
            return keywords[0] if keywords else None
 

if __name__=="__main__":
    print main(sys.argv)
