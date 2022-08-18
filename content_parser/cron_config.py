import json


class CronConfig(object):

    def __init__(self, path='cron_config.json'):
        with open(path) as config_file:
            self._config = json.load(config_file)

    def crons(self):
        return dict((company, config['cron']) for company, config in self._config.iteritems())

    def get(self, company):
        return self._config.get(company)
