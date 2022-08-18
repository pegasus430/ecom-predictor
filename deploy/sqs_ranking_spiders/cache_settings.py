import os

CACHE_HOST = 'http://sqs-metrics.contentanalyticsinc.com/'
CACHE_URL_GET = 'get_cache'  # url to retrieve task cache from
CACHE_URL_SAVE = 'save_cache'  # to save cached result to
CACHE_URL_STATS = 'complete_task'  # to have some stats about completed tasks
CACHE_URL_FAIL = 'fail_task'  # to manage broken tasks
CACHE_AUTH = ('admin', os.getenv('CACHE_AUTH_PASSWORD', 'gLfb-N4gd<'))
CACHE_TIMEOUT = 15  # 15 seconds request timeout
# key in task data to not retrieve cached result
# if True, task will be executed even if there is result for it in cache
CACHE_GET_IGNORE_KEY = 'sqs_cache_get_ignore'
# key in task data to not save cached result
# if True, result will not be saved to cache
CACHE_SAVE_IGNORE_KEY = 'sqs_cache_save_ignore'
