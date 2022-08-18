import json

from recaptcha import RecaptchaSolver

from scrapy import Request


class FunCaptchaSolver(RecaptchaSolver):

    def __init__(self, spider, captcha_middleware):
        super(FunCaptchaSolver, self).__init__(spider, captcha_middleware)
        self.output_url = 'http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}'
        self.delay = 20

    def input_captcha(self, response, spider):
        sitekey = spider.get_captcha_key(response)
        solve_url = spider.get_captcha_formaction(response)
        response.meta.update(
            {
                'captcha_request': True,
                'captcha_response': response,
                'solve_url': solve_url
            }
        )

        return Request(
            self.input_url,
            method='POST',
            callback=self.check_response,
            body=json.dumps(
                {
                    "key": self.api_key,
                    "method": "funcaptcha",
                    "publickey": sitekey,
                    "pageurl": response.url
                }),
            meta=response.meta,
            dont_filter=True
        )

    def _get_solved_captcha_response(self, response):
        status = response.body_as_unicode().split('|')[0]

        if status == 'OK':
            captcha = response.body_as_unicode().replace('OK|', '')
            meta = response.meta.copy()

            return self.spider.get_captcha_form(
                meta.get('solve_url'),
                solution=captcha,
                callback=self.captcha_middleware.captcha_handled
            ).replace(
                dont_filter=True,
                meta=meta
            )
        else:
            return super(FunCaptchaSolver, self)._get_solved_captcha_response(response)
