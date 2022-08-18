import re

import w3lib.url


def default(url):
    return w3lib.url.canonicalize_url(url)


def amazon(url):
    if 'ppw=fresh' in url:
        url = w3lib.url.url_query_cleaner(url, parameterlist=('ppw', ))
    return w3lib.url.canonicalize_url(url)

def hayneedle(url):
    url = w3lib.url.url_query_cleaner(url)
    return w3lib.url.canonicalize_url(url)

def jcpenney(url):
    if 'prod.jump' in url:
        url = w3lib.url.url_query_cleaner(url, parameterlist=('ppId', ))
    return w3lib.url.canonicalize_url(url)

def johnlewis(url):
    if re.search(r'/p\d+', url):
        url = w3lib.url.url_query_cleaner(
            url, parameterlist=('colour', 'selectedSize', 'sku')
        )
    return w3lib.url.canonicalize_url(url)

def samsclub(url):
    if re.search(r'/prod\d+\.ip', url):
        url = w3lib.url.url_query_cleaner(url)
    return w3lib.url.canonicalize_url(url)

def walmart(url):
    url = w3lib.url.url_query_cleaner(url)
    return w3lib.url.canonicalize_url(url)
