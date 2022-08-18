import json
import random
import string
from urllib import urlopen
import urlparse
from urlparse import urljoin

import boto
import re
import six
from boto.s3.key import Key
from scrapy import log, signals, Request, FormRequest
from scrapy.conf import settings
from scrapy.contrib.downloadermiddleware.redirect import (MetaRefreshMiddleware,
                                                          RedirectMiddleware)
from scrapy.contrib.downloadermiddleware.retry import RetryMiddleware
from scrapy.core.downloader.handlers.http11 import TunnelError
from scrapy.exceptions import IgnoreRequest
from scrapy.exceptions import NotConfigured
from scrapy.http import HtmlResponse
from scrapy.log import ERROR
from scrapy.utils.response import get_meta_refresh, response_status_message
from twisted.internet import defer, reactor

from incapsula_headers import (monkey_patch_scrapy_request,
                               monkey_patch_twisted_headers)
from utils import ProxyConfig


class VerizonMetaRefreshMiddleware(MetaRefreshMiddleware):
    def process_response(self, request, response, spider):
        request.meta['dont_filter'] = True
        if 'dont_redirect' in request.meta or request.method == 'HEAD' or \
                not isinstance(response, HtmlResponse) or request.meta.get('redirect_times') >= 1:
            request.meta['dont_redirect'] = True
            return response

        if isinstance(response, HtmlResponse):
            interval, url = get_meta_refresh(response)
            if url and interval < self._maxdelay:
                redirected = self._redirect_request_using_get(request, url)
                redirected.dont_filter = True
                return self._redirect(redirected, request, spider, 'meta refresh')

        return response


class VerizonRedirectMiddleware(RedirectMiddleware):
    def process_response(self, request, response, spider):
        if (request.meta.get('dont_redirect', False) or
                    response.status in getattr(spider, 'handle_httpstatus_list', []) or
                    response.status in request.meta.get('handle_httpstatus_list', []) or
                request.meta.get('handle_httpstatus_all', False)):
            return response

        allowed_status = (301, 302, 303, 307)
        if 'Location' not in response.headers or response.status not in allowed_status:
            return response

        # HTTP header is ascii or latin1, redirected url will be percent-encoded utf-8
        location = response.headers['location'].decode('latin1')
        search_final_location = re.search('actualUrl=(.*)', location)

        if search_final_location:
            redirected_url = urljoin(request.url, search_final_location.group(1))
        else:
            redirected_url = urljoin(request.url, location)

        if response.status in (301, 307) or request.method == 'HEAD':
            redirected = request.replace(url=redirected_url)
            return self._redirect(redirected, request, spider, response.status)

        redirected = self._redirect_request_using_get(request, redirected_url)
        return self._redirect(redirected, request, spider, response.status)


class AmazonProxyMiddleware(RetryMiddleware):
    def process_response(self, request, response, spider):
        if 'dont_retry' in request.meta:
            return response
        if response.status == 503:
            if request.meta.get('retry_times', 0) >= 14:
                proxy = ProxyConfig(getattr(spider, 'name')).get_proxy()
                request.meta['proxy'] = proxy
                request.headers['Connection'] = 'close'
                # request.headers.pop('Cookie', None)
            request.headers.pop('Referer', None)
            reason = response_status_message(response.status)
            # print "AmazonProxyMiddleware retrying {} --- {}".format(request.url, reason)
            return self._retry(request, reason, spider) or response
        return response


class WalmartRetryMiddleware(RedirectMiddleware):
    def process_response(self, request, response, spider):
        if response.status in [301, 302, 307]:
            location = response.headers.get('Location')
            request.meta['retry_count'] = request.meta.get('retry_count', 0)
            if not re.search('^https?://((www|photos3)\.)?walmart\.com/', location) and \
                            request.meta.get('retry_count') < 5:
                request.meta['retry_count'] += 1
                log.msg('WalmartRetryMiddleware: {}, times: {}, location: {}'.format(
                    request.url, request.meta['retry_count'], location))
                request.dont_filter = True
                return request
            else:
                log.msg('Redirect to {}'.format(location))
                request = request.replace(url=location)
                return request
        return response


