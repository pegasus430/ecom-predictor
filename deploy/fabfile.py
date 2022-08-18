#!/usr/bin/env python
from __future__ import with_statement

import os
import re
import random
from contextlib import contextmanager

from fabric.api import cd, env, run, local, sudo, settings, prefix
from fabric.contrib.console import confirm
from fabric.utils import puts
from fabric.colors import red, green
from fabric.contrib import files
import cuisine

'''
Fabric deployment script for Web Runner

This script will help to deploy:
. Scrapyd
. Web Runner REST Server
. Web Runner Web
'''

'''
TODO:
1) deploy users and permissions
2) deploy keys
3) deploy dependencies
4) virtual environment creation
5) download repos on target machine
6) deploy scrapy project
7) deploy web runner project
8) create web-runner-web wheel package
9) deploy web-runner-web
11) Configure supervisord
12) configure nginx
13) work on updates.
'''

# FIXME: For the moment the configuration will be constant defined here.
# Later this info will be added to a configuration file.
#SSH_USER = 'vagrant'
#SSH_PASSWORD = 'vagrant'
#SSH_SERVER = '127.0.0.1'
#SSH_PORT = 2222

WEB_RUNNER_GROUP = 'web_runner'
WEB_RUNNER_USER = 'web_runner'
WEB_RUNNER_PASSWORD = 'web_runner'
WEB_RUNNER_CERT = None

VENV_PREFIX = '~/virtual-environments/'
VENV_SCRAPYD = 'scrapyd'
VENV_WEB_RUNNER = 'web-runner'
VENV_WEB_RUNNER_WEB = 'web-runner-web'

SSH_SUDO_USER = None
SSH_SUDO_PASSWORD = None
SSH_SUDO_CERT = None

REPO_BASE_PATH = '~/repos/'
#REPO_URL = 'https://ContentSolutionsDeploy:Content2020@bitbucket.org/dfeinleib/tmtext.git'
#REPO_URL = 'https://ContentSolutionsDeploy@bitbucket.org/dfeinleib/tmtext.git'
REPO_URL = 'git@bitbucket.org:dfeinleib/tmtext.git'

LOCAL_CERT_BASE_PATH = os.getenv("HOME") + '/tmp/web_runner_ssh_keys'
CERT_REPO_URL = 'git@bitbucket.org:dfeinleib/tmtext.git'
LOCAL_CERT_PATH = LOCAL_CERT_BASE_PATH + os.sep + re.search(
                    '.+\/([^\s]+?)\.git$', CERT_REPO_URL).group(1)


@contextmanager
def virtualenv(environment):
    '''Define the virtual environment to use.

    This function is useful for fabric.api.run commands, because all run
    invocation will be called within the virtual environemnt. Example:

      with virtualenv(VENV_SCRAPYD):
        run('pip install scrapyd')
        run('pip install simplejson')

    The parameter environment is the name of the virtual environment
    followed by VENV_PREFIX
    '''
    venv_path = VENV_PREFIX + os.sep + environment
    venv_activate = 'source %s%sbin%sactivate' % (venv_path, os.sep, os.sep)

    with cuisine.cd(venv_path):
        with prefix(venv_activate):
            yield


def get_ssh_keys():
    '''Get ssh certificates to connect to target servers'''
    puts(green('Getting ssh certificates'))

    local_original_mode = cuisine.is_local()
    cuisine.mode_local()

    if not cuisine.dir_exists(LOCAL_CERT_PATH):
        local('mkdir -p ' + LOCAL_CERT_BASE_PATH)
        local('cd %s && git clone %s && cd %s'
            % (LOCAL_CERT_BASE_PATH, CERT_REPO_URL, LOCAL_CERT_PATH))
    else:
        local('cd %s && git pull' % (LOCAL_CERT_PATH))

    if not local_original_mode:
        cuisine.mode_remote()

def set_environment_vagrant():
    '''Define Vagrant's environment'''
    puts(green('Using Vagrant settings'))
    global SSH_SUDO_USER
    global SSH_SUDO_PASSWORD
    global SSH_SUDO_CERT
    global WEB_RUNNER_CERT

    get_ssh_keys()
