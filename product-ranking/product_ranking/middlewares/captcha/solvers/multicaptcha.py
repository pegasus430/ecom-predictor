import json
from recaptcha import RecaptchaSolver


class MultiCaptchaSolver(RecaptchaSolver):

    def __init__(self, spider, captcha_middleware):
        super(MultiCaptchaSolver, self).__init__(spider, captcha_middleware)
        self.is_recaptcha = True

    def input_captcha(self, response, spider):
        request = super(MultiCaptchaSolver, self).input_captcha(response, spider)

        # determine if captcha is recaptcha or funcaptcha
        self.is_recaptcha = spider.is_recaptcha(response)
        if not self.is_recaptcha:
            sitekey = spider.get_captcha_key(response)
            body = {
                "key": self.api_key,
                "method": "funcaptcha",
                "publickey": sitekey,
                "pageurl": response.url
            }

            solve_url = spider.get_captcha_formaction(response)
            request.meta.update(
                {
                    'solve_url': solve_url
                }
            )
            request = request.replace(body=json.dumps(body), meta=request.meta)
        return request

    def _get_solved_captcha_response(self, response):
        status = response.body_as_unicode().split('|')[0]

        if status == 'OK' and not self.is_recaptcha:
            meta = response.meta.copy()

            captcha = response.body_as_unicode().replace('OK|', '')

            return self.spider.get_funcaptcha_form(
                meta.get('solve_url'),
                solution=captcha,
                callback=self.captcha_middleware.captcha_handled
            ).replace(
                dont_filter=True,
                meta=meta
            )
        else:
            return super(MultiCaptchaSolver, self)._get_solved_captcha_response(response)