class ProxyFromConfig(object):
    def __init__(self, use_proxies, settings):
        self.haproxy_endpoint = None
        self.amazon_bucket_name = "sc-settings"
        self.production_bucket_config_filename = "global_proxy_config.cfg"
        self.master_bucket_config_filename = "master_proxy_config.cfg"

    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool('USE_PROXIES') and not crawler.settings.get('USE_PROXIES'):
            raise NotConfigured
        use_proxies = crawler.settings.getbool('USE_PROXIES')
        obj = cls(use_proxies, crawler.settings)
        crawler.signals.connect(obj.spider_opened, signal=signals.spider_opened)
        return obj

    def spider_opened(self, spider):
        try:
            with open("/tmp/branch_info.txt", "r") as gittempfile:
                all_lines = gittempfile.readlines()
                branch_name = all_lines[0].strip()
        except Exception:
            # TODO Add logging to middlewares/extensions
            # defaults to production config
            branch_name = "sc_production"
        # check for flag put there by scrapy_daemon
        if branch_name == "sc_production":
            config_filename = self.production_bucket_config_filename
        else:
            config_filename = self.master_bucket_config_filename
        full_config = self.get_proxy_config_file(self.amazon_bucket_name, config_filename)
        setattr(spider, "proxy_config_filename", str(config_filename))
        spider_name = getattr(spider, 'name')
        if full_config and spider_name:
            site = spider_name.replace("_shelf_urls_products", "").replace("_products", "")
            if site in full_config:
                spider_config = full_config.get(site, {})
            else:
                spider_config = full_config.get("default", {})
            setattr(spider, "proxy_config", str(spider_config))
            if spider_config:
                chosen_proxy = self._weighted_choice(spider_config)
                if chosen_proxy and ":" in chosen_proxy:
                    middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
                    middlewares['product_ranking.scrapy_fake_useragent.middleware.RandomUserAgent'] = 400
                    middlewares['scrapy.contrib.downloadermiddleware.useragent.UserAgentMiddleware'] = None
                    middlewares['product_ranking.randomproxy.RandomProxy'] = None
                    settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares
                    self.haproxy_endpoint = "http://" + chosen_proxy
                    setattr(spider, "proxy_service", chosen_proxy)

        if not self.haproxy_endpoint:
            raise NotConfigured

    def _insert_proxy_into_request(self, request):
        request.meta['proxy'] = self.haproxy_endpoint

    def process_request(self, request, spider):
        if self.haproxy_endpoint:
            # Don't overwrite existing
            if 'proxy' in request.meta:
                return
            if not "crawlera" in self.haproxy_endpoint:
                self._insert_proxy_into_request(request)

    def process_exception(self, request, exception, spider):
        log.msg('Error {} getting url {} using {} proxy'.format(exception, request.url, self.haproxy_endpoint))

    def _weighted_choice(self, choices_dict):
        choices = [(key, value) for (key, value) in choices_dict.items()]
        # Accept dict, converts to list
        # of iterables in following format
        # [("choice1", 0.6), ("choice2", 0.2), ("choice3", 0.3)]
        # Returns chosen variant
        total = sum(w for c, w in choices)
        r = random.uniform(0, total)
        upto = 0
        for c, w in choices:
            if upto + w >= r:
                return c
            upto += w

    @staticmethod
    def get_proxy_config_file(amazon_bucket_name, bucket_config_filename):
        proxy_config = None
        try:
            S3_CONN = boto.connect_s3(is_secure=False)
            S3_BUCKET = S3_CONN.get_bucket(amazon_bucket_name, validate=False)
            k = Key(S3_BUCKET)
            k.key = bucket_config_filename
            value = k.get_contents_as_string()
            value = value.replace("\n", "").replace(" ", "").replace(",}", "}")
            proxy_config = json.loads(value)
        except Exception as e:
            print(e)
        else:
            print('Retrieved proxy config from bucket: {}'.format(value))
        return proxy_config


class IncapsulaRequestMiddleware(object):
    def __init__(self):
        monkey_patch_twisted_headers()
        monkey_patch_scrapy_request()

    def process_request(self, request, spider):
        # TODO: replace spider with request
        spider.headers['Host'] = urlparse.urlparse(request.url).netloc
        for k, v in spider.headers.items():
            request.headers.setdefault(k, v)


