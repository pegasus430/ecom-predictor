#
# Scans the ranking spiders dir and uploads the monitoring config
# and the files to the monitoring host. Also updates the crontab there.
#

import os
import re
import sys

from fabric.api import env, sudo, put
from fabric.contrib import files
import cuisine

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..'))
from monitoring import MONITORING_HOST, SIMMETRICA_CONFIG
HOST_USER = 'andr0s'
HOST_KEY = os.path.join(CWD, '..', '..', '..', '..',
                        'ssh_certificates', 'ubuntu_id_rsa')
PATH = '/home/monitoring'


def _setup_env(host):
    env.hosts = []

    env.reject_unknown_hosts = False
    env.disable_known_hosts = True

    # server 1
    env.host_string = HOST_USER + '@' + host
    env.user = HOST_USER
    #env.password = 'somepassword'
    env.key_filename = HOST_KEY


def find_spiders(path):
    """ Returns the list of spidernames and their domains """
    spiders = []
    for f in os.listdir(path):
        if not re.findall("(.*?).pyc", f):
            if os.path.isdir(os.path.join(path, f)):
                continue
            f = open(os.path.join(path, f), 'r')
            text = f.read()
            allowed_domains = re.findall(
                "allowed_domains\s*=\s*\[([^\]]*)\]", text)
            name = re.findall(r"name\s*=\s*('|\")([\w]+)(\1)", text)
            interm = []
            if name:
                interm.append(name[0][1])
            if allowed_domains:
                interm.append(allowed_domains[0].strip().replace(
                    "\"", "").replace("'", ""))
            if interm:
                spiders.append(interm)
    return spiders


def generate_config_for_spider(spider_name):
    config = """
    # {spider_name}
    - title: {spider_name}
      timespan: 7 day
      colorscheme: cool
      type: area
      interpolation: cardinal
      resolution: 15min
      size: M
      offset: zero
      events:
          - name: monitoring_spider_closed_{spider_name}
            title: Spider finished
          - name: monitoring_spider_working_time_{spider_name}
            title: Working time, seconds
          - name: monitoring_spider_dupefilter_filtered_{spider_name}
            title: Dupefilter/Filtered
          - name: monitoring_spider_downloader_request_count_{spider_name}
            title: Downloader requests - count
          - name: monitoring_spider_downloader_response_bytes_{spider_name}
            title: Megabytes downloaded
    """
    config = config.format(spider_name=spider_name)
    return config


def generate_general_config():
    config = """
    # General
    - title: Overall performance
      timespan: 7 day
      colorscheme: cool
      type: area
      interpolation: cardinal
      resolution: 15min
      size: M
      offset: zero
      events:
          - name: monitoring_spider_closed
            title: Spider finished
          - name: monitoring_spider_working_time
            title: Working time, seconds
    """
    return config


def upload_config(content):
    # must be a SUDO user
    cuisine.file_write(SIMMETRICA_CONFIG, content, mode=755, sudo=True)


def upload_files():
    """ Uploads the files from the specified path """
    put(os.path.join(CWD, '..', 'monitoring'), '/home',
        mode=0644, use_sudo=True)


def setup_cron():
    cron_file = '/etc/cron.d/send_alerts'
    script_name = 'send_alerts.py'

    _cron_line = \
        '*/37  *  *  *  *  root /usr/bin/python {path}/{script_name}'.format(
            path=PATH, script_name=script_name
        )
    if not files.contains(cron_file, script_name):
        files.append(cron_file, _cron_line, use_sudo=True)


def setup_paths():
    env.warn_only = True
    sudo('mkdir "%s"' % PATH)
    env.warn_only = False


def install_packages():
    cuisine.package_ensure('mc htop iotop python-pip')
    env.warn_only = True
    sudo('pip install -U boto simmetrica')
    env.warn_only = False


def restart_uwsgi():
    env.warn_only = True
    sudo('/etc/init.d/uwsgi restart')
    env.warn_only = False


if __name__ == '__main__':
    CWD = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(CWD, '..', 'product_ranking', 'spiders')
    spiders = find_spiders(os.path.realpath(path))
    spiders.sort(key=lambda val: val[0])  # sort by alphabet
    result = 'graphs:\n'
    result += generate_general_config() + '\n'
    for spider in spiders:
        result += generate_config_for_spider(spider[0]) + '\n'
    #print result
    _setup_env(MONITORING_HOST)
    setup_paths()
    install_packages()
    upload_config(result)
    setup_cron()
    upload_files()
    restart_uwsgi()
    print 'DONE'
