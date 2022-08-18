from scrapy import signals
from scrapy.exceptions import NotConfigured

# Log 503 responses
class SpiderLog503(object):

    def __init__(self):
        # file where to save logs for responses handled
        self.log_file = open("handler503_log.txt", "w+")

    @classmethod
    def from_crawler(cls, crawler):
        # first check if the extension should be enabled and raise
        # NotConfigured otherwise
        if not crawler.settings.getbool('HANDLE503_ENABLED'):
            raise NotConfigured

        # instantiate the extension object
        ext = cls()

        # connect the extension object to signals
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.response_downloaded, signal=signals.response_downloaded)

        # return the extension object
        return ext

    def spider_opened(self, spider):
        spider.log("opened spider %s" % spider.name)

    def response_downloaded(self, response, request, spider):
        if response.status == 503:
            self.log_file.write(response.body)