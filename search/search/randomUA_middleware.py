from search.settings import USER_AGENT_LIST
import random
from scrapy import log
from scrapy.exceptions import NotConfigured
 
class RandomUserAgentMiddleware(object):

    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool('ROTATE_UA'):
            raise NotConfigured

        midd = cls()
        return midd
 
    def process_request(self, request, spider):
        ua  = random.choice(USER_AGENT_LIST)
        if ua:
            request.headers.setdefault('User-Agent', ua)
        # log.msg('>>>> UA %s'%request.headers)