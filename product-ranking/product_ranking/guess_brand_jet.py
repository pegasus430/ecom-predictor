# ~~coding=utf-8~~

from pkg_resources import resource_string
import csv
import traceback

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

def brand_in_list(brand):
    return _brand_in_list(brand)

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
    # take `max_words` first words; `max_words`-1; `max_words`-2; and so on
    for cur_words in list(reversed(range(max_words)))[0:-1]:
        partial_brand_left = text.split(' ')[0:cur_words]
        partial_brand_right = text.split(' ')[cur_words-1: max_words]

        partial_brand_left = ' '.join(partial_brand_left)
        partial_brand_right = ' '.join(partial_brand_right)

        found_brand_left = _find_brand(partial_brand_left)
        found_brand_right = _find_brand(partial_brand_right)

        if found_brand_left:
            return found_brand_left

        elif found_brand_right:
            return found_brand_right

        elif partial_brand_left and _brand_in_list(partial_brand_left):
            return partial_brand_left

        elif partial_brand_right and _brand_in_list(partial_brand_right):
            return partial_brand_right
    # nothing has been found - try to get rid of 'the'
    if text.lower().startswith('the '):
        text = text[4:]
    for cur_words in list(reversed(range(max_words)))[0:-1]:
        partial_brand_left = text.split(' ')[0:cur_words]
        partial_brand_right = text.split(' ')[cur_words - 1: max_words]

        partial_brand_left = ' '.join(partial_brand_left)
        partial_brand_right = ' '.join(partial_brand_right)

        found_brand_left = _find_brand(partial_brand_left)
        found_brand_right = _find_brand(partial_brand_right)

        if found_brand_left:
            return found_brand_left

        elif found_brand_right:
            return found_brand_right

        elif partial_brand_left and _brand_in_list(partial_brand_left):
            return partial_brand_left

        elif partial_brand_right and _brand_in_list(partial_brand_right):
            return partial_brand_right