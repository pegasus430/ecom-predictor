from __future__ import absolute_import
import hashlib
from binascii import hexlify
from struct import pack
from zlib import crc32
import datetime

import six
# from w3lib.util import to_native_str, to_bytes

def parse_url(url, encoding=None):
    """Return urlparsed url from the given argument (which could be an
    already parsed url).
    """
    parse = six.moves.urllib.parse
    return url if isinstance(url, parse.ParseResult) \
        else parse.urlparse(to_native_str(url))


def get_crc32(name):
    """Signed crc32 of bytes or unicode.

    In python 3, return the same number as in python 2, converting to
    [-2**31, 2**31-1] range. This is done to maintain backwards
    compatibility with python 2, since checksums are stored in the
    database, so this allows to keep the same database schema.
    """
    return to_signed32(crc32(to_bytes(name, 'utf-8', 'ignore')))


def to_signed32(x):
    """ If x is an usigned 32-bit int, convert it to a signed 32-bit.
    """
    return x - 0x100000000 if x > 0x7fffffff else x


def sha1(key):
    return to_bytes(hashlib.sha1(to_bytes(key, 'utf8')).hexdigest())


def hostname_local_fingerprint(url):
    """Calculates fingerprint.

    This function is used for URL fingerprinting, which serves to
    uniquely identify the document in storage.

    Default option is set to make use of HBase block cache. It is
    expected to fit all the documents of average website within one
    cache block, which can be efficiently read from disk once.

    Arguments:
        url (str): URL to calculate the fingerprint from.

    Returns:
        str: 20 bytes hex string. First 4 bytes as Crc32 from host,
            and rest is MD5 from rest of the URL.
    Raises:
        TypeError: `url` must be a string
    """
    if not isinstance(url, six.string_types):
        raise TypeError('url must be a string')

    result = parse_url(url)
    if not result.hostname:
        return sha1(url)
    host_checksum = get_crc32(result.hostname)
    doc_uri_combined = result.path + ';' + result.params \
        + result.query + result.fragment

    doc_uri_combined = to_bytes(doc_uri_combined, 'utf8', 'ignore')
    doc_fprint = hashlib.md5(doc_uri_combined).digest()
    fprint = hexlify(pack(">i16s", host_checksum, doc_fprint))
    return fprint

def request_fingerprint(url, date=None, date_format='%Y-%m-%d'):
    if isinstance(date, datetime.datetime):
        date = date.strftime(date_format)
    elif not isinstance(date, six.string_types):
        date = ""

    fp = hashlib.sha1()
    fp.update(to_bytes(url, 'utf8'))
    fp.update(date)
    return fp.hexdigest()
