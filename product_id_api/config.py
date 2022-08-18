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

# Define the database
SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:password@localhost/product_id_api?sslmode=disable'
SQLALCHEMY_TRACK_MODIFICATIONS = False

if os.getenv('DEV_CONFIG'):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///{}?timeout=20'.format(os.path.join(BASE_DIR, 'app.db'))

# Application threads.
THREADS_PER_PAGE = 2

# Enable protection agains *Cross-site Request Forgery (CSRF)
CSRF_ENABLED = True

# Use a secure, unique and absolutely secret key for
# signing the data.
CSRF_SESSION_KEY = "5nleo28cp1dyzm3klrunbeuyd87d2agdlp5t8ce3"

# Secret key for signing cookies
SECRET_KEY = CSRF_SESSION_KEY

# Collect argument errors
BUNDLE_ERRORS = True

# Disable 404 help
ERROR_404_HELP = False

BUILDERS_PACKAGE = 'app.builders'
