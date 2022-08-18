from __future__ import absolute_import

import aerospike
import cachetools
import six


class AerospikeTTLCache(cachetools.TTLCache):
    """Soft TTLCache for Aerospike

    It will keep an internal data structure for fast access and manage
    interactions with Aerospike for cache purposes. Doesn't delete anything
    from Aerospike, in fact it will keep even expired records on it.

    Example:
        >>> client = get_client_magic() # poof
        >>> namespace, set_, ttl = 'test', 'test', 10
        >>> cache = AerospikeTTLCache(client, namespace, set_, ttl)
        >>> cache[0] = 0
        >>> sleep(ttl)
        >>> cache[0]
        ... KeyError('Key 0 doesn't exist.')
        >>> cache.close()

    Attributes:
        client (aerospike.Client): client object passed on `__init__`
        namespace (str): namespace passed on `__init__`
        set (str): set passsed on `__init__`
        ttl (int): ttl passed on `__init__`
        maxsize (int): maxsize passed on `__init__`
    """
    def __init__(self, client, namespace, set_, ttl, maxsize=1000):
        """Initializes AerospikeTTLCache.

        Arguments:
            client (aerospike.Client): client to use on cache.
            namespace (str): namespace to use on cache.
            set (str): set to use as cache.
            ttl (int): maximum time expressed in seconds.
            maxsize (int): maximum size in rows stored inside the
                internal data structure.

        Raises:
            TypeError: `ttl` and `maxsize` must be int.
        """
        if not isinstance(ttl, int):
            raise TypeError('`ttl` must be an int.')

        if not isinstance(maxsize, int):
            raise TypeError('`maxsize` must be an int.')

        super(AerospikeTTLCache, self).__init__(ttl=ttl, maxsize=maxsize)
        self.client = client
        self.namespace = namespace
        self.set = set_
        self.__key = (namespace, set_)
        self.__keep_expire = set()

    def _Cache__missing(self, key):
        """Item is missing locally.

        Pull from Aerospike if exists and updates internal data structure.
        __setitem__ is called by `cachetools` to populate internal
        data structure.

        Arguments:
            key (str): reference on Aerospike.

        Returns:
            dict: data stored on Aerospike.

        Raises:
            KeyError: Key {key} doesn't exist.
        """
        with self._TTLCache__timer as time:
            try:
                __key = self.__key + (key, )
                _, _, bins = self.client.get(__key)
            except aerospike.exception.RecordNotFound:
                raise KeyError('Key {} doesn\'t exists'.format(key))
        timestamp = bins.pop('__timestamp')
        if (time - timestamp) > self.ttl:
            raise KeyError('Key {} doesn\'t exists'.format(key))
        self.__keep_expire.add(key)
        self._TTLCache__links[key] = link = cachetools.ttl._Link(key)
        link.expire = timestamp + self.ttl
        link.next = root = self._TTLCache__root
        link.prev = prev = root.prev
        prev.next = root.prev = link
        return bins

    def __setitem__(self, key, value):
        """Keeps expire

        Raises:
            ValueError: Value is too large (handled by cachetools).
        """
        expire = None
        if key in self.__keep_expire:
            expire = self._TTLCache__links[key].expire
        super(AerospikeTTLCache, self).__setitem__(key, value)
        if expire is not None:
            self._TTLCache__links[key].expire = expire

    def popitem(self):
        """Removes an item locally.

        Removes the item locally, but saves it to Aerospike.

        Returns:
            tuple: of the form (<key>, <value>)

        Raises:
            KeyError: `Aerospike` is empty.
        """
        key, value = super(AerospikeTTLCache, self).popitem()
        self._store_item(key, value)
        return key, value

    def _store_item(self, key, value):
        """Writes directly to Aerospike.

        Arguments:
            key (str): reference on Aerospike.
            value (dict): data stored on Aerospike.

        Returns:
            bool: True in case the operation is succesful.
        """
        value = dict(value)
        with self._TTLCache__timer as time:
            timestamp = None
            if key in self._TTLCache__links:
                timestamp = self._TTLCache__links[key].expire - self.ttl
            __key = self.__key + (key, )
            value['__timestamp'] = timestamp or time
            self.client.put(__key, value)
        return True

    def flush(self):
        """Updates Aerospike.

        Sends everything from the internal data structure to Aerospike.

        Returns:
            bool: True in case the operation is succesful.
        """
        for key, value in six.iteritems(self._Cache__data):
            self._store_item(key, value)
        return True

    def close(self, flush=True):
        """Close the Aerospike connection.

        Arguements:
            flush (bool): indicates if it should call
                `AerospikeTTLCache.flush` before closing the connection.

        Returns:
            bool: True in case the operation is succesful.
        """
        if flush:
            self.flush()
        return True
