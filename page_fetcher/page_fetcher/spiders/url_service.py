import json
import time
import urlparse

from scrapy.log import DEBUG, INFO, ERROR
from scrapy.spider import Spider
from scrapy.http import (Request, FormRequest)
from scrapy.selector import Selector
from scrapy.contrib.spidermiddleware.httperror import HttpError

from captcha_solver import CaptchaBreakerWrapper

from page_fetcher.items import PageItem, RequestErrorItem


class FailedToSolveCaptcha(Exception):

    def __init__(self, captcha_img_url, *args, **kwargs):
        super(FailedToSolveCaptcha, self).__init__(*args, **kwargs)

        self.message = "Failed to solve captcha " + captcha_img_url
        self.url = captcha_img_url


class UrlServiceSpider(Spider):

    name = "url_service"
    allowed_domains = []
    start_urls = []

    def __init__(self, limit='100', service_url=None,
                 captcha_retries='10', *args, **kwargs):
        super(UrlServiceSpider, self).__init__(*args, **kwargs)

        if service_url is None:
            raise AssertionError("Service URL is not optional.")

        self.limit = limit
        self.captcha_retries = int(captcha_retries)
        self.service_url = service_url

        self._cbw = CaptchaBreakerWrapper()

        queue_url = urlparse.urljoin(
            self.service_url, 'get_queued_urls/?limit=%d&block=%d') \
            % (int(limit), 0)
        self.log("Fetching URLs with '%s'." % queue_url, level=DEBUG)
        self.start_urls.append(queue_url)

    def parse(self, response):
        for crawl_data in json.loads(response.body):
            self.log("From URL Service: %s" % crawl_data, DEBUG)
            url = crawl_data['url']

            req = Request(url, callback=self.parse_target,
                          errback=self.parse_target_err)
            req.meta['crawl_data'] = crawl_data
            req.meta['start_time'] = time.clock()
            yield req

    def parse_target(self, response):
        if not self._has_captcha(response.body):
            result = self._parse_target(response)
        elif response.meta.get('captch_solve_try', 0) >= self.captcha_retries:
            # We already tried to solve the captcha, give up.

            result = RequestErrorItem(
                base_url=self.service_url,
                id=response.meta['crawl_data']['id'],
                http_code=response.status,
                error_string="Failed to solve captcha.")
        else:
            result = self._handle_captcha(response)
        return result

    def _parse_target(self, response):
        crawl_data = response.meta['crawl_data']

        body = None
        if hasattr(response, 'body_as_unicode'):
            body = response.body_as_unicode().encode('utf-8')
        else:
            body = response.body  # Probably binary or incorrect Content-Type.

        item = PageItem(
            base_url=self.service_url,
            total_time=time.clock() - response.meta['start_time'],
            id=crawl_data['id'],
            url=crawl_data['url'],
            imported_data_id=crawl_data['imported_data_id'],
            category_id=crawl_data['category_id'],
            body=body)
        return item

    def _handle_captcha(self, response):
        crawl_data = response.meta['crawl_data']
        captch_solve_try = response.meta.get('captch_solve_try', 0)

        self.log("Captcha challenge for %s (try %d)."
                 % (crawl_data.get('url'), captch_solve_try),
                 level=INFO)

        forms = Selector(response).xpath('//form')
        assert len(forms) == 1, "More than one form found."
        hidden_value1 = forms[0].xpath(
            '//input[@name="amzn"]/@value').extract()[0]
        hidden_value2 = forms[0].xpath(
            '//input[@name="amzn-r"]/@value').extract()[0]
        captcha_img = forms[0].xpath(
            '//img[contains(@src, "/captcha/")]/@src').extract()[0]

        self.log(
            "Extracted capcha values: (%s) (%s) (%s)"
            % (hidden_value1, hidden_value2, captcha_img),
            level=DEBUG)
        captcha = self._solve_captcha(captcha_img)

        if captcha is None:
            err_msg = "Failed to guess captcha for '%s' (id: %s, try: %d)." % (
                crawl_data.get('url'), crawl_data.get('id'), captch_solve_try)
            self.log(err_msg, level=ERROR)
            result = RequestErrorItem(
                base_url=self.service_url,
                id=crawl_data['id'],
                http_code=response.status,
                error_string=err_msg)
        else:
            self.log("Submitting captcha '%s' for '%s' (try %d)."
                     % (captcha, captcha_img, captch_solve_try),
                     level=INFO)
            result = FormRequest.from_response(
                response,
                formname='',
                formdata={
                    'field-keywords': captcha,
                },
                callback=self.parse_target,
                errback=self.parse_target_err)
            result.meta['captch_solve_try'] = captch_solve_try + 1
            result.meta['crawl_data'] = response.meta['crawl_data']
            result.meta['start_time'] = response.meta['start_time']

        return result

    def parse_target_err(self, failure):
        url_id = failure.request.meta['crawl_data']['id']
        error_string = failure.getErrorMessage()
        if isinstance(failure.value, HttpError):
            status = failure.value.response.status
        else:
            status = 0
            self.log("Unhandled failure type '%s'. Will continue"
                     % type(failure.value), level=ERROR)

        item = RequestErrorItem(
            base_url=self.service_url,
            id=url_id,
            http_code=status,
            error_string=error_string)
        return item

    def _has_captcha(self, body):
        return '.images-amazon.com/captcha/' in body

    def _solve_captcha(self, captcha_url):
        return self._cbw.solve_captcha(captcha_url)
