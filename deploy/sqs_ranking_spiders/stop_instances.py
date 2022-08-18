import os
import sys
import json
import time
import multiprocessing as mp
import logging
import logging.config
import subprocess
import random


import boto
import boto.ec2
from boto.s3.key import Key
from boto.ec2.autoscale import AutoScaleConnection

from libs import get_autoscale_groups


"""This script will stop all remote instances where spider finish
it's task, failed to start scrapy or still wait for tasks.

Instance will not be deleted if task still performed or
file /tmp/remote_instance_starter2.log is blank.

Script should be provided with SSH key so that it can connect to remote
servers.

And should be stored on instance that hace access to amazon
EC2 and autoscale.

After performing tasks script will upload logs to S3 bucket.
"""

# log settings
log_file_path = '/tmp/instances_killer_logs.log'
log_settings = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(levelname)s:%(message)s'
        }
    },
    'handlers': {
        'to_log_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'default',
            'filename': log_file_path,
            'maxBytes': 1024*1024*1024, # 1GB
            'backupCount': 1,
        },
        'console':{
            'level':'DEBUG',
            'class':'logging.StreamHandler',
            'formatter': 'default'
        },
    },
    'loggers': {
        'killer_log': {
            'level': 'DEBUG',
            'handlers': ['to_log_file', 'console']
        }
    },
}
logging.config.dictConfig(log_settings)
logger = logging.getLogger('killer_log')
BUCKET_NAME = 'spyder-bucket'
BUCKET_KEY = 'instances_killer_logs'
TOTAL_WAS_TERMINATED = 0
autoscale_conn = None


def get_all_group_instances_and_conn(
        groups_names=get_autoscale_groups()['groups']):
    conn = AutoScaleConnection()
    global autoscale_conn
    autoscale_conn = conn
    ec2 = boto.ec2.connect_to_region('us-east-1')
    selected_group_name = random.choice(groups_names)
    logger.info('Selected autoscale group: %s' % selected_group_name)
    group = conn.get_all_groups(names=[selected_group_name])[0]
    if not group.instances:
        logger.info("No working instances in selected group %s" % selected_group_name)
        upload_logs_to_s3()
        sys.exit()
    instance_ids = [i.instance_id for i in group.instances]
    instances = ec2.get_only_instances(instance_ids)
    return instances, conn


def check_is_scrapy_daemon_not_running(ssh_key, inst_ip):
    base_cmd = "ssh -o 'StrictHostKeyChecking no' -i %s ubuntu@%s 'ps aux'"
    cmd = base_cmd % (ssh_key, inst_ip)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out, err = p.communicate()
    for line in out.splitlines():
        if 'scrapy_daemon.py' in line:
            return False
    return True


def check_logs_status(file_path):
    """
    returns tuple of two elements,
    if first element is True, then instance finished work and can be stopped,
    second element is finish reason string
    """
    flag = False
    reason = ''
    try:
        f = open(file_path)
    except IOError:
        return flag, reason
    last_lines = f.readlines()[-20:]  # read last lines
    end_marker_ok = 'Scrapy daemon finished'
    end_marker_fail = 'Finished with error'
    for line in last_lines:
        if end_marker_ok in line:
            flag = True
            reason = 'Task was finished'
            break
        elif end_marker_fail in line:
            flag = True
            reason = 'Task failed with errors'
            break
    else:
        reason = 'No logs exist'
        flag = False
    return flag, reason


def teminate_instance_and_log_it(inst_ip, inst_id, reason):
    global autoscale_conn, TOTAL_WAS_TERMINATED
    logger.warning("Instance with ip=%s and id=%s was terminated"
                   " due to reason='%s'.", inst_ip, inst_id, reason)
    autoscale_conn.terminate_instance(inst_id, decrement_capacity=True)
    TOTAL_WAS_TERMINATED += 1


