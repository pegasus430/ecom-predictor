import logging

import os

# Define logging level
LOG_LEVEL = logging.INFO

# Statement for enabling the development environment
DEBUG = True

RESOURCES_DIR = '/var/tmp/reviews/'

# Define the database
DATABASE_URI = 'mongodb://localhost'
DATABASE_NAME = 'review_api'

SERVER_URL = '//review-api.contentanalyticsinc.com'

DEV_CONFIG = os.getenv('DEV_CONFIG')

if DEV_CONFIG:
    LOG_LEVEL = logging.DEBUG
    DATABASE_NAME = 'review_api_dev'
    RESOURCES_DIR = '/tmp/reviews/'
    SERVER_URL = '//review-api.contentanalyticsinc.com:8080'

# Application threads.
THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)
CSRF_ENABLED = True

# Use a secure, unique and absolutely secret key for
# signing the data.
CSRF_SESSION_KEY = 'fh482pa84x63kgoryx52m1opzd83bapl478dj430'

# Secret key for signing cookies
SECRET_KEY = CSRF_SESSION_KEY

# Collect argument errors
BUNDLE_ERRORS = True

# Disable 404 help
ERROR_404_HELP = False

# Celery
CELERY_BROKER_URL = '{}/{}'.format(DATABASE_URI, DATABASE_NAME)
CELERY_RESULT_BACKEND = DATABASE_URI
CELERY_MONGODB_BACKEND_SETTINGS = {
    'database': DATABASE_NAME
}
# Run crawler every N seconds
CELERY_PROCESS_TIMEDELTA_SECONDS = 10

SPIDERS_PACKAGE = 'app.spiders'
API_KEY_HEADER = 'X-API-KEY'

PAGINATION = 15
