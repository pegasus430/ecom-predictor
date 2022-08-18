import argparse
from urlparse import urlparse

from twisted.internet import reactor
from scrapy.crawler import Crawler
from scrapy import log, signals
from scrapy.utils.project import get_project_settings
from scrapy.contrib.spiders.sitemap import SitemapSpider, iterloc
from scrapy.http import Request
from scrapy.utils.sitemap import Sitemap, sitemap_urls_from_robots
from scrapy.item import Item, Field


def get_args():
    """
    Parse command line arguments

    :return: command line arguments
    """

    parser = argparse.ArgumentParser(description='Scrape urls from sitemap to CSV file')

    parser.add_argument('sitemap_or_robots_url',
                        help='Url for sitemap or robots.txt')

    parser.add_argument('-o', '--output',
                        help='CSV file to save urls')

    return parser.parse_args()


class SitemapToCsvItem(Item):
    url = Field()


class SitemapToCsvSpider(SitemapSpider):

    def __init__(self, url, *args, **kwargs):
        self.sitemap_urls = [url]

        url_parts = urlparse(url)
        self.name = url_parts.netloc

        super(SitemapToCsvSpider, self).__init__(*args, **kwargs)

    def _parse_sitemap(self, response):
        if response.url.endswith('/robots.txt'):
            for url in sitemap_urls_from_robots(response.body):
                yield Request(url, callback=self._parse_sitemap)
        else:
            body = self._get_sitemap_body(response)
            if body is None:
                log.msg(format="Ignoring invalid sitemap: %(response)s",
                        level=log.WARNING, spider=self, response=response)
                return

            s = Sitemap(body)
            if s.type == 'sitemapindex':
                for loc in iterloc(s, self.sitemap_alternate_links):
                    if any(x.search(loc) for x in self._follow):
                        yield Request(loc, callback=self._parse_sitemap)
            elif s.type == 'urlset':
                for loc in iterloc(s):
                    for r, c in self._cbs:
                        if r.search(loc):
                            yield SitemapToCsvItem(url=loc)
                            break


def run_sitemap_spider(sitemap_or_robots_url, output=None):
    spider = SitemapToCsvSpider(url=sitemap_or_robots_url)

    if not output:
        output = '{}.csv'.format(spider.name)

    settings = get_project_settings()
    settings.overrides['FEED_URI'] = output
    settings.overrides['FEED_FORMAT'] = 'csv'
    crawler = Crawler(settings)
    crawler.signals.connect(reactor.stop, signal=signals.spider_closed)
    crawler.configure()
    crawler.crawl(spider)
    crawler.start()
    log.start()
    reactor.run()

if __name__ == '__main__':

    args = get_args()

    run_sitemap_spider(args.sitemap_or_robots_url, args.output)