def stop_if_required(inst_ip, inst_id):
    """If this method return 'True' it will mean that script failed
    to downoad or handle logs and the instance should be stopped"""
    tmp_file = '/tmp/tmp_file'
    # purge previous entry
    open(tmp_file, 'w').close()
    # ssh_key = '/home/ubuntu/.ssh/ubuntu_id_rsa'
    ssh_key = '/home/ubuntu/.ssh/tmtext_rsa'
    cmd = 'scp -o "StrictHostKeyChecking no" -i %s '\
          'ubuntu@%s:/tmp/remote_instance_starter2.log %s'
    run_cmd = cmd % (ssh_key, inst_ip, tmp_file)
    proc = mp.Process(target=os.system, args=(run_cmd,))
    proc.start()
    checker = 0
    # it will give 5 minutes to downloads logs.
    while checker < 60*5:
        if proc.is_alive():
            checker += 1
            time.sleep(1)
        else:
            break
    else:
        proc.terminate()
        logger.error('Failed to download logs, instance %s (%s), terminating.',
                     inst_ip, inst_id)
        return True
    try:
        flag, reason = check_logs_status(tmp_file)
    except Exception as e:
        logger.exception(e)
        return True
    print(inst_id, inst_ip, flag, reason)
    if flag:
        if reason == 'No logs exist':
            return True
        if reason in ['Task was finished', 'Task failed with errors']:
            time.sleep(30)
        teminate_instance_and_log_it(inst_ip, inst_id, reason)
    else:
        return check_is_scrapy_daemon_not_running(ssh_key, inst_ip)


def update_unresponded_dict_or_terminate_instance(inst_ip, inst_id,
                                                  unresponded, state_code=None):
    if inst_id in unresponded.keys():
        last_time = unresponded[inst_id][1]
        # if instance not responded for 32 minutes already
        if time.time() - int(last_time) > 32*60:
            reason = "Instance not respond for 32 minutes or "\
                     "failed to downoald logs"
            teminate_instance_and_log_it(
                inst_ip,
                inst_id,
                reason=reason
            )
            del unresponded[inst_id]
    else:
        unresponded[inst_id] = [inst_ip, time.time()]


def delete_old_unresponded_hosts(unresponded):
    for inst_id in unresponded.keys():
        last_time = unresponded[inst_id][1]
        if time.time() - int(last_time) > 60*60*24*3:  # three day
            del unresponded[inst_id]

def get_amazon_connection():
    conn = boto.connect_s3()
    bucket = conn.get_bucket(BUCKET_NAME)
    k = Key(bucket)
    k.key = BUCKET_KEY
    return k


def get_logs_from_s3():
    k = get_amazon_connection()
    k.get_contents_to_filename(log_file_path)


def upload_logs_to_s3():
    k = get_amazon_connection()
    k.set_contents_from_filename(log_file_path)


def main():
    get_logs_from_s3()
    instances, conn = get_all_group_instances_and_conn()
    names = ', '.join([inst.id for inst in instances])
    logger.info("Instances running at this moment: %s", names)
    total_instances = len(instances)
    not_responded_hosts = '/tmp/not_responded_hosts'
    if not os.path.exists(not_responded_hosts):
        f = open(not_responded_hosts, 'w')
        f.close()
    with open(not_responded_hosts, 'r') as f:
        try:
            unresponded = json.load(f)
        except:
            unresponded = {}
    for instance in instances:
        print('\n------------')
        # instance is not running
        if instance.state_code != 16:
            update_unresponded_dict_or_terminate_instance(
                instance.ip_address,
                instance.id,
                unresponded,
                instance.state_code
            )
        else:
            inst_ip = instance.ip_address
            inst_id = instance.id
            failed_to_downoad_logs = stop_if_required(inst_ip, inst_id)
            if failed_to_downoad_logs:
                update_unresponded_dict_or_terminate_instance(
                    inst_ip,
                    inst_id,
                    unresponded,
                    instance.state_code
                )
    delete_old_unresponded_hosts(unresponded)
    with open(not_responded_hosts, 'w') as f:
        f.write(json.dumps(unresponded))
    logger.info("Were terminated %s instances from %s total.",
                TOTAL_WAS_TERMINATED, total_instances)
    upload_logs_to_s3()

if __name__ == '__main__':
    main()