class HayneedleCaptchaBypassMiddleware(MetaRefreshMiddleware):
    def process_response(self, request, response, spider):
        if 'dont_redirect' in request.meta or request.method == 'HEAD' or \
                not isinstance(response, HtmlResponse):
            return response

        if isinstance(response, HtmlResponse):
            interval, url = get_meta_refresh(response)
            if url and interval < self._maxdelay:
                request.headers['Connection'] = 'close'
                request = request.replace(dont_filter=True)
                redirected = self._redirect_request_using_get(request, request.url)
                return self._redirect(redirected, request, spider, 'meta refresh, redirect to captcha page')

        return response


class IncapsulaRetryMiddleware(object):
    def process_response(self, request, response, spider):
        if not response.headers.get('X-CDN'):
            incapsula_retry = request.meta.get('incapsula_retry', 0) + 1
            if incapsula_retry < 5:
                request.meta['incapsula_retry'] = incapsula_retry
                return request.replace(dont_filter=True)
        return response


class TunnelRetryMiddleware(RetryMiddleware):
    def process_exception(self, request, exception, spider):
        if (isinstance(exception, self.EXCEPTIONS_TO_RETRY) or isinstance(exception, TunnelError)) \
                and 'dont_retry' not in request.meta:
            # TODO: remove two lines below
            if hasattr(spider, 'headers'):
                spider.headers['Connection'] = 'close'
            else:
                request.headers['Connection'] = 'close'
            return self._retry(request, exception, spider)


class WalmartNoJsonRetryMiddleware(RetryMiddleware):
    def process_response(self, request, response, spider):
        request.meta['nojson_retry'] = request.meta.get('nojson_retry', 0)
        if request.meta['nojson_retry'] < 15:
            invalid_page = "to view the page content" in response.body
            if invalid_page and request.url.startswith('https://www.walmart.com/search/'):
                reason = "No json on page"
                request.headers.pop('Referer', '')
                request.headers.setdefault("Connection", "close")
                request.headers.pop('Cookie', None)
                request.meta['nojson_retry'] += 1
                return self._retry(request, reason, spider) or response
        return response


class ReCaptchaV1Middleware(object):
    max_retries = 10
    spider = None
    captchas_retries = {}

    @staticmethod
    def is_captcha(response):
        try:
            return bool(response.xpath('//div/h1[text()="Pardon Our Interruption..."]'))
        except AttributeError:
            return False

    @staticmethod
    def _get_captcha_address(response):
        return response.xpath('//iframe/@src').extract()[0]

    @staticmethod
    def _get_remote_ip(response):
        return response.xpath('//input[@name="remoteip"]/@value').extract()[0]

    def process_response(self, request, response, spider):
        if not self.spider:
            self.spider = spider
        try:
            solved_request = response.meta.get('solved_request', False)
        except:
            solved_request = False
        if self.is_captcha(response) and not solved_request:
            if not hasattr(response, 'meta'):
                response = response.replace(request=request)
            response.meta.update({'captcha_response': response,
                                  'initial_callback': request.callback,
                                  'cookiejar': random.randint(1, 1000)})
            return Request(self._get_captcha_address(response), callback=self._get_captcha_image,
                           meta=response.meta, dont_filter=True)
        return response

    def _get_captcha_image(self, response):
        captcha_id = response.xpath("//input[@id='recaptcha_challenge_field']/@value").extract()
        if not captcha_id:
            self.spider.log('can not extract the captcha id')
            return
        captcha_id = captcha_id[0]

        captcha_image_link = urlparse.urljoin(response.url, 'image?c={}'.format(captcha_id))

        self.spider.log('Downloading captcha file...')

        captcha = urlopen(captcha_image_link).read()
        captcha_file = MultipartFile('captcha.jpg', captcha)

        data = {'file': captcha_file,
                'key': self.spider.TWOCAPTCHA_APIKEY}

        response.meta.update({'captcha_id': captcha_id})

        return MultipartFormRequest('http://2captcha.com/in.php', formdata=data, callback=self.check_response,
                                    meta=response.meta, dont_filter=True)

    def check_response(self, response):
        status = response.body_as_unicode().split('|')[0]

        if status == 'OK':
            captcha_server_id = response.body_as_unicode().split('|')[-1]

            solved_captcha_url = "{server}?key={api_key}&action=get&id={captcha_id}".format(
                server="http://2captcha.com/res.php",
                api_key=self.spider.TWOCAPTCHA_APIKEY,
                captcha_id=captcha_server_id)

            check_captcha_request = Request(solved_captcha_url,
                                            callback=self._get_solved_captcha_response,
                                            meta=response.meta,
                                            dont_filter=True)

            deferred = defer.Deferred()
            reactor.callLater(10, deferred.callback, check_captcha_request)
            return deferred

        else:
            self.spider.log("Failed to upload captcha image to solve")

    def _get_solved_captcha_response(self, response):
        status = response.body_as_unicode().split('|')[0]

        if  status == 'OK':
            self.spider.log('Server response: {}'.format(response.body))

            captcha = response.body_as_unicode().split('|')[-1]

            self.spider.log(u"Captcha solved: {}".format(captcha))

            response.meta.update({'solved_request': True})
            meta = response.meta.copy()
            response = response.meta.get('captcha_response')
            response.meta.update({'cookiejar': meta['cookiejar']})

            return FormRequest.from_response(response,
                                             formdata=
                                             {
                                                 "remoteip": self._get_remote_ip(response),
                                                 "recaptcha_challenge_field": meta.get('captcha_id'),
                                                 "recaptcha_response_field": captcha
                                             },
                                             dont_filter=True,
                                             meta=response.meta,
                                             callback=meta.get('initial_callback'))
        elif status == 'ERROR_CAPTCHA_UNSOLVABLE':
            response = response.meta.get('captcha_response')
            response.meta['captcha_retries'] = 0

            return Request(response.url, dont_filter=True, callback=response.request.callback, meta=response.meta)
        else:
            self.spider.log('Server response: {}'.format(response.body_as_unicode()))
            if response.meta.get('captcha_retries', 0) == self.max_retries:
                self.spider.log('max retries for captcha reached for {}'.format(response.url), ERROR)

                return response.meta.get('captcha_response')
            response.meta['captcha_retries'] = response.meta.get('captcha_retries', 0) + 1
            get_solved_captcha_request = Request(response.url, callback=self._get_solved_captcha_response,
                                                 meta=response.meta, dont_filter=True)

            deferred = defer.Deferred()
            reactor.callLater(10, deferred.callback, get_solved_captcha_request)
            return deferred


