from __future__ import absolute_import

import six
import cachetools


class HBaseTTLCache(cachetools.TTLCache):
    """Soft TTLCache for HBase

    It will keep an internal data structure for fast access and manage
    interactions with HBase for cache purposes. Doesn't delete anything
    from HBase, in fact it will keep even expired records on it.

    Example:
        >>> table = get_talbe_magic() # poof
        >>> ttl = 10
        >>> cache = HBaseTTLCache(table, ttl)
        >>> cache[0] = 0
        >>> sleep(ttl)
        >>> cache[0]
        ... KeyError('Key 0 doesn't exist.')
        >>> cache.close()

    Attributes:
        table (happybase.Table): table object passed on `__init__`
        ttl (int): ttl passed on `__init__`
        maxsize (int): maxsize passed on `__init__`
    """
    def __init__(self, table, ttl, maxsize=1000):
        """Initializes HBaseTTLCache.

        Arguments:
            table (happybase.Table): table to use as cache.
            maxsize (int): maximum size in rows stored inside the
                internal data structure.
            ttl (int): maximum time expressed in seconds.

        Raises:
            TypeError: `ttl` and `maxsize` must be int.
        """
        if not isinstance(ttl, int):
            raise TypeError('`ttl` must be an int.')

        if not isinstance(maxsize, int):
            raise TypeError('`maxsize` must be an int.')

        super(HBaseTTLCache, self).__init__(ttl=ttl, maxsize=maxsize)
        self.table = table
        self.__keep_expire = set()

    def _Cache__missing(self, key):
        """Item is missing locally.

        Pull from HBase if exists and updates internal data structure.
        __setitem__ is called by `cachetools` to populate internal
        data structure.

        Arguments:
            key (str): reference on HBase.

        Returns:
            dict: data stored on HBase (happybase.row output)

        Raises:
            KeyError: Key {key} doesn't exist.
        """
        with self._TTLCache__timer as time:
            row = self.table.row(key, include_timestamp=True)
        if not row:
            raise KeyError('Key {} doesn\'t exists'.format(key))
        timestamp = max(x[1] for x in row.values()) / 1000
        if (time - timestamp) > self.ttl:
            raise KeyError('Key {} doesn\'t exists'.format(key))
        value = {k: v[0] for k, v in six.iteritems(row)}
        self.__keep_expire.add(key)
        self._TTLCache__links[key] = link = cachetools.ttl._Link(key)
        link.expire = timestamp + self.ttl
        link.next = root = self._TTLCache__root
        link.prev = prev = root.prev
        prev.next = root.prev = link
        return value

    def __setitem__(self, key, value):
        """Keeps expire

        Raises:
            ValueError: Value is too large (handled by cachetools).
        """
        expire = None
        if key in self.__keep_expire:
            expire = self._TTLCache__links[key].expire
        super(HBaseTTLCache, self).__setitem__(key, value)
        if expire is not None:
            self._TTLCache__links[key].expire = expire

    def popitem(self):
        """Removes an item locally.

        Removes the item locally, but saves it to HBase.

        Returns:
            tuple: of the form (<key>, <value>)

        Raises:
            KeyError: `HBaseTTLCache` is empty.
        """
        key, value = super(HBaseTTLCache, self).popitem()
        self._store_item(key, value)
        return key, value

    def _store_item(self, key, value):
        """Writes directly to HBase.

        Arguments:
            key (str): reference on HBase.
            value (dict): data stored on HBase.

        Returns:
            bool: True in case the operation is succesful.

        Raises:
            IOError: (happybase) An IOError exception signals that an
                error occurred communicating to the Hbase master or an
                Hbase region server. Also used to return more general
                Hbase error conditions.
            IllegalArgument: (happybase) An IllegalArgument exception
                indicates an illegal or invalid argument was passed
                into a procedure.
        """
        timestamp = None
        if key in self._TTLCache__links:
            timestamp = int((self._TTLCache__links[key].expire -
                             self.ttl) * 1000)
        self.table.put(key, value, timestamp=timestamp)
        return True

    def flush(self):
        """Updates HBase.

        Sends everything from the internal data structure to HBase.

        Returns:
            bool: True in case the operation is succesful.

        Raises:
            IOError: (happybase) An IOError exception signals that an
                error occurred communicating to the Hbase master or an
                Hbase region server. Also used to return more general
                Hbase error conditions.
            IllegalArgument: (happybase) An IllegalArgument exception
                indicates an illegal or invalid argument was passed
                into a procedure.
        """
        for key, value in six.iteritems(self._Cache__data):
            self._store_item(key, value)
        return True

    def close(self, flush=True):
        """Close the HBase connection.

        Arguements:
            flush (bool): indicates if it should call
                `HBaseLRUCache.flush` before closing the connection.

        Returns:
            bool: True in case the operation is succesful.

        Raises:
            IOError: (happybase) An IOError exception signals that an
                error occurred communicating to the Hbase master or an
                Hbase region server. Also used to return more general
                Hbase error conditions.
            IllegalArgument: (happybase) An IllegalArgument exception
                indicates an illegal or invalid argument was passed
                into a procedure.
        """
        if flush:
            self.flush()
        return True
