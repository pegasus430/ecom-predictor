import logging
from math import ceil
import random

import boto.sqs
from boto.ec2.autoscale import AutoScaleConnection

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s, %(levelname)s] %(message)s',
    filename='/tmp/load_balancer.log'
)
logger = logging.getLogger(__name__)


def get_sqs_tasks_count():
    q_prefix = 'sqs_ranking_spiders'
    tasks_count = 0
    try:
        conn = boto.sqs.connect_to_region('us-east-1')
        queues = conn.get_all_queues(prefix=q_prefix)
        tasks_count = sum(q.count() for q in queues)
    except Exception as e:
        logger.error('get_sqs_tasks_count error: %s', e)
    return tasks_count


def scale_instances(tasks_per_instance, group_name, total_groups):
    conn = AutoScaleConnection()
    group = conn.get_all_groups(names=[group_name])[0]

    if group.desired_capacity == group.max_size:
        logger.info('Maximum number of instances reached')
        return
    tasks_count = get_sqs_tasks_count()
    if not tasks_count:
        logger.info('No tasks left in queues')
        return
    logger.info('Num of tasks in queues %s', tasks_count)

    tasks_per_instance = float(tasks_per_instance)
    additional_instances_count = int(ceil(tasks_count/tasks_per_instance) / total_groups)
    updated_instances_count = \
        group.desired_capacity + additional_instances_count
    # consider max allowed instances
    if updated_instances_count > group.max_size:
        updated_instances_count = group.max_size

    logger.info('Updating group from %s to %s instances',
                group.desired_capacity, updated_instances_count)
    group.set_capacity(updated_instances_count)
    group.desired_capacity = updated_instances_count
    group.update()
    logger.info('Done\n')


if __name__ == '__main__':
    groups_names = ('SCCluster3', 'SCCluster4')  # contact Alex Kondratiev before changing this!
    # TODO: discuss with Alex what to do with this script (if we need it at all?)
    #  if yes - update group configs (S3 key) and specify clearly there whether a group is autoscaled by this script or not
    for group_name in groups_names:
        logger.info('PROCESSING QUEUE %s', group_name)
        scale_instances(tasks_per_instance=16, group_name=group_name,
                        total_groups=len(groups_names))
