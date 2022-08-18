from __future__ import with_statement
import os
from contextlib import contextmanager

from fabric.api import cd, run, env, prefix, sudo, put
import cuisine


env.user = 'ubuntu'
env.hosts = ['52.4.67.56']
env.host_string = env.hosts[0]
VENV_DIR = 'virtual_env'
VENV_PATH = '/home/%s/%s/' % (env.user, VENV_DIR)
CACHE_ROOT_DIR = '/home/%s/cache' % env.user
CACHE_LOGS_DIR = '/tmp/cache_logs/'


@contextmanager
def virtualenv():
    venv_activate = 'source %s%sbin%sactivate' % (VENV_PATH, os.sep, os.sep)
    with cuisine.cd(VENV_PATH):
        with prefix(venv_activate):
            yield

def setup_packages():
    sudo('apt-get update --fix-missing')
    sudo('apt-get install -y python-pip')
    sudo('pip install virtualenv')

def create_virtualenv():
    if not cuisine.dir_exists(VENV_PATH):
        run('virtualenv -p python2.7 ' + VENV_PATH)

    with virtualenv():
        run('pip install boto')
        run('pip install Flask')
        run('pip install uwsgi')

def copy_cache_scripts():
    if not cuisine.dir_exists(CACHE_ROOT_DIR):
        run('mkdir %s' % CACHE_ROOT_DIR)
    sub_folders = ['cache_layer', 'cache_web_interface']
    main_dir = os.path.dirname(os.getcwd())
    for folder in sub_folders:
        local_path = os.path.join(main_dir, folder)
        put(local_path, CACHE_ROOT_DIR)
    if not cuisine.dir_exists(CACHE_LOGS_DIR):
        run('mkdir %s' % CACHE_LOGS_DIR)

def setup_cron():
    required_scriptnames = [
        'cache_starter.py',
        'simmetrica_class.py',
        'send_cache_mail_report.py',
    ]

def restart_services():
    sudo('service nginx restart')
    sudo('service uwsgi restart')

def deploy():
    setup_packages()
    create_virtualenv()
    copy_cache_scripts()
    setup_cron()
    restart_services()

if __name__ == '__main__':
    deploy()