#
# List Scrapy processes on all SQS instances of our autoscale group
#


import os
import sys
import datetime
import json
import time
import multiprocessing as mp
import logging
import logging.config
import subprocess


import boto
import boto.ec2
from boto.s3.key import Key
from boto.ec2.autoscale import AutoScaleConnection


ssh_key = '/home/ubuntu/.ssh/ubuntu_id_rsa'
autoscale_conn = None


def get_all_group_instances_and_conn():
    conn = AutoScaleConnection()
    global autoscale_conn
    autoscale_conn = conn
    ec2 = boto.ec2.connect_to_region('us-east-1')
    groups = conn.get_all_groups(
        names=['SCCluster1', 'SCCluster2', 'SCCluster3', 'SCCluster4'])  # TODO: update this list
    instances = [instance for group in groups for instance in group]
    if not instances:
        sys.exit()
    instance_ids = [instance.instance_id for instance in instances]
    instances = ec2.get_only_instances(instance_ids)
    return instances, conn


def get_processes(ssh_key, inst_ip):
    base_cmd = "ssh -o 'StrictHostKeyChecking no' -i %s ubuntu@%s 'ps aux'"
    cmd = base_cmd % (ssh_key, inst_ip)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out, err = p.communicate()
    return [l.strip() for l in out.splitlines() if l.strip()]


def main():
    instances, conn = get_all_group_instances_and_conn()
    names = ', '.join([inst.id for inst in instances])
    for inst in instances:
        processes = get_processes(ssh_key=ssh_key, inst_ip=inst.ip)
        print
        print inst
        print ' '*4, processes

if __name__ == '__main__':
    assert False, 'this script is no longer working, see TODO'
    main()