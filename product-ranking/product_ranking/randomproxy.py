# Copyright (C) 2013 by Aivars Kalvans <aivars.kalvans@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os
import re
import random
import base64


class Mode:
    RANDOMIZE_PROXY_EVERY_REQUESTS, RANDOMIZE_PROXY_ONCE, SET_CUSTOM_PROXY = range(3)


class RandomProxy(object):
    def __init__(self, settings):
        self.mode = settings.get('PROXY_MODE')
        self.proxy_list = settings.get('PROXY_LIST')
        if not os.path.exists(self.proxy_list):
            self._create_http_proxies_list(self.proxy_list)
        self.chosen_proxy = ''
        if self.proxy_list is None:
            raise KeyError('PROXY_LIST setting is missing')

        if self.mode == Mode.RANDOMIZE_PROXY_EVERY_REQUESTS or self.mode == Mode.RANDOMIZE_PROXY_ONCE:
            fin = open(self.proxy_list)
            self.proxies = {}
            for line in fin.readlines():
                parts = re.match('(\w+://)(\w+:\w+@)?(.+)', line.strip())
                if not parts:
                    continue

                # Cut trailing @
                if parts.group(2):
                    user_pass = parts.group(2)[:-1]
                else:
                    user_pass = ''

                self.proxies[parts.group(1) + parts.group(3)] = user_pass
            fin.close()
            if self.mode == Mode.RANDOMIZE_PROXY_ONCE:
                self.chosen_proxy = random.choice(list(self.proxies.keys()))
        elif self.mode == Mode.SET_CUSTOM_PROXY:
            custom_proxy = settings.get('CUSTOM_PROXY')
            self.proxies = {}
            parts = re.match('(\w+://)(\w+:\w+@)?(.+)', custom_proxy.strip())
            if not parts:
                raise ValueError('CUSTOM_PROXY is not well formatted')

            if parts.group(2):
                user_pass = parts.group(2)[:-1]
            else:
                user_pass = ''

            self.proxies[parts.group(1) + parts.group(3)] = user_pass
            self.chosen_proxy = parts.group(1) + parts.group(3)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def process_request(self, request, spider):
        if not getattr(spider, 'use_proxies', None):
            # spider.log('use_proxies is OFF for this spider - not using proxy...')
            return
        
        # Don't overwrite with a random one (server-side state for IP)
        if 'proxy' in request.meta:
            if request.meta["exception"] is False:
                return
        request.meta["exception"] = False
        if len(self.proxies) == 0:
            raise ValueError('All proxies are unusable, cannot proceed')

        if self.mode == Mode.RANDOMIZE_PROXY_EVERY_REQUESTS:
            proxy_address = random.choice(list(self.proxies.keys()))
        else:
            proxy_address = self.chosen_proxy

        proxy_user_pass = self.proxies[proxy_address]

        if proxy_user_pass:
            request.meta['proxy'] = proxy_address
            basic_auth = 'Basic ' + base64.b64encode(proxy_user_pass.encode()).decode()
            request.headers['Proxy-Authorization'] = basic_auth
        else:
            spider.log('Proxy user pass not found')
        spider.log('Using proxy <%s>, %d proxies left' % (
                proxy_address, len(self.proxies)))

    def process_exception(self, request, exception, spider):
        if not getattr(spider, 'use_proxies', None):
            # spider.log('use_proxies is OFF for this spider - not using proxy...')
            return

        if 'proxy' not in request.meta:
            return
        if self.mode == Mode.RANDOMIZE_PROXY_EVERY_REQUESTS or self.mode == Mode.RANDOMIZE_PROXY_ONCE:
            proxy = request.meta['proxy']
            try:
                del self.proxies[proxy]
            except KeyError:
                pass
            request.meta["exception"] = True
            if self.mode == Mode.RANDOMIZE_PROXY_ONCE:
                self.chosen_proxy = random.choice(list(self.proxies.keys()))
            spider.log('Removing failed proxy <%s>, %d proxies left' % (
                proxy, len(self.proxies)))

    # PROXY LIST SECTION
    @staticmethod
    def _create_http_proxies_list(fpath, host='tprox.contentanalyticsinc.com'):
        BASE_HTTP_PORT = 22100
        NUM_PROXIES = 300
        fh = open(fpath, 'w')
        for i in xrange(NUM_PROXIES):
            proxy = 'http://%s:%s' % (host, str(BASE_HTTP_PORT + i))
            fh.write(proxy + '\n')
        fh.close()
