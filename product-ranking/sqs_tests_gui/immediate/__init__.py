import tempfile
import subprocess
import os
import re
import time

from urlparse import urlparse


REPO_DIR = tempfile.mkdtemp()

REPO_DIR_UPDATE_PERIOD = 60  # don't update repo early then 60 sec from previous update


def find_sites(url):

    domains = urlparse(url).netloc.split('.')
    domains = set(['.'.join(domains[i:]) for i in range(len(domains))])

    update_code()
    spiders = find_spiders(domains)

    return [spider.replace('_products', '') for spider in spiders]


def find_spiders(domains):
    spiders = []

    path = os.path.join(REPO_DIR, 'content_analytics', 'spiders')

    if os.path.exists(path):
        for spider_filename in os.listdir(path):
            if os.path.isdir(os.path.join(path, spider_filename)):
                continue

            with open(os.path.join(path, spider_filename)) as spider_file:
                spider = spider_file.read()

                name = re.search(r'\s*name\s*=\s*[\'"](\w+)[\'"]', spider)

                if name:
                    name = name.group(1)

                    allowed_domains = re.search(r'\s*allowed_domains\s*=\s*\[(.+?)\]', spider)

                    if allowed_domains:
                        allowed_domains = map(lambda x: re.sub(r'[\s\'"]', '', x), allowed_domains.group(1).split(','))

                        if domains & set(allowed_domains):
                            spiders.append(name)

    return spiders


def update_code():
    # using ~/.ssh/new_scrapers_rsa key
    if not os.listdir(REPO_DIR):
        command = ['git', 'clone', 'git@git-ca:ContentAnalytics/scrapers.git', REPO_DIR]
        subprocess.check_call(command)
    else:
        path = os.path.join(REPO_DIR, '.git', 'FETCH_HEAD')

        if not os.path.exists(path) or time.time() - os.path.getmtime(path) > REPO_DIR_UPDATE_PERIOD:
            command = ['git', '--work-tree', REPO_DIR, '--git-dir', os.path.join(REPO_DIR, '.git'), 'pull']
            subprocess.check_call(command)