#    env.hosts = ['vagrant@127.0.0.1:2222']
    #SSH_SUDO_USER = 'vagrant'
    #SSH_SUDO_PASSWORD = 'vagrant'
    SSH_SUDO_USER = 'vagrant'
    SSH_SUDO_PASSWORD = 'vagrant'
    WEB_RUNNER_CERT = LOCAL_CERT_PATH + os.sep + 'web_runner_rsa'

    env.hosts = ['127.0.0.1']
    env.port = 2222

    env.user = WEB_RUNNER_USER
    env.password = WEB_RUNNER_PASSWORD
    env.key_filename = WEB_RUNNER_CERT


def set_production():
    puts(red('Using production credentials'))

    global SSH_SUDO_USER
    global SSH_SUDO_PASSWORD
    global SSH_SUDO_CERT
    global WEB_RUNNER_CERT

    get_ssh_keys()

    SSH_SUDO_USER = 'ubuntu'
    SSH_SUDO_PASSWORD = None
    SSH_SUDO_CERT = LOCAL_CERT_PATH + os.sep + 'ubuntu_id_rsa'
    WEB_RUNNER_CERT = LOCAL_CERT_PATH + os.sep + 'web_runner_rsa'

    env.user = WEB_RUNNER_USER
    env.password = WEB_RUNNER_PASSWORD
    env.key_filename = WEB_RUNNER_CERT


def setup_users():
    '''Add web runner group and users'''

    puts(green('Creating users and groups'))

    orig_user, orig_passw, orig_cert = env.user, env.password, env.key_filename
    env.user, env.password, env.key_filename = \
        SSH_SUDO_USER , SSH_SUDO_PASSWORD, SSH_SUDO_CERT

    cuisine.group_ensure(WEB_RUNNER_GROUP)
    cuisine.user_ensure(
        WEB_RUNNER_USER,
        gid=WEB_RUNNER_GROUP,
        shell='/bin/bash',
        passwd=WEB_RUNNER_PASSWORD,
        encrypted_passwd=False,
    )

    # Create the ssh certificate for web_runner user
    rem_ssh_deploy_cert_file = '~%s/.ssh/authorized_keys' % WEB_RUNNER_USER
    rem_ssh_priv_cert_file = '~%s/.ssh/id_rsa' % WEB_RUNNER_USER
    rem_ssh_pub_cert_file = '~%s/.ssh/id_rsa.pub' % WEB_RUNNER_USER
    ssh_config_file = '~%s/.ssh/config' % WEB_RUNNER_USER

    if orig_cert and not sudo(
            'test -e %s && echo OK ; true' % (rem_ssh_deploy_cert_file,)
    ).endswith("OK"):
        sudo('mkdir -p ~%s/.ssh' % WEB_RUNNER_USER)
        sudo('chmod 700  ~%s/.ssh' % WEB_RUNNER_USER)

        deploy_cert = open(LOCAL_CERT_PATH + os.sep + 'web_runner_rsa.pub', 'r').read()
        priv_cert = open(LOCAL_CERT_PATH + os.sep + 'web_runner_user_rsa', 'r').read()
        pub_cert = open(LOCAL_CERT_PATH + os.sep + 'web_runner_user_rsa.pub', 'r').read()
        ssh_config = 'Host bitbucket.org\n\tStrictHostKeyChecking no'
        cuisine.file_write('/tmp/deploy_cert', deploy_cert)
        cuisine.file_write('/tmp/priv_cert', priv_cert)
        cuisine.file_write('/tmp/pub_cert', pub_cert)
        cuisine.file_write('/tmp/ssh_config', ssh_config)
        sudo('mv /tmp/deploy_cert ' + rem_ssh_deploy_cert_file)
        sudo('mv /tmp/priv_cert ' + rem_ssh_priv_cert_file)
        sudo('mv /tmp/pub_cert ' + rem_ssh_pub_cert_file)
        sudo('mv /tmp/ssh_config ' + ssh_config_file)
        sudo('chmod 600 %s' % rem_ssh_deploy_cert_file)
        sudo('chmod 600 %s' % rem_ssh_priv_cert_file)
        sudo('chmod 600 %s' % rem_ssh_pub_cert_file)
        sudo(
            'chown -R %s:%s ~%s/.ssh/'
            % (WEB_RUNNER_USER, WEB_RUNNER_GROUP, WEB_RUNNER_USER))

    env.user, env.password, env.key_filename = \
        orig_user, orig_passw, orig_cert


