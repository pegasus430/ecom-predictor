#
# This is a slightly modified version of the FilesystemCacheStorage class
# from scrapy.contrib. We separate cache folders by search terms.
#

# TODO:
# - packing appropriate cache dirs;
# - uploading them to S3 on spider close;
# - downloading cache dirs and unpacking them;
# - executing the crawler against the cached dir;
# - error handling (blank page?); solving captcha issues at amazon
# - CH support
#

import os
import sys
import datetime
import shutil
import hashlib
from exceptions import OSError

from scrapy.contrib.httpcache import *
from scrapy.utils import gz

import settings
from cache_models import list_db_cache

UTC_NOW = datetime.datetime.utcnow()  # we don't init it in a local method
                                      # to avoid spreading one job across
                                      #  2 dates, if it runs for too long


def get_cache_map(spider=None, term=None, date=None):
    """ Get cache data, spider -> date -> searchterm
    :return: dict
    """
    _started = datetime.datetime.now()
    cache_map = list_db_cache(spider=spider, term=term, date=date)
    _finished = datetime.datetime.now()
    print('    [cache map finished in %s seconds]'
          % (_finished - _started).total_seconds())
    return cache_map


def _get_searchterms_str_or_product_url():
    args_term = [a for a in sys.argv if 'searchterms_str' in a]
    args_url = [a for a in sys.argv if 'product_url' in a]
    args_urls = [a for a in sys.argv if 'products_url' in a]
    if args_term:
        args = args_term
    elif args_url:
        args = args_url
    else:
        args = args_urls
    if not args:
        return
    arg_name, arg_value = args[0].split('=', 1)
    if args_urls:
        _urls = arg_value.split('||||')  # break into individual URLs
        _urls = sorted(_urls)
        arg_value = '||||'.join(_urls)
    arg_value = hashlib.md5(arg_value).hexdigest() + '__' + arg_value
    if args_url or args_urls:
        arg_value = _slugify(arg_value)[7:67]  # reduce the length of the url(s)
    return arg_value


def _get_load_from_date():
    arg = [a for a in sys.argv if 'load_raw_pages' in a]
    if arg:
        arg = arg[0].split('=')[1].strip()
        return datetime.datetime.strptime(arg, '%Y-%m-%d')


def _slugify(value, replaces='\'"~@#$%^&*()[] _-/\:\?\=\,\.'):
    for char in replaces:
        value = value.replace(char, '-')
    return value


def clear_local_cache(cache_dir, spider, UTC_NOW=UTC_NOW):
    if _get_searchterms_str_or_product_url():
        if os.path.exists(get_partial_request_path(
                settings.HTTPCACHE_DIR, spider, UTC_NOW)):
            shutil.rmtree(get_partial_request_path(
                cache_dir, spider, UTC_NOW))
            print('Local cache cleared')


def get_partial_request_path(cache_dir, spider, UTC_NOW=UTC_NOW):
    searchterms_str = _slugify(_get_searchterms_str_or_product_url())
    utc_today = UTC_NOW.strftime('%Y-%m-%d')
    if searchterms_str:
        return os.path.join(
            cache_dir, spider.name, utc_today, searchterms_str)  # TODO: replace searchterms_str with double hash (md5 and sha1); or do it in _get_searchterms_str_or_product_url ?
    else:
        return os.path.join(
            cache_dir, spider.name, utc_today, 'url')


def get_request_path_with_date(cache_dir, spider, request, UTC_NOW=UTC_NOW):
    key = request_fingerprint(request)
    result = os.path.join(
        get_partial_request_path(cache_dir, spider, UTC_NOW),
        #_slugify(request.url),  # TODO: removeme! shouldn't be too long to avoid truncating keys!
        key[0:2], key
    )
    # check max filename length and truncate it if needed
    if not os.path.exists(result):
        try:
            os.makedirs(result)
        except OSError as e:
            if 'too long' in str(e).lower():
                result = result[0:235]  # depends on OS! Works for Linux
                print('Cache filename truncated to 235 chars!', result)
    return result


class CustomFilesystemCacheStorage(FilesystemCacheStorage):
    """ For local spider usage (mostly for development purposes) """

    def _get_request_path(self, spider, request):
        key = request_fingerprint(request)
        searchterms_str = _slugify(_get_searchterms_str_or_product_url())
        if searchterms_str:
            result = os.path.join(self.cachedir, spider.name, searchterms_str,
                                  key[0:2], key)
        else:
            result = os.path.join(self.cachedir, spider.name, key[0:2], key)
        print('    retrieving cache file', result)
        return result


class S3CacheStorage(FilesystemCacheStorage):
    """ For uploading cache to S3 """

    def _get_request_path(self, spider, request):
        utcnow = _get_load_from_date()
        if not utcnow:  # not loading from cache, but saving
            global UTC_NOW
            utcnow = UTC_NOW
        return get_request_path_with_date(self.cachedir, spider, request,
                                          utcnow)

    def store_response(self, spider, request, response):
        # store request URL as an empty file
        rpath = self._get_request_path(spider, request)
        if not os.path.exists(rpath):
            os.makedirs(rpath)
        fname = '__MARKER_URL__' + _slugify(request.url)
        fname = fname[0:254]
        fname = os.path.join(rpath, fname)
        with open(fname, 'w') as f:
            f.write(response.url)
        return super(S3CacheStorage, self).store_response(spider, request, response)


class CustomCachePolicy(DummyPolicy):
    """ For not caching amazon captcha """

    def should_cache_response(self, response, request):
        # all gzipped strings start with this symbols
        gzip_line_start = '\037\213'
        body = response.body
        if body.startswith(gzip_line_start):
            body = gz.gunzip(body)
        if '.images-amazon.com/captcha/' in body:
            return False
        return super(CustomCachePolicy, self).should_cache_response(
            response, request)
