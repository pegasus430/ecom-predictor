#!/usr/bin/python

# Checks if the image of a product is relevant for it or not

import urllib2
#TODO: if we need thread safety, we need to switch to urllib
from lxml import html

SEARCH_URL = 'https://www.google.com/searchbyimage?site=search&image_url=%s'
'''URL for Google reverse image search results'''

def _get_search_response(image_url):
    '''Make a search request on google reverse image search,
    return the contents of the response page.
    '''

    search_url = SEARCH_URL % image_url

    request = urllib2.Request(search_url)
    request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64; rv:24.0) Gecko/20140319 Firefox/24.0 Iceweasel/24.4.0')
    response_text = urllib2.urlopen(request).read()
    return response_text


def get_keywords(image_url):
    '''Get text keywords related to the image,
    as returned by google reverse image search
    '''

    contents = _get_search_response(image_url)
    tree = html.fromstring(contents)
    keywords = tree.xpath("//a[contains(@class, 'Ub')]/text()")[0]
    return keywords

if __name__=='__main__':

    print get_keywords("http://ecx.images-amazon.com/images/I/71GGHbswZLL._SL1500_.jpg")