def setup_packages():
    '''Install all packages prerequirements'''
    puts(green('Installing packages'))

    orig_user, orig_passw, orig_cert = env.user, env.password, env.key_filename
    env.user, env.password, env.key_filename = \
        SSH_SUDO_USER, SSH_SUDO_PASSWORD, SSH_SUDO_CERT

    sudo('apt-get update --fix-missing')
    cuisine.package_ensure('python-software-properties')
    # TODO: verify if the repo must be added
    cuisine.package_ensure('tesseract-ocr')
    #cuisine.repository_ensure_apt('ppa:fkrull/deadsnakes')
    cuisine.package_ensure('python3.4 python3.4-dev')
    cuisine.package_ensure('python-dev')
    cuisine.package_ensure('python-pip python3-pip')
    cuisine.package_ensure('libffi-dev')
    cuisine.package_ensure('libxml2-dev libxslt1-dev')
    cuisine.package_ensure('libssl-dev')
    cuisine.package_ensure('git')
    cuisine.package_ensure('tmux')
    cuisine.package_ensure('mc htop iotop nano')  # just for convenience
    cuisine.package_ensure('python-psycopg2 libpq-dev python-dev')
    cuisine.package_ensure('libjpeg-dev')
    cuisine.package_ensure('phantomjs')
    sudo('pip install virtualenv --upgrade')
    sudo('pip install pytesseract')
    sudo('pip install tldextract')

    env.user, env.password, env.key_filename = \
        orig_user, orig_passw, orig_cert


def setup_tmux():
    # Verify if a new tmux session must be created
    try:
        tmux_ls = run('tmux list-windows -t webrunner')

        if not re.search('0: scrapyd', tmux_ls.stdout):
            run('tmux new-window -k -t webrunner:0 -n scrapyd')
        if not re.search('1: web_runner', tmux_ls.stdout):
            run('tmux new-window -k -t webrunner:1 -n web_runner')
        if not re.search('2: web_runner_web', tmux_ls.stdout):
            run('tmux new-window -k -t webrunner:2 -n web_runner_web')
        if not re.search('3: misc', tmux_ls.stdout):
            run('tmux new-window -k -t webrunner:3 -n misc')
    except:
        # The tmux session does not exists. Create everything
        run('tmux new-session -d -s webrunner -n scrapyd')
        run('tmux new-window -k -t webrunner:1 -n web_runner')
        run('tmux new-window -k -t webrunner:2 -n web_runner_web')
        run('tmux new-window -k -t webrunner:3 -n misc')


def _get_venv_path(venv):
    return VENV_PREFIX + os.sep + venv


def _get_repo_path(base_path=REPO_BASE_PATH, url=REPO_URL):
    return base_path + os.sep + re.search(
        '.+\/([^\s]+?)\.git$', url).group(1)


def _setup_virtual_env_scrapyd():
    '''Handle scrapyd virtual environment'''
    venv_scrapyd = _get_venv_path(VENV_SCRAPYD)
    if not cuisine.dir_exists(venv_scrapyd):
        run('virtualenv -p python2.7 ' + venv_scrapyd)

    with virtualenv(VENV_SCRAPYD):
        run('pip install scrapy==0.24.6')
        run('pip install scrapyd==1.0.1')
        run('pip install service_identity')
        run('pip install simplejson')
        run('pip install requests')
        run('pip install Pillow')
        run('pip install pytesseract')
        run('pip install boto')
        run('pip install django')
        run('pip install django-ses')
        run('pip install django_adminplus')
        run('pip install lxml')
        run('pip install pyvirtualdisplay')
        run('pip install tldextract')
        run('pip install s3peat')
        run('pip install workerpool')
        run('pip install boto')
        run('pip install s3peat')
        run('pip install sqlalchemy')
        run('pip install psycopg2')
        run('pip install hjson')
        run('pip install pyyaml')
        run('pip install python-dateutil')
        run('pip install psutil')
        run('pip install mmh3')
        run('pip install flask')
        run('pip install selenium')

    _setup_simmetrica_monitoring()


