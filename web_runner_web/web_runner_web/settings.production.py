try:
    from web_runner_web.shared_settings import *
except ImportError as e:
    pass

# WEB_RUNNER_WEB settings
WEB_RUNNER_LOG_FILES = (
    '/home/web_runner/virtual-environments/web-runner/pyramid.log',
    '/home/web_runner/virtual-environments/web-runner/access.log',
)