# https://github.com/scrapy/scrapy/pull/1954
class MultipartFormRequest(FormRequest):
    def __init__(self, *args, **kwargs):
        formdata = kwargs.pop('formdata', None)

        kwargs.setdefault('method', 'POST')

        super(MultipartFormRequest, self).__init__(*args, **kwargs)

        content_type = self.headers.setdefault(b'Content-Type', [b'multipart/form-data'])[0]
        method = kwargs.get('method').upper()
        if formdata and method == 'POST' and content_type == b'multipart/form-data':
            items = formdata.items() if isinstance(formdata, dict) else formdata
            self._boundary = ''

            # encode the data using multipart spec
            self._boundary = to_bytes(''.join(
                random.choice(string.digits + string.ascii_letters) for i in range(20)), self.encoding)
            self.headers[b'Content-Type'] = b'multipart/form-data; boundary=' + self._boundary
            request_data = _multpart_encode(items, self._boundary, self.encoding)
            self._set_body(request_data)


class MultipartFile(object):
    def __init__(self, name, content, mimetype='application/octet-stream'):
        self.name = name
        self.content = content
        self.mimetype = mimetype


def _multpart_encode(items, boundary, enc):
    body = []

    for name, value in items:
        body.append(b'--' + boundary)
        if isinstance(value, MultipartFile):
            file_name = value.name
            content = value.content
            content_type = value.mimetype

            body.append(
                b'Content-Disposition: form-data; name="' + to_bytes(name, enc) + b'"; filename="' + to_bytes(file_name,
                                                                                                              enc) + b'"')
            body.append(b'Content-Type: ' + to_bytes(content_type, enc))
            body.append(b'')
            body.append(to_bytes(content, enc))
        else:
            body.append(b'Content-Disposition: form-data; name="' + to_bytes(name, enc) + b'"')
            body.append(b'')
            body.append(to_bytes(value, enc))

    body.append(b'--' + boundary + b'--')
    return b'\r\n'.join(body)


def to_bytes(text, encoding=None, errors='strict'):
    """Return the binary representation of `text`. If `text`
    is already a bytes object, return it as-is."""
    if isinstance(text, bytes):
        return text
    if not isinstance(text, six.string_types):
        raise TypeError('to_bytes must receive a unicode, str or bytes '
                        'object, got %s' % type(text).__name__)
    if encoding is None:
        encoding = 'utf-8'
    return text.encode(encoding, errors)
