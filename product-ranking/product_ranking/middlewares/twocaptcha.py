from scrapy import log
from scrapy.exceptions import IgnoreRequest
from scrapy.utils.misc import load_object


class TwoCaptchaMiddleware(object):

    CAPTCHA_SOLVING_SUCCESS = 'captcha/success'
    CAPTCHA_SOLVING_FAILURE = 'captcha/failure'

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def __init__(self, crawler):
        self.crawler = crawler
        self.stats = crawler.stats
        self.settings = crawler.settings
        self.queue = []
        self.is_paused = False
        self.solver = load_object(self.settings.get('CAPTCHA_SOLVER'))
        self.api_key = self.settings.get('TWOCAPTCHA_APIKEY')
        self.retry_limit = 5

    def get_initial_url(self, request):
        if hasattr(request, 'meta') and request.meta.get('redirect_urls'):
            initial_url = request.meta['redirect_urls'][0]
        else:
            initial_url = request.url
        return initial_url

    def process_request(self, request, spider):
        if request.meta.get('captcha_request', False):
            return

        if self.is_paused:
            self.queue.append((request, spider))
            raise IgnoreRequest(
                'Crawling paused, because CAPTCHA is being solved'
            )

    def process_response(self, request, response, spider):
        if spider.is_captcha_page(response):
            if request.meta.get('captcha_retry_attempt') and request.meta.get('captcha_request'):
                spider.log('Probably captcha was solved incorrectly')
                self.stats.inc_value(self.CAPTCHA_SOLVING_FAILURE)
        else:
            if request.meta.get('captcha_retry_attempt') and request.meta.get('captcha_request'):
                spider.log('Probably captcha was solved correctly')
                self.stats.inc_value(self.CAPTCHA_SOLVING_SUCCESS)

        if request.meta.get('captcha_request', False):
            return response

        if self.is_paused:
            self.queue.append(
                (request, spider)
            )
            raise IgnoreRequest(
                'Crawling paused, because CAPTCHA is being solved'
            )

        if spider.is_captcha_page(response) and request.meta.get('captcha_retry_attempt', 0) < self.retry_limit:
            self.pause_crawling()
            response.request = request
            self.queue.append((request, spider))
            response.meta['captcha_request'] = True
            response.meta['initial_url'] = self.get_initial_url(response.request)
            response.meta['captcha_retry_attempt'] = response.meta.get('captcha_retry_attempt', 0) + 1
            return self.solver(spider, self).input_captcha(response, spider)
        return response

    def captcha_handled(self, _):
        log.msg('CAPTCHA handled, resuming crawling')
        self.resume_crawling()

    def pause_crawling(self):
        self.is_paused = True

    def resume_crawling(self):
        # import pprint
        self.is_paused = False
        for request, spider in self.queue:
            # pprint.pprint(self.queue)
            # pprint.pprint(request.headers)
            request.dont_filter = True
            request.meta['captcha_request'] = False
            self.crawler.engine.crawl(request.replace(url=self.get_initial_url(request)), spider)
        self.queue[:] = []
