#
# This script is going to check if EC2/S3/SQS/SES services are accessible from this machine
#

import random

import boto.ec2
import boto.sqs
import boto.ses
from boto.s3.connection import S3Connection
from boto.ec2.autoscale import AutoScaleConnection


class Email(object):
    def __init__(self, to, subject):
        self.to = to
        self.subject = subject
        self._html = None
        self._text = None
        self._format = 'html'

    def html(self, html):
        self._html = html

    def text(self, text):
        self._text = text

    def send(self, from_addr=None):
        body = self._html

        if isinstance(self.to, basestring):
            self.to = [self.to]
        if not from_addr:
            from_addr = 'me@example.com'
        if not self._html and not self._text:
            raise Exception('You must provide a text or html body.')
        if not self._html:
            self._format = 'text'
            body = self._text

        connection = boto.ses.connect_to_region('us-east-1')

        return connection.send_email(
            from_addr,
            self.subject,
            None,
            self.to,
            format=self._format,
            text_body=self._text,
            html_body=self._html
        )


def check_ec2(groups_names=('SCCluster1', 'SCCluster2', 'SCCluster3', 'SCCluster4')):
    # TODO: update group names!
    # check autoscaling
    conn = AutoScaleConnection()
    selected_group_name = random.choice(groups_names)
    group = conn.get_all_groups(names=[selected_group_name])[0]
    if not group:
        return

    # check ec2
    ec2 = boto.ec2.connect_to_region('us-east-1')
    images = ec2.get_all_images()
    if not images:
        return

    return True


def check_s3(bucket_name):
    conn = S3Connection()
    bucket = conn.get_bucket(bucket_name)
    return bool(bucket.list())


def check_sqs():
    q_prefix = 'sqs_ranking_spiders'
    conn = boto.sqs.connect_to_region('us-east-1')
    queues = conn.get_all_queues(prefix=q_prefix)
    _ = sum(q.count() for q in queues)
    return True


def check_ses():
    test_code = ''.join([str(random.randint(0, 9)) for _ in xrange(8)])

    email = Email(to='test@gmail.com', subject=__file__)
    email.text('Text code: %s' % test_code)
    email.html('<html><body>HTML code: <b>%s</b></body></html>' % test_code)
    email.send(from_addr='noreply@contentanalyticsinc.com')

    return test_code


if __name__ == '__main__':
    if not check_ec2():
        print 'EC2: NOT WORKING'
    else:
        print 'EC2: OK'

    if not check_s3('spyder-bucket'):
        print 'S3: NOT WORKING'
    else:
        print 'S3: OK'

    if not check_sqs():
        print 'SQS: NOT WORKING'
    else:
        print 'SQS: OK'

    test_code = check_ses()
    print 'SES: check mailbox test@gmail.com for an email with code %s' % test_code