def _setup_simmetrica_monitoring():
    # TODO: fix the paths, we should not link to the global packages
    orig_user, orig_passw, orig_cert = env.user, env.password, env.key_filename
    env.user, env.password, env.key_filename = \
        SSH_SUDO_USER, SSH_SUDO_PASSWORD, SSH_SUDO_CERT

    sudo('pip install simmetrica')
    env.warn_only = True
    with cd('/home/web_runner/virtual-environments/scrapyd/lib/python2.7'):
        sudo('ln -s /usr/local/lib/python2.7/dist-packages/markupsafe')
        sudo('ln -s /usr/local/lib/python2.7/dist-packages/simmetrica')
        sudo('ln -s /usr/local/lib/python2.7/dist-packages/redis')
        sudo('ln -s /usr/local/lib/python2.7/dist-packages/flask')
        sudo('ln -s /usr/local/lib/python2.7/dist-packages/jinja2')
    env.warn_only = False

    env.user, env.password, env.key_filename = \
        orig_user, orig_passw, orig_cert


def _setup_virtual_env_web_runner():
    venv_webrunner = _get_venv_path(VENV_WEB_RUNNER)
    if not cuisine.dir_exists(venv_webrunner):
        run('virtualenv -p python2.7 ' + venv_webrunner)

    with virtualenv(VENV_WEB_RUNNER):
        run('pip install wheel')
        run('pip install Paste')
        run('pip install flask')
        run('pip install lxml')
        run('pip install pyvirtualdisplay')
        run('pip install s3peat')
        run('pip install workerpool')
        run('pip install boto')
        run('pip install s3peat')
        run('pip install workerpool')
        run('pip install fabric')
        run('pip install cuisine')
        run('pip install scrapy==0.24.6')
        run('pip install scrapyd==1.0.1')
        run('pip install service_identity')
        run('pip install simplejson')
        run('pip install requests')
        run('pip install Pillow')
        run('pip install pytesseract')
        run('pip install boto')
        run('pip install django')
        run('pip install django-ses')
        run('pip install django_adminplus')
        run('pip install lxml')
        run('pip install tldextract')
        run('pip install s3peat')
        run('pip install workerpool')
        run('pip install boto')
        run('pip install s3peat')
        run('pip install sqlalchemy')
        run('pip install psycopg2')
        run('pip install hjson')
        run('pip install pyyaml')
        run('pip install python-dateutil')
        run('pip install psutil')


def _setup_virtual_env_web_runner_web():
    venv_webrunner_web = _get_venv_path(VENV_WEB_RUNNER_WEB)
    if not cuisine.dir_exists(venv_webrunner_web):
        run('virtualenv -p python3.4 ' + venv_webrunner_web)

    with virtualenv(VENV_WEB_RUNNER_WEB):
        run('pip install django')
        run('pip install requests')
        run('pip install lxml')
        run('pip install pyvirtualdisplay')


def setup_virtual_env(scrapyd=True, web_runner=True, web_runner_web=True):
    '''Handle virtual envrironment installation'''
    puts(green('Installing virtual environments'))

    run('mkdir -p ' + VENV_PREFIX)
    if scrapyd:
        _setup_virtual_env_scrapyd()
    if web_runner:
        _setup_virtual_env_web_runner()
    if web_runner_web:
        _setup_virtual_env_web_runner_web()


def get_repos(branch='sc_production'):
    '''Download and install the main source repository'''
    puts(green('Updating repositories'))

    repo_path = _get_repo_path()
    if not cuisine.dir_exists(repo_path):
        run('mkdir -p ' + REPO_BASE_PATH)
        run('cd %s && git clone %s && cd %s && git checkout %s'
            % (REPO_BASE_PATH, REPO_URL, repo_path, branch))
    else:
        run('cd %s && git fetch && git checkout %s && git pull' % (repo_path, branch))


def _configure_scrapyd():
    venv_scrapyd = _get_venv_path(VENV_SCRAPYD)
    repo_path = _get_repo_path()

    run('cp %s/web_runner/conf/instance_two/scrapyd.conf %s'
        % (repo_path, venv_scrapyd))


def _configure_web_runner():
    venv_webrunner = _get_venv_path(VENV_WEB_RUNNER)
    repo_path = _get_repo_path()

    run('cp %s/web_runner/conf/instance_two/instance_two.ini %s'
        % (repo_path, venv_webrunner))


