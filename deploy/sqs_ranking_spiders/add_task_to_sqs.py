import sys
import json
import random
import os
import pprint
import ConfigParser

from boto.sqs.message import Message, RawMessage
import boto.sqs

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, '..'))

from sqs_ranking_spiders import QUEUES_LIST

CREDENTIALS_FILE = '~/.sqs_credentials'  # u have to create it to test locally

### Script can be run with 'manual' argument to provide manual edditing
# of task message


def put_msg_to_sqs(message, queue_name=QUEUES_LIST['test']):
    conn = boto.sqs.connect_to_region("us-east-1")
    q = conn.create_queue(queue_name)
    print "created/get queue: ", q
    # q = conn.get_queue(queue_name)
    # if not q:
    #     q = conn.create_queue(queue_name)
    #     q = conn.get_queue(queue_name)
    #m = Message()
    m = RawMessage()
    m.set_body(json.dumps(message))
    q.write(m)
    print("Task was provided to sqs %s" % queue_name)
    # print("Task:\n{}".format(message))
    print "="*5
    pprint.pprint(message)


def edit_message(msg):
    keys = ['task_id', 'site', 'searchterms_str', 'server_name']
    for key in keys:
        data = raw_input("Provide '%s' for task message.\n"
                         "If you left field blunk default value will be used.\n"
                         ">>> " % key)
        if data:
            msg[key] = data
    additional_args = raw_input("Provide additional arguments if required "
                                "in format arg=value;arg2=value2\n>>> ")
    args_dict = {}
    for i in additional_args.split(';'):
        splited = i.split('=')
        args_dict[splited[0]] = splited[1]
    if 'quantity' not in args_dict.keys():
        args_dict['quantity'] = 100
    msg['cmd_args'] = args_dict


if __name__ == '__main__':
    msg = {
            'task_id': 4444,
            'site': 'amazon',
            'searchterms_str': random.choice(['water', 'cola', 'wine']),
            'server_name': 'test_server_name',
            # "url": "http://www.walmart.com/ip/42211446?productRedirect=true",
            'cmd_args': {'quantity': 30}
        }
    if 'manual' in [a.lower().strip() for a in sys.argv]:
        edit_message(msg)

    # you can pass additional args like task_id=123 or searchterms_str=cola
    for arg in sys.argv:
        # TODO: SC+CH "batch" URL support (like -a products_url=url1||||url2||||url3)
        if 'task_id=' in arg:
            extra_marker, extra_marker_value = arg.split('=')
            if not 'cmd_args' in msg:
                msg['cmd_args'] = {}
            msg['task_id'] = extra_marker_value.strip()
        if 'searchterms_str=' in arg:
            _str, _st_value = arg.split('=')
            msg['searchterms_str'] = _st_value.strip()
        if 'server_name=' in arg:
            _str, _st_value = arg.split('=')
            msg['server_name'] = _st_value.strip()
        if 'product_url=' in arg:
            _str, _st_value = arg.split('=', 1)
            msg['url'] = _st_value.strip()
            try:
                del msg['searchterms_str']
            except Exception as e:
                print e
            try:
                del msg['cmd_args']['quantity']
            except Exception as e:
                print e
        if 'with_best_seller_ranking=' in arg:
            _str, _st_value = arg.split('=')
            msg['with_best_seller_ranking'] = _st_value.strip()
        if 'branch_name=' in arg:
            _str, _st_value = arg.split('=')
            msg['branch_name'] = _st_value.strip()
    put_msg_to_sqs(msg)