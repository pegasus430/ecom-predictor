import json
import time
import requests
import logging

# initialize the logger
logger = logging.getLogger('basic_logger')
logger.setLevel(logging.DEBUG)
fh = logging.StreamHandler()
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

class LogHistory(object):
    def __init__(self, scraper):
        self.start = None
        if scraper == "scrapy_daemon":
            self.data = {"source": scraper}
        else:
            self.data = {
                'git_branch': None,
                'build': None,
                'scraper': scraper,
                'scraper_type': None,
                'server_hostname': None,
                'pl_name': None,
                'url': None,
                'response_time': None,
                'date': None,
                'duration': None,
                'page_size': None,
                'instance': None,
                'max_response_time': None,
                'min_response_time': None,
                'proxy_service': None,
                'status_code': None,
                'failure_cause': 'none',
                'errors': []
            }

    def start_log(self):
        self.start = time.time()

    def get_log(self):
        return json.dumps(self.data)

    def add_log(self, key, value):
        self.data[key] = value

    def increase_counter_log(self, key, start_value=0, increase_value=1):
        if not self.data.get(key):
            self.data[key] = start_value
        self.data[key] += increase_value

    def add_list_log(self, key, value):
        if key not in self.data:
            self.data[key] = []
        self.data[key].append(value)

    def send_log(self):
        end = time.time()

        self.data['duration'] = round(end-self.start, 2)
        self.data['date'] = time.time()
        if self.data.get('scraper') == "CH":
            try:
                self.data['instance'] = requests.get('http://169.254.169.254/latest/meta-data/instance-id',
                    timeout=5).content
            except Exception as e:
                self.data['instance'] = 'Failed to get instance metadata: %s %s' % (type(e), e)

            try:
                requests.post('http://logstash-ch-crawler.contentanalyticsinc.com:5044',
                    auth=('chlogstash', 'shijtarkecBekekdetloaxod'),
                    headers={'Content-type': 'application/json'},
                    data=self.get_log(),
                    timeout=5)
            except Exception as e:
                logger.warn('Failed to send logs: %s %s' % (type(e), e))
        elif self.data.get('scraper') == "SC":
            # import pprint
            # pprint.pprint(self.data)
            try:
                r = requests.post(
                    url='http://logstash-sc-crawler.contentanalyticsinc.com:5044',
                    auth=('sclogstash', 'shijtarkecBekekdetloaxod'),
                    headers={'Content-type': 'application/json'},
                    data=self.get_log(),
                    timeout=10)
                logger.info('Logstash response: {}'.format(r.text))
            except Exception as e:
                logger.warn('Failed to send logs: %s %s' % (type(e), e))
        elif not self.data.get("scraper") and self.data.get("source") == "scrapy_daemon":
            try:
                r = requests.post(
                    url='http://logstash-general.contentanalyticsinc.com:5044',
                    auth=('generallogstash', 'shijtarkecBekekdetloaxod'),
                    headers={'Content-type': 'application/json'},
                    data=self.get_log(),
                    timeout=10)
                logger.info('Logstash response: {}'.format(r.text))
            except Exception as e:
                logger.warn('Failed to send logs: %s %s' % (type(e), e))
