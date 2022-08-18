import json
import time

from scrapy import Request
from scrapy.log import ERROR


class RecaptchaSolver(object):

    def __init__(self, spider, captcha_middleware):
        self.spider = spider
        self.api_key = captcha_middleware.api_key
        self.input_url = 'http://2captcha.com/in.php'
        self.output_url = 'http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}'
        self.delay = 5
        self.max_retries = 30
        self.captcha_middleware = captcha_middleware

    def input_captcha(self, response, spider):
        sitekey = spider.get_captcha_key(response)
        response.meta.update(
            {
                'captcha_request': True,
                'captcha_response': response,
                'initial_request': response.request,
            }
        )

        return Request(
            self.input_url,
            method='POST',
            callback=self.check_response,
            body=json.dumps(
                {
                    "key": self.api_key,
                    "method": "userrecaptcha",
                    "googlekey": sitekey,
                    "pageurl": response.meta['initial_url']
                }),
            meta=response.meta,
            dont_filter=True
        )


    def check_response(self, response):
        status = response.body_as_unicode().split('|')[0]

        if status == 'OK':
            captcha_server_id = response.body_as_unicode().split('|')[-1]
            time.sleep(self.delay)
            return Request(
                self.output_url.format(
                    api_key=self.api_key,
                    captcha_id=captcha_server_id
                ),
                callback=self._get_solved_captcha_response,
                meta=response.meta,
                dont_filter=True
            )
        else:
            self.spider.log("Failed to upload captcha to solve")

    def _get_solved_captcha_response(self, response):
        status = response.body_as_unicode().split('|')[0]

        if status == 'OK':
            captcha = response.body_as_unicode().split('|')[-1]
            meta = response.meta.copy()
            response = response.meta.get('captcha_response')
            response.meta.update(meta)

            return self.spider.get_captcha_form(
                response,
                solution=captcha,
                referer=response.meta['initial_url'],
                callback=self.captcha_middleware.captcha_handled
            ).replace(
                dont_filter=True
            )
        elif status == 'ERROR_CAPTCHA_UNSOLVABLE':
            response = response.meta.get('captcha_response')
            response.meta['captcha_retries'] = 0

            return Request(
                response.url,
                dont_filter=True,
                callback=response.request.callback,
                meta=response.meta
            )
        else:
            self.spider.log('Server response: {}'.format(response.body_as_unicode()))
            if response.meta.get('captcha_retries', 0) == self.max_retries:
                self.spider.log('max retries for captcha reached for {}'.format(response.url), ERROR)
                if response.meta.get('captcha_response'):
                    return response.meta['captcha_response'].request

            response.meta['captcha_retries'] = response.meta.get('captcha_retries', 0) + 1

            time.sleep(self.delay)
            return response.request
