"""
Django settings for image_duplication_check project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.7/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'z%qnqx%)je!0*g4$b)n0uc)7xx_13c2d1ew-mhd19l71-rz5ku'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_dumpdb',
    'walmart_developer_accounts',
    'nutrition_info_images',
    'statistics',
    'walmart_api',
    'mocked_walmart_api',
    'fcgi',
    'ckeditor',
    'ckeditor_uploader',
)

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAdminUser',),
    'PAGE_SIZE': 10,
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    )
}

MIDDLEWARE_CLASSES = (
    'rest_apis_content_analytics.middleware.DisableCSRF',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'rest_apis_content_analytics.auth_middleware.AuthMiddleware'
)

ROOT_URLCONF = 'rest_apis_content_analytics.urls'

WSGI_APPLICATION = 'rest_apis_content_analytics.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.7/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/
STATIC_ROOT = '/home/ubuntu/tmtext/rest_apis_content_analytics/rest_apis_content_analytics/static'
STATIC_URL = '/static/'

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'


TEMPLATE_LOADERS = ['django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader']
TEMPLATE_DIRS = [os.path.join(BASE_DIR, 'templates')]

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.template.context_processors.debug',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',

    'statistics.context_processors.stats_walmart_xml_items',
    'walmart_api.context_processors.get_submission_history_as_json',
)


LOGIN_REDIRECT_URL = '/items_update_with_xml_file_by_walmart_api/'


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        # Include the default Django email handler for errors
        # This is what you'd get without configuring logging at all.
        'mail_admins': {
            'class': 'django.utils.log.AdminEmailHandler',
            'level': 'ERROR',
            # But the emails are plain text by default - HTML is nicer
            'include_html': True,
        },
        # Log to a text file that can be rotated by logrotate
        'logfile': {
            'class': 'logging.handlers.WatchedFileHandler',
            'filename': os.path.join(BASE_DIR, 'django.errors'),
            'filters': []
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        # Again, default Django configuration to email unhandled exceptions
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        # Might as well log any errors anywhere else in Django
        'django': {
            'handlers': ['logfile'],
            'level': 'ERROR',
            'propagate': False,
        },
        'default': {
            'handlers': ['logfile'],
            'level': 'WARNING',  # Or maybe INFO or DEBUG
            'propagate': False
        }
    },
}


CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.path.join(BASE_DIR, '_fs_cache'),
    }
}

SUBMISSION_HISTORY_CACHE_KEY = 'get_submission_history_as_json'
STATISTICS_CACHE_KEY = 'get_statistics_as_json'


if DEBUG and os.path.exists('/tmp/_django_log_sql'):
    LOGGING['loggers']['django.db.backends'] = {
        'level': 'DEBUG',
        'handlers': ['console'],
    }

FORCE_SCRIPT_NAME = "/"


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'DIRS': TEMPLATE_DIRS,
        'OPTIONS': {
            'context_processors': TEMPLATE_CONTEXT_PROCESSORS
        }
    },
]


TEST_TWEAKS = {
    'item_upload_ajax_ignore': '/tmp/_walmart_api_do_not_test_ajax_on_item_upload'
}


# CKEditor
CKEDITOR_ALLOW_NONIMAGE_FILES = False
CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_IMAGE_BACKEND = "pillow"


IS_PRODUCTION = os.path.exists(
    os.path.dirname(__file__) + "/is_walmart_api_production_server")

if IS_PRODUCTION:
    MEDIA_URL = 'http://restapis-itemsetup.contentanalyticsinc.com:8080/media/'

# print "Server production mode? %s" % IS_PRODUCTION

try:
    from local_settings import *
except ImportError:
    pass
