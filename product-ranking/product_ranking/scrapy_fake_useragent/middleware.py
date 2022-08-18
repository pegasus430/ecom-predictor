import logging

logger = logging.getLogger(__name__)

import random

CONFIG = {
    'product': 'Mozilla',
    'version': ['4.0', '5.0'],
    'comment': [
        [None, 'compatible'],
        [None, 'Windows', 'Linux', 'Ubuntu', 'Macintosh'],
        [None] + ['MSIE %s.0' % v for v in range(6, 11)],
        [None, 'AcooBrowser', 'AOL 9.5', 'Trident/5.0'],
        [None, 'en-US', 'zh-CN', 'es-ES'],
    ],
    'subproducts': [
        {
            'product': 'AppleWebKit',
            'version': {
                'format': '%s.%s',
                'ranges': [
                    (500, 540),
                    (0, 50),
                ],
            },
            'comment': [
                [None, 'KHTML, like Gecko'],
            ],
        },
        {
            'product': 'Gecko',
            'version': {
                'format': '%d%02d%02d',
                'ranges': [
                    (2010, 2014),
                    (0, 12),
                    (0, 12),
                ],
            },
        },
        {
            'product': 'Firefox',
            'version': {
                'format': '%d.0',
                'ranges': [
                    (10, 50),
                ],
            },
        },
        {
            'product': 'Chrome',
            'version': {
                'format': '%d.%d.%d.%d',
                'ranges': [
                    (10, 40),
                    (0, 100),
                    (0, 10000),
                    (0, 1000),
                ],
            },
        },
        {
            'product': 'Chromium',
            'version': {
                'format': '%d.%d.%d.%d',
                'ranges': [
                    (10, 40),
                    (0, 100),
                    (0, 10000),
                    (0, 1000),
                ],
            },
        },
        {
            'product': 'Safari',
            'version': {
                'format': '%d.%d',
                'ranges': [
                    (500, 600),
                    (0, 100),
                ],
            },
        },
        {
            'product': 'Version',
            'version': {
                'format': '%d.%d',
                'ranges': [
                    (0, 10),
                    (0, 10),
                ],
            }
        },
        {
            'product': 'Build',
            'version': {
                'format': '%dD%d',
                'ranges': [
                    (1, 100),
                    (0, 1000),
                ],
            },
        },
    ],
}


def _get_value(values):
    if isinstance(values, list):
        return random.choice(values)
    return values


def _get_version(version):
    if isinstance(version, list):
        return random.choice(version)
    if isinstance(version, dict):
        fmt = version['format']
        args = []
        for a, b in version['ranges']:
            args.append(random.randint(a, b))
        return fmt % tuple(args)
    return version


def _get_product(cfg):
    product = _get_value(cfg['product'])
    version = _get_version(cfg['version'])
    comments = filter(None, [
        random.choice(value) for value in cfg.get('comment', [])
    ])
    subproducts = cfg.get('subproducts', [])
    extra = []
    if subproducts:
        nr_extra = random.randint(0, len(subproducts) - 1)
        extra = [
            _get_product(c) for c in random.sample(subproducts, nr_extra)
        ]
    parts = filter(None, [
        '%s/%s' % (product, version),
        '(%s)' % '; '.join(comments) if comments else None,
        ' '.join(extra),
    ])
    return ' '.join(parts)


def get_random_ua():
    return _get_product(CONFIG)


class RandomUserAgent(object):
    """A downloader middleware to generate a random user agent for each request and repeat
    based on a mapping from a header value to a user agent.

    According to the RFC2616, the user agent contains multiple product tokens
    and comments as well as any subproducts.

    Settings:
    ---------

    RANDOM_USER_AGENT - Set a specific user agent

    Algorithm used depends on availability, tried in the following order:
    - fake_useragent.UserAgent.random (from https://github.com/hellysmile/fake-useragent)
    - get_random_ua() (defined above, default if none of third parties algorithms are found)
    """
    session_header = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def __init__(self, crawler):
        self.user_agent = crawler.settings.get('RANDOM_USER_AGENT')
        self.get_random_user_agent = None
        try:
            from fake_useragent import UserAgent
        except:
            pass
        else:
            ua = UserAgent()
            self.get_random_user_agent = lambda : ua.random
            logger.debug('Using fake_useragent User Agent generator')
        if self.get_random_user_agent is None:
            self.get_random_user_agent = get_random_ua
            logger.info('Using default User Agent generator')


    def process_request(self, request, spider):
        self.set_user_agent(request, spider)

    def set_user_agent(self, request, spider):
        uagent = self.user_agent or self.get_random_user_agent()
        request.headers['User-Agent'] = uagent
        logger.info('UA set to: {}'.format(uagent))
