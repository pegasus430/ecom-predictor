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

SITEMAP_RESOURCES_DIR = '/var/tmp/sitemaps/'

# Define the database
SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:password@localhost/sitemap_service?sslmode=disable'
SQLALCHEMY_TRACK_MODIFICATIONS = False

if os.getenv('DEV_CONFIG'):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///{}?timeout=20'.format(os.path.join(BASE_DIR, 'app.db'))
    SITEMAP_RESOURCES_DIR = '/tmp/sitemaps/'

# Application threads.
THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)
CSRF_ENABLED = True

# Use a secure, unique and absolutely secret key for
# signing the data.
CSRF_SESSION_KEY = "38g10vpamf74wkf456s9gkew7opg5hbvn5z73agf"

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

SPIDERS_PACKAGE = 'app.spiders'

PAGINATION = 15
