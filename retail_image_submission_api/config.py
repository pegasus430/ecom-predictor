import logging
import os
import sys

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
SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:password@localhost/retail_image_submission_api?sslmode=disable'
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
CSRF_SESSION_KEY = "49dkh4qpnfl46cj3108hbd7irfp4j3nqp9vyu5m3"

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
CELERY_TIMEDELTA_SECONDS = 10

CLOUDINARY_CLOUD_NAME = 'sheryl-test'
CLOUDINARY_API_KEY = '474545898925692'
CLOUDINARY_API_SECRET = 'tMTZfHJxlj80eLYbwQLdSd2SmM0'

DOWNLOADERS_PACKAGE = 'app.downloaders'
API_KEY_HEADER = 'X-API-KEY'
FEED_ID_HEADER = 'X-FEED-ID'

PAGINATION = 15
