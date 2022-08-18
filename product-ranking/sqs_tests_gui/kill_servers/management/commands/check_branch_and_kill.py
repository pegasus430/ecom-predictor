# TODO: make sure Amazon Load-Balancer won't upscale groups after we set them to 0
# (in order for all instances to get killed)

import os
import sys
import shutil
import hashlib
import time
import datetime
import subprocess
import json

from django.core.management.base import BaseCommand

CWD = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(os.path.join(CWD, '..', '..', '..', '..'))

from kill_servers.models import ProductionBranchUpdate, ServerKill
from sqs_stats import set_autoscale_group_capacity,\
    get_number_of_instances_in_autoscale_groups, get_max_instances_in_groups


sys.path.append(os.path.join(CWD,  '..', '..', '..', '..', '..',
                             'deploy', 'sqs_ranking_spiders'))
from libs import get_autoscale_groups
#from add_task_to_sqs import put_msg_to_sqs


def run(command, shell=None):
    """ Run the given command and return its output
    """
    out_stream = subprocess.PIPE
    err_stream = subprocess.PIPE

    if shell is not None:
        p = subprocess.Popen(command, shell=True, stdout=out_stream,
                             stderr=err_stream, executable=shell)
    else:
        p = subprocess.Popen(command, shell=True, stdout=out_stream,
                             stderr=err_stream)
    (stdout, stderr) = p.communicate()

    return stdout, stderr


def num_of_running_instances(file_path):
    """ Check how many instances of the given file are running """
    processes = 0
    output = run('ps aux')
    output = ' '.join(output)
    for line in output.split('\n'):
        line = line.strip()
        line = line.decode('utf-8')
        if file_path in line and not '/bin/sh' in line:
            processes += 1
    return processes


class Command(BaseCommand):
    help = 'Tracks changes of the SC production branch'

    repo_dir = '/tmp/_repo/tmtext'
    git_log_file = '/tmp/_git_log_file'

    def _save_group_sizes(self, fname='/tmp/_group_sizes.json'):
        """ Stores autoscale groups sizes locally """
        result = {}
        for autoscale_group, items in get_max_instances_in_groups().items():
            result[autoscale_group] = items['max_size']
        with open(fname, 'w') as fh:
            fh.write(json.dumps(result))

    def _load_group_sizes(self, fname='/tmp/_group_sizes.json'):
        """ Stores autoscale groups sizes locally """
        with open(fname, 'r') as fh:
            return json.loads(fh.read())

    def _clone_repo(self, branch):
        old_dir = os.getcwd()
        if os.path.exists(self.repo_dir):
            shutil.rmtree(self.repo_dir)
        if not os.path.exists(os.path.dirname(self.repo_dir)):
            os.makedirs(os.path.dirname(self.repo_dir))
        os.chdir(os.path.dirname(self.repo_dir))
        os.system('git clone git@bitbucket.org:dfeinleib/tmtext.git')
        os.chdir(self.repo_dir)
        os.system('git checkout %s' % branch)
        os.system('git pull origin %s' % branch)
        os.chdir(old_dir)

    def _repo_hashsum(self):
        old_dir = os.getcwd()
        os.chdir(self.repo_dir)
        os.system('git log -n 100 > %s' % self.git_log_file)
        os.chdir(old_dir)
        with open(self.git_log_file, 'r') as fh:
            cont = fh.read()
        return hashlib.sha1(cont).hexdigest()

    def _cleanup(self):
        shutil.rmtree(self.repo_dir)
        os.remove(self.git_log_file)

    def _set_autoscale_capacities_to_zero(self):
        for group in get_autoscale_groups()['groups']:
            print 'setting autoscale group size to 0: %s' % group
            set_autoscale_group_capacity(group, 0, attributes=('max_size', 'desired_capacity'))

    def _set_autoscale_max_instances(self):
        groups = self._load_group_sizes()
        for group, size in groups.items():
            time.sleep(5)
            print 'setting autoscale group size to %s: %s' % (size, group)
            set_autoscale_group_capacity(group, size, attributes=('max_size',))

    def handle(self, *args, **options):
        if num_of_running_instances('check_branch_and_kill') > 1:
            print 'another instance of the script is already running - exit'
            sys.exit()

        # check if we need to update the config file that contains sizes of all groups
        should_update_size = True
        for autoscale_group, items in get_max_instances_in_groups().items():
            max_size = items['max_size']
            if not max_size or max_size == 0:
                should_update_size = False

        if should_update_size:
            self._save_group_sizes()

        # restore groups sizes if needed (sizes may equal to 0 due to some errors in deploy)
        for autoscale_group, items in get_max_instances_in_groups().items():
            max_size = items['max_size']
            if not max_size or max_size == 0:
                self._set_autoscale_max_instances()

        branch = ProductionBranchUpdate.branch_to_track
        # get last commit id
        last_commit_hashsum = ProductionBranchUpdate.objects.all().order_by('-when_updated')
        if last_commit_hashsum:
            last_commit_hashsum = last_commit_hashsum[0].last_commit_hashsum
        else:
            last_commit_hashsum = '-111'  # non-existing, invalid commit ID

        self._clone_repo(branch)
        repo_hashsum = self._repo_hashsum()
        self._cleanup()

        if repo_hashsum != last_commit_hashsum:
            # check if there are some unfinished kills already
            if ServerKill.objects.filter(started__isnull=False, finished__isnull=True):
                print("There's already some unfinished ServerKill DB records! - exit")
                sys.exit()

            branch_update = ProductionBranchUpdate.objects.create(last_commit_hashsum=repo_hashsum)

            print('Need to restart servers')
            print('Setting autoscale groups to zero')
            server_kill = ServerKill.objects.create(branch_update=branch_update)
            self._set_autoscale_capacities_to_zero()
            while 1:
                time.sleep(10)
                sizes_sum = 0
                a_groups = get_number_of_instances_in_autoscale_groups()
                for g_name, g_size in a_groups.items():
                    g_size = g_size['current_size']
                    sizes_sum += g_size
                if sizes_sum == 0:
                    print('Autoscale groups are empty now')
                    break  # ok we have finally killed all the instances
            self._set_autoscale_max_instances()

            server_kill.finished = datetime.datetime.utcnow()
            server_kill.save()

            print('Restored autoscale groups sizes back')
        else:
            print('No restart needed')
