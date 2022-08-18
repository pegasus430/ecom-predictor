import json
import time

import boto.sqs
from boto.sqs.message import RawMessage
from boto.s3.connection import S3Connection

from dateutil.parser import parse as parse_date
from datetime import datetime, timedelta

from django.shortcuts import render
from django.http import JsonResponse

from .forms import ImmediateForm

SERVER_NAME = 'test_server'

QUEUE_INPUT = 'scraper_walmart-test_in'
QUEUE_OUTPUT = 'immediate_output'

TIMEOUT_LITE = 60 * 5  # wait 5 minutes for the response in the output queue
TIMEOUT_HARD = 60 * 60  # store messages in the output queue for 60 minutes
TIMEOUT_VISIBILITY = 3  # 3 sec for scanning output queue


def immediate_run(request):
    if request.method == 'POST':
        form = ImmediateForm(request.POST)

        if form.is_valid():
            url = form.cleaned_data['url']
            site = form.cleaned_data['site']

            response = {
                'success': True,
                'url': url,
            }

            try:
                # try to find message for the same request
                message = find_message(site, url)

                if not message:
                    send_message(site, url)

                message = find_message(site, url, timeout=TIMEOUT_LITE)
                if message:
                    response['sqs'] = message

                    data = get_data(message)
                    if data:
                        response['result'] = data
                    else:
                        response['success'] = False
                        response['message'] = 'Task failed. No data'
                else:
                    response['message'] = 'Task is not ready yet, check later'
            except Exception as e:
                response['success'] = False
                response['message'] = e.message

            return JsonResponse(response)
    else:
        form = ImmediateForm()

    return render(request, 'form.html', {'form': form})


def send_message(site, url):
    body = {
        'site': site,
        'server_name': SERVER_NAME,
        'url': url,
        'response_format': 'sc',  # TODO: let to select CH
        'result_queue': QUEUE_OUTPUT
    }

    message = RawMessage()
    message.set_body(json.dumps(body))

    queue = get_queue(QUEUE_INPUT)
    queue.write(message)


def find_message(site, url, timeout=None):
    queue = get_queue(QUEUE_OUTPUT)

    time_start = time.time()

    while timeout is None or time.time() - time_start < timeout:
        # scan output queue
        messages = queue.get_messages(num_messages=10, visibility_timeout=TIMEOUT_VISIBILITY)

        for message in messages:
            body = message.get_body()

            if isinstance(body, basestring):
                body = json.loads(body)

            # remove old messages
            utc_datetime = body.get('utc_datetime', None)

            if utc_datetime:
                utc_datetime = parse_date(utc_datetime)

                if utc_datetime < datetime.now() - timedelta(seconds=TIMEOUT_HARD):
                    queue.delete_message(message)

                    continue

            if body.get('site') == site and body.get('url') == url:
                queue.delete_message(message)

                return body

        # not repeat
        if timeout is None:
            break


def get_data(body):
    if body.get('status') == 'success':
        bucket = body.get('bucket_name') or 'spyder-bucket'
        json_data_file = body.get('s3_key_data', None) or body.get('s3_filepath', None)

        aws_connection = S3Connection()
        bucket = aws_connection.get_bucket(bucket)
        key = bucket.get_key(json_data_file)

        return json.loads(key.get_contents_as_string())


def get_queue(name):
    connection = boto.sqs.connect_to_region("us-east-1")
    queue = connection.lookup(name)

    if not queue:
        queue = connection.create_queue(name)

    return queue