def _configure_web_runner_web():
    venv_webrunner_web = _get_venv_path(VENV_WEB_RUNNER_WEB)
    venv_webrunner_web_activate = '%s%sbin%sactivate' % (
        venv_webrunner_web, os.sep, os.sep)
    repo_path = _get_repo_path()

    settings_prod = repo_path + '/web_runner_web/web_runner_web/' \
        'settings.production.py'
    settings_link = repo_path + '/web_runner_web/web_runner_web/settings.py'

    # Create the settings.py
    if not cuisine.file_exists(settings_link):
        run('ln -s %s %s' % (settings_prod, settings_link))

    # Create the Django DB and Django users
    django_db = repo_path + '/web_runner_web/db.sqlite3'
    if not cuisine.file_exists(django_db):
        with virtualenv(VENV_WEB_RUNNER_WEB):
            run("cd %s/web_runner_web && ./manage.py syncdb --noinput"
                % repo_path)

        run('tmux new-window -k -t webrunner:4 -n django_config')
        run("tmux send-keys -t webrunner:4 'source %s' C-m" %
            venv_webrunner_web_activate)
        run("tmux send-keys -t webrunner:4 'cd %s' C-m" % repo_path)
        run("tmux send-keys -t webrunner:4 'cd web_runner_web' C-m")
        run("tmux send-keys -t webrunner:4 './manage.py shell' C-m")
        run("tmux send-keys -t webrunner:4 'from django.contrib.auth.models import User' C-m")
        run("tmux send-keys -t webrunner:4 'user = User.objects.create_user(username=\"admin\", password=\"Content\")' C-m")
        run("tmux send-keys -t webrunner:4 'exit()' C-m")


def setup_cron():
    """
    Setup cron tasks, for now only log compression
    """
    orig_user, orig_passw, orig_cert = env.user, env.password, env.key_filename
    env.user, env.password, env.key_filename = \
        SSH_SUDO_USER, SSH_SUDO_PASSWORD, SSH_SUDO_CERT
    cron_file = '/etc/cron.d/compresslogs'
    username = 'web_runner'
    homedir = '/home/web_runner'
    repopath = 'repos/tmtext/web_runner'
    scriptname = 'compress_old_logs_and_output_files.py'
    if files.contains(cron_file, scriptname):
        puts(green('Cron already installed'))
    else:
        files.append(cron_file,
                     '*/7  *  *  *  *  {user} /usr/bin/python {home}/{repo}/{script}'.format(
                         user=username, home=homedir, repo=repopath, script=scriptname
                     ),
                     use_sudo=True)
    env.user, env.password, env.key_filename = \
        orig_user, orig_passw, orig_cert

def setup_swap():
    """
    Create and enable swap, 8G
    """
    orig_user, orig_passw, orig_cert = env.user, env.password, env.key_filename
    env.user, env.password, env.key_filename = \
        SSH_SUDO_USER, SSH_SUDO_PASSWORD, SSH_SUDO_CERT
    swap_file = '/mnt/swapfile'
#    with settings(warn_only=True):
    result = sudo('/sbin/swapon -s')
    if swap_file not in result:
        sudo('dd if=/dev/zero of={swap} bs=1M count=8192'.format(swap=swap_file))
        sudo('/sbin/mkswap {swap}'.format(swap=swap_file))
        sudo('/sbin/swapon {swap}'.format(swap=swap_file))
        result = sudo('/sbin/swapon -s')
        if swap_file in result:
            files.append('/etc/fstab',
                         '{swap}  none    swap    sw    0    0'.format(swap=swap_file), use_sudo=True)
            sudo('chmod 600 {swap}'.format(swap=swap_file))
            sudo('chown root.root {swap}'.format(swap=swap_file))
    else:
        puts(green('Swap already enabled'))
    env.user, env.password, env.key_filename = \
        orig_user, orig_passw, orig_cert


def configure():
    puts(green('Configuring the servers'))

    _configure_scrapyd()
    _configure_web_runner()
    _configure_web_runner_web()



def _install_web_runner():
    venv_webrunner = _get_venv_path(VENV_WEB_RUNNER)
    venv_webrunner_activate = '%s%sbin%sactivate' \
        % (venv_webrunner, os.sep, os.sep)
    repo_path = _get_repo_path()

    run("tmux send-keys -t webrunner:1 'source %s' C-m" %
        venv_webrunner_activate)
    run("tmux send-keys -t webrunner:1 'cd %s' C-m" % repo_path)
    run("tmux send-keys -t webrunner:1 'cd web_runner' C-m")
    run("tmux send-keys -t webrunner:1 'rm -fr build dist' C-m")
    run("tmux send-keys -t webrunner:1 'python setup.py bdist_wheel' C-m")
    run("tmux send-keys -t webrunner:1 '/usr/bin/yes | pip uninstall web-runner' C-m")

    with virtualenv(VENV_WEB_RUNNER):
        with cd("%s/web_runner" % repo_path):
            # "build" has to be removed since it accumulates files.
            # "dist" has to be removed as it accumulates versions.
            run("rm -fr build dist")
            run('python setup.py bdist_wheel')
            run('pip install dist/web_runner-*.whl')


