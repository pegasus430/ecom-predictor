# Put anything here you want to be executed BY THE SUPERUSER right after
#  the instance spins up

import os
import sys
from subprocess import check_output, CalledProcessError, STDOUT


main_folder = '/home/spiders/repo/'


def can_run():
    if os.path.exists(os.path.join(main_folder,
                                   'remote_instance_starter.py.marker')):
        # this script wasn't executed yet
        if not os.path.exists(os.path.join(main_folder, __file__+'.marker')):
            return True


def mark_as_finished():
    """ Mark this machine as the one that has already executed this script """
    with open(os.path.join(main_folder, __file__+'.marker'), 'w') as fh:
        fh.write('1')


def _install_system_package(package):
    """
    After running 'install' command, each package will be checked for succeeded
    installation process via 'dpkg -s'. In case, if any of these commands fail
    or return non-0 status code, http request will be sent to the url
    to indicate the error happened.
    """
    try:
        commands = ['sudo apt-get install -y %s', 'dpkg -s %s']
        for cmd in commands:
            check_output(cmd % package, shell=True, stderr=STDOUT)
    except CalledProcessError as e:
        data = dict(item=package, error=e.output)
        # check if error was caused by running script second time
        #  if so, ignore it
        if 'Could not get lock /var/lib/dpkg/lock' in data['error']:
            return
        try:
            import urllib2
            import urllib
            import base64
            from cache_settings import CACHE_AUTH
            url = 'http://sqs-metrics.contentanalyticsinc.com/log_install_error'
            req = urllib2.Request(url, urllib.urlencode(data))
            base64string = base64.b64encode('%s:%s' % CACHE_AUTH)
            req.add_header('Authorization', 'Basic {}'.format(base64string))
            urllib2.urlopen(req)
        except Exception:
            pass


def main():
    f = open('/tmp/check_file_post_starter_root_new', 'w')
    f.write('1')
    f.close()
    # put anything you want here...
    # install extra system packages
    tmp_cron_name = 'mycron'
    os.system('crontab -l > %s' % tmp_cron_name)
    with open(tmp_cron_name, 'a') as f:
        cmd = \
        '* * * * * cd /home/spiders/repo/tmtext/deploy/sqs_ranking_spiders;'\
        ' source /home/spiders/virtual_environment/bin/activate && '\
        'python self_killer_script.py \n'
        f.write(cmd)
        f.write('\n')
    os.system('crontab %s' % tmp_cron_name)
    os.system('sudo apt-get update')
    # _install_system_package('tesseract-ocr')
    # _install_system_package('xvfb')
    # _install_system_package('wget')
    _install_system_package('chromium-browser')
    _install_system_package('libnss3')
    _install_system_package('firefox')
    _install_system_package('phantomjs')
    # _install_system_package('python-setuptools')
    # _install_system_package('python-distutils-extra')
    # _install_system_package('python-apt')
    _install_system_package('python-lxml')
    # _install_system_package('python-requests')
    # TODO: phantomjs2
    os.system(
        "cd ~"
        " && wget http://chromedriver.storage.googleapis.com/{version}/chromedriver_linux64.zip -O chromedriver_linux64.zip"
        " && unzip -o chromedriver_linux64.zip"
        " && sudo mv chromedriver /usr/sbin/"
        " && sudo chmod +x /usr/sbin/chromedriver".format(version=get_latest_chromedriver_version())
    )
    # download & install phantomjs2
    os.system(
        "cd ~"
        " && wget https://github.com/Pyppe/phantomjs2.0-ubuntu14.04x64/raw/master/bin/phantomjs"
        " && sudo mv phantomjs /usr/sbin/phantomjs2"
        " && sudo chmod +x /usr/sbin/phantomjs2"
    )
    # download and install geckodriver (for Firefox)
    # disable marketplaces (they are too slow)
    disabler = '/tmp/stop_marketplaces'
    os.system('echo "1" > %s' % disabler)


def remove_aws_credentials(keys=('/home/spiders/.aws/credentials', )):
    """ Remove local AWS credentials file since we've switched to metadata-based keys """
    for key in keys:
        if os.path.exists(key):
            print 'AWS credentials removed:', key
            os.remove(key)

def get_latest_chromedriver_version():
    import urllib2
    try:
        response = urllib2.urlopen('http://chromedriver.storage.googleapis.com/LATEST_RELEASE')
        version = response.read().strip()
    except:
        version = '2.29'
    return version

if __name__ == '__main__':
    remove_aws_credentials()
    if not can_run():
        sys.exit()
    main()
    mark_as_finished()