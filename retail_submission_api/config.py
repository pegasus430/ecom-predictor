import os
import sys
import logging

# Define logging level
LOG_LEVEL = logging.DEBUG

# Statement for enabling the development environment
DEBUG = True

# Define the application directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

SUBMISSION_RESOURCES_DIR = '/var/tmp/submissions/'

# Define the database
SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:password@localhost/retail_submission_api?sslmode=disable'
SQLALCHEMY_TRACK_MODIFICATIONS = False

if os.getenv('DEV_CONFIG'):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///{}?timeout=20'.format(os.path.join(BASE_DIR, 'app.db'))
    SUBMISSION_RESOURCES_DIR = '/tmp/submissions/'

# Application threads.
THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)
CSRF_ENABLED = True

# Use a secure, unique and absolutely secret key for
# signing the data.
CSRF_SESSION_KEY = "6ae78550690238d4bdbfcdb123a77aa52c7fd91a"

# Secret key for signing cookies
SECRET_KEY = CSRF_SESSION_KEY

# Collect argument errors
BUNDLE_ERRORS = True

# Disable 404 help
ERROR_404_HELP = False

# Celery
CELERY_BROKER_URL = 'sqla+{}'.format(SQLALCHEMY_DATABASE_URI)
CELERY_RESULT_BACKEND = 'db+{}'.format(SQLALCHEMY_DATABASE_URI)
# Run crawler every N seconds
CELERY_PROCESS_TIMEDELTA_SECONDS = 10
CELERY_CHECK_TIMEDELTA_SECONDS = 300

SPIDERS_PACKAGE = 'app.spiders'
API_KEY_HEADER = 'X-API-KEY'
FEED_ID_HEADER = 'X-FEED-ID'

PAGINATION = 15
