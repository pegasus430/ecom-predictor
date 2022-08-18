# ~~coding=utf-8~~

from pkg_resources import resource_string
import csv
import traceback
import re

BRANDS = ()


def _load_brands(fname):
    """ Fills the global BRANDS variable """
    global BRANDS
    if BRANDS:  # don't perform expensive load operations
        return
    BRANDS = resource_string(__name__, fname)
    BRANDS = BRANDS.split('\n')
    BRANDS = [b.lower().strip().rstrip() for b in BRANDS]
    BRANDS = set(BRANDS)  # set lookup is faster than list lookup


def _brand_in_list(brand):
    """ Utility method to check if the given brand is in the list """
    global BRANDS
    return brand.lower() in BRANDS


def _find_brand(brand, fname='data/brands.csv'):
    try:
        data = resource_string(__name__, fname)
        brandsreader = csv.reader(data.split('\n'), delimiter=',')
        for row in brandsreader:
            for x in row:
                if unicode(x, encoding='utf-8') == brand:
                    return row[0]
    except:
        print traceback.format_exc()


def guess_brand_from_first_words(text, fname='data/brands.list', max_words=7):
    """ Tries to guess the brand in the given text, assuming that the
         given text starts with the brand name.
        Example: Apple Iphone 16GB
        Should normally return: Apple
    :param text: str containing brand
    :param max_words: int, longest brand possible
    :return: str or None
    """
    global BRANDS
    _load_brands(fname)
    # prepare the data
    if isinstance(text, str):
        text = text.decode('utf8')
    text = text.replace(u'®', ' ').replace(u'©', ' ').replace(u'™', ' ')
    text = text.strip().replace('  ', ' ')

    # nothing has been found from first word - try to get rid of first word
    while True:
        for cur_words in list(reversed(range(max_words)))[0:-1]:
            partial_brand = text.split(' ')[0:cur_words]
            partial_brand = ' '.join(partial_brand)
            found_brand = _find_brand(partial_brand)
            if found_brand:
                return found_brand
            elif _brand_in_list(partial_brand):
                return partial_brand
        text = text.split(' ')
        if len(text) > 1:
            text = ' '.join(text[1:])
        else:
            break


def find_brand(brand):
    brand = re.sub(r' +', ' ', brand)
    brand_first_word = brand.split(' ')[0]
    guess_brand = _find_brand(brand_first_word)

    return guess_brand if guess_brand else brand