def install():
    _install_web_runner()


def _restart_scrapyd():
    puts(green('Stoping scrapyd'))

    try:
        run("tmux send-keys -t webrunner:0 C-c")
    except:
        pass


def _run_scrapyd_deploy():
    venv_scrapyd = _get_venv_path(VENV_SCRAPYD)
    venv_scrapyd_activate = '%s%sbin%sactivate' % (venv_scrapyd, os.sep, os.sep)
    repo_path = _get_repo_path()

    run('tmux new-window -k -t webrunner:4 -n scrapyd_deploy')
    run("tmux send-keys -t webrunner:4 'source %s' C-m" % venv_scrapyd_activate)
    run("tmux send-keys -t webrunner:4 'cd %s' C-m" % repo_path)
    run("tmux send-keys -t webrunner:4 'cd product-ranking' C-m")
    run("tmux send-keys -t webrunner:4 'scrapyd-deploy' C-m")
    run("tmux send-keys -t webrunner:4 'exit' C-m")


def _run_scrapyd():
    venv_scrapyd = _get_venv_path(VENV_SCRAPYD)
    venv_scrapyd_activate = '%s%sbin%sactivate' % (venv_scrapyd, os.sep, os.sep)

    run("tmux send-keys -t webrunner:0 'source %s' C-m" % venv_scrapyd_activate)
    run("tmux send-keys -t webrunner:0 'cd %s' C-m" % venv_scrapyd)
    run("tmux send-keys -t webrunner:0 'scrapyd' C-m")
    _run_scrapyd_deploy()


def _run_web_runner():
    venv_webrunner = _get_venv_path(VENV_WEB_RUNNER)
    venv_webrunner_activate = '%s%sbin%sactivate' \
        % (venv_webrunner, os.sep, os.sep)

    run("tmux send-keys -t webrunner:1 'source %s' C-m"
        % venv_webrunner_activate)
    run("tmux send-keys -t webrunner:1 'cd %s' C-m" % venv_webrunner)
    run("tmux send-keys -t webrunner:1 'pserve instance_two.ini --stop-daemon' C-m")
    run("tmux send-keys -t webrunner:1 'pserve instance_two.ini start' C-m")

#    with virtualenv(VENV_WEB_RUNNER):
#        if cuisine.file_exists('pyramid.pid'):
#            try:
#                run('pserve  instance_two.ini restart')
#            except:
#                run('pserve  instance_two.ini start')
#        else:
#            run('pserve  instance_two.ini start')


def _is_django_running():
    '''Return boolean representing if django is running or not'''
    process = run("ps -ef | grep python | grep manage | grep runserver; true")
    return process.stdout.find('\n') > 0


def _run_web_runner_web():
    venv_webrunner_web = _get_venv_path(VENV_WEB_RUNNER_WEB)
    venv_webrunner_web_activate = '%s%sbin%sactivate' \
        % (venv_webrunner_web, os.sep, os.sep)
    repo_path = _get_repo_path()

    if not _is_django_running():
        run("tmux send-keys -t webrunner:2 'source %s' C-m"
            % venv_webrunner_web_activate)
        run("tmux send-keys -t webrunner:2 'cd %s/web_runner_web' C-m"
            % repo_path)
        run("tmux send-keys -t webrunner:2 './manage.py runserver 0.0.0.0:8000' C-m")


def run_servers(restart_scrapyd=False):
    puts(green('Starting/restaring servers'))

    if restart_scrapyd:
        _restart_scrapyd()

    _run_scrapyd()
    _run_web_runner()
    _run_web_runner_web()


def _common_tasks():
    setup_users()
    setup_packages()
    setup_tmux()
    setup_swap()
    setup_cron()


