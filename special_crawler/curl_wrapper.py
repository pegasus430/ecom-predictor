#!/usr/bin/python
#  -*- coding: utf-8 -*-

# Author: Marek Glica
# This is Curl wrapper to support unicode string.
# Curl spits out the cyrillic characters in UTF.
# And this wrapper prints the scraper output in original language for testing purpose.
# curl argument is given as an argument.
# for ex: python curl_wrapper.py 'localhost/get_data?url=http://www.ozon.ru/context/detail/id/28659614/'"
# (Before, we used $ curl "localhost/get_data?url=http://ww.ozon.ru/context/detail/id/28659614/")
# This print unicode string - "Электроника" from "\u042d\u043b\u0435\u043a\u0442\u0440\u043e\u043d\u0438\u043a\u0430"
# pip install pycurl==7.19.5

import sys
import pycurl
import urllib
import re

from StringIO import StringIO


def curl_wrapper(url):
    """
    :param url: URL string to curl
    :return: result string
    """
    storage = StringIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.WRITEFUNCTION, storage.write)
    c.perform()
    c.close()
    content = storage.getvalue()
    content_decoded = content.decode('unicode_escape')
    return content_decoded


if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1] # 'localhost/get_data?url=http://www.ozon.ru/context/detail/id/28659614/'
        url_front = re.findall(r'^(localhost\/get_data\?url=)(.*)', url)[0][0]
        url_end = re.findall(r'^(localhost\/get_data\?url=)(.*)', url)[0][1]
        url = url_front + urllib.quote(url_end)
        print curl_wrapper(url)
    else:
        print "######################################################################################################"
        print "This is Curl wrapper to support unicode string.(Author: Marek Glica)"
        print "Please input correct argument.\nfor ex: python curl_wrapper.py 'localhost/get_data?url=http://www.ozon.ru/context/detail/id/28659614/'"
        print '(Before, we used $ curl "localhost/get_data?url=http://ww.ozon.ru/context/detail/id/28659614/")'
        print "######################################################################################################"
