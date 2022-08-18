from collections import Mapping, OrderedDict

from scrapy.http.request import Request as ScrapyRequest
from twisted.web.http_headers import Headers as TwistedHeaders
from w3lib.http import headers_dict_to_raw


class CaselessOrderedDict(OrderedDict):

    __slots__ = ()

    def __init__(self, seq=None):
        super(CaselessOrderedDict, self).__init__()
        if seq:
            self.update(seq)

    def __getitem__(self, key):
        return OrderedDict.__getitem__(self, self.normkey(key))

    def __setitem__(self, key, value):
        OrderedDict.__setitem__(self, self.normkey(key), self.normvalue(value))

    def __delitem__(self, key):
        OrderedDict.__delitem__(self, self.normkey(key))

    def __contains__(self, key):
        return OrderedDict.__contains__(self, self.normkey(key))
    has_key = __contains__

    def __copy__(self):
        return self.__class__(self)
    copy = __copy__

    def normkey(self, key):
        """Method to normalize dictionary key access"""
        return key.lower()

    def normvalue(self, value):
        """Method to normalize values prior to be setted"""
        return value

    def get(self, key, def_val=None):
        return OrderedDict.get(self, self.normkey(key), self.normvalue(def_val))

    def setdefault(self, key, def_val=None):
        return OrderedDict.setdefault(self, self.normkey(key), self.normvalue(def_val))

    def update(self, seq):
        seq = seq.items() if isinstance(seq, Mapping) else seq
        iseq = ((self.normkey(k), self.normvalue(v)) for k, v in seq)
        super(CaselessOrderedDict, self).update(iseq)

    @classmethod
    def fromkeys(cls, keys, value=None):
        return cls((k, value) for k in keys)

    def pop(self, key, *args):
        return OrderedDict.pop(self, self.normkey(key), *args)


class Headers(CaselessOrderedDict):
    """Case insensitive and ordered http headers"""

    def __init__(self, seq=None, encoding='utf-8'):
        self.encoding = encoding
        super(Headers, self).__init__(seq)

    def normkey(self, key):
        """Headers must not be unicode"""
        if isinstance(key, unicode):
            return key.title().encode(self.encoding)
        return key.title()

    def normvalue(self, value):
        """Headers must not be unicode"""
        if value is None:
            value = []
        elif not hasattr(value, '__iter__'):
            value = [value]
        return [x.encode(self.encoding) if isinstance(x, unicode) else x \
            for x in value]

    def __getitem__(self, key):
        try:
            return super(Headers, self).__getitem__(key)[-1]
        except IndexError:
            return None

    def get(self, key, def_val=None):
        try:
            return super(Headers, self).get(key, def_val)[-1]
        except IndexError:
            return None

    def getlist(self, key, def_val=None):
        try:
            return super(Headers, self).__getitem__(key)
        except KeyError:
            if def_val is not None:
                return self.normvalue(def_val)
            return []

    def setlist(self, key, list_):
        self[key] = list_

    def setlistdefault(self, key, default_list=()):
        return self.setdefault(key, default_list)

    def appendlist(self, key, value):
        lst = self.getlist(key)
        lst.extend(self.normvalue(value))
        self[key] = lst

    def items(self):
        return list(self.iteritems())

    def iteritems(self):
        return ((k, self.getlist(k)) for k in self.keys())

    def values(self):
        return [self[k] for k in self.keys()]

    def to_string(self):
        return headers_dict_to_raw(self)

    def __copy__(self):
        return self.__class__(self)
    copy = __copy__


def monkey_patch_scrapy_request():
    def __init__(self, url, callback=None, method='GET', headers=None, body=None,
                 cookies=None, meta=None, encoding='utf-8', priority=0,
                 dont_filter=False, errback=None):

        self._encoding = encoding  # this one has to be set first
        self.method = str(method).upper()
        self._set_url(url)
        self._set_body(body)
        assert isinstance(priority, int), "Request priority not an integer: %r" % priority
        self.priority = priority

        assert callback or not errback, "Cannot use errback without a callback"
        self.callback = callback
        self.errback = errback

        self.cookies = cookies or {}
        self.headers = Headers(headers or {}, encoding=encoding)
        self.dont_filter = dont_filter

        self._meta = dict(meta) if meta else None

    ScrapyRequest.__init__ = __init__


def monkey_patch_twisted_headers():
    def __init__(self, rawHeaders=None):
        self._rawHeaders = OrderedDict()
        if rawHeaders is not None:
            for name, values in rawHeaders.items():
                self.setRawHeaders(name, values)

    TwistedHeaders.__init__ = __init__