def deploy_scrapyd(restart_scrapyd=False, branch='sc_production'):
    _common_tasks()
    setup_virtual_env(web_runner=False, web_runner_web=False)
    get_repos(branch=branch)
    _configure_scrapyd()

    if restart_scrapyd:
        _restart_scrapyd()
    _run_scrapyd()


def deploy_web_runner(branch='sc_production'):
    _common_tasks()
    setup_virtual_env(scrapyd=False, web_runner_web=False)
    get_repos(branch=branch)
    _configure_web_runner()
    _install_web_runner()
    _run_web_runner()


def deploy_web_runner_web(branch='sc_production'):
    _common_tasks()
    setup_virtual_env(scrapyd=False, web_runner=False)
    get_repos(branch=branch)
    _configure_web_runner_web()
    _run_web_runner_web()


def deploy(restart_scrapyd=False, branch='sc_production'):
    _common_tasks()
    setup_virtual_env()
    get_repos(branch=branch)
    configure()
    install()
    run_servers(restart_scrapyd)


def _restart_test_flask_uwsgi():
    orig_user, orig_passw, orig_cert = env.user, env.password, env.key_filename
    env.user, env.password, env.key_filename = \
        SSH_SUDO_USER, SSH_SUDO_PASSWORD, SSH_SUDO_CERT
    sudo('service uwsgi restart')
    env.user, env.password, env.key_filename = \
        orig_user, orig_passw, orig_cert


def deploy_sc_test_server(branch='sc_production'):
    _common_tasks()
    setup_virtual_env()
    get_repos(branch=branch)
    configure()
    install()
    _restart_test_flask_uwsgi()


def test_scrapy():
    search_terms = (
        'water', 'guitar', 'gibson', 'toy', 'books', 'laptop', 'smartphone'
    )
    cmd = ("curl --verbose http://localhost:6543/ranking_data/"
           "  -d 'site=amazon;searchterms_str=%s;quantity=10"
           ";group_name=test'")
    run(cmd % random.choice(search_terms))


def fix_captchas():
    """ This is a temporary fix and should be removed\changed in the future
        Written with dirty hacks such as copying local project files directly
         into virtualenv. Please get away from this nightmare-ish Scrapyd
         to the normal command-line calls!
    """
    # TODO: removeme\changeme
    orig_user, orig_passw, orig_cert = env.user, env.password, env.key_filename
    env.user, env.password, env.key_filename = \
        SSH_SUDO_USER, SSH_SUDO_PASSWORD, SSH_SUDO_CERT
    sudo('apt-get install -y python-opencv')
    sudo('chmod 777 -R /home/web_runner/virtual-environments/scrapyd/')
    sudo('cp /usr/lib/python2.7/dist-packages/cv* /home/web_runner/virtual-environments/scrapyd/lib/python2.7/site-packages/')
    env.warn_only = True
    sudo('mkdir /home/web_runner/repos/tmtext/product-ranking/captchas')
    sudo('mkdir /home/web_runner/repos/tmtext/product-ranking/solved_captchas')
    sudo("cp /home/web_runner/repos/tmtext/product-ranking/captcha_solver.py /home/web_runner/virtual-environments/scrapyd/lib/python2.7/")
    sudo('mkdir /home/web_runner/virtual-environments/scrapyd/train_captchas_data/')
    sudo('cp /home/web_runner/repos/tmtext/product-ranking/train_captchas_data/* /home/web_runner/virtual-environments/scrapyd/train_captchas_data/')
    env.warn_only = False
    sudo('chmod 777 -R /home/web_runner/repos/tmtext/product-ranking/captchas')
    sudo('chmod 777 -R /home/web_runner/repos/tmtext/product-ranking/solved_captchas')
    env.user, env.password, env.key_filename = \
        orig_user, orig_passw, orig_cert

    with virtualenv(VENV_SCRAPYD):
        run('pip install numpy')


def tmp_mass_execute():
    orig_user, orig_passw, orig_cert = env.user, env.password, env.key_filename
    env.user, env.password, env.key_filename = \
        SSH_SUDO_USER, SSH_SUDO_PASSWORD, SSH_SUDO_CERT
    env.warn_only = True
    sudo('pkill -9 -f scrapyd')

    run('sudo chmod 777 -R /scraper_data')
    env.warn_only = False
    env.user, env.password, env.key_filename = \
        orig_user, orig_passw, orig_cert



# vim: set expandtab ts=4 sw=4:
