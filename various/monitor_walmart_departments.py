#
# Check FTP server, if we haven't received updated
# department lists for more than 7 days,
# send email alert to support@contentanalyticsinc.com 1x/day every day
# until the problem is corrected.
#
# See https://bugzilla.contentanalyticsinc.com/show_bug.cgi?id=8916#c0
#

import os
import sys
import urllib2
import datetime

import boto.ses


DEBUG = False

UPLOAD_DIR = '/walmart/departments'
THRESHOLD = 7  # days

from ses_secret import SES_SECRET, SES_KEY

EMAIL_FROM = 'noreply@contentanalyticsinc.com'
EMAIL_TO = 'support@contentanalyticsinc.com'
EMAIL_SUBJ = 'Missing Walmart Directory Files'
EMAIL_BODY = """
Last file received: {last_file_received_name}

Date of its upload: {last_file_received_date} (UTC)

Threshold: {threshold} day(s)
"""

if DEBUG:
    #EMAIL_BODY = "TEST EMAIL! IGNORE THIS ALERT - " + EMAIL_SUBJ
    EMAIL_TO = 'test@gmail.com'


def _get_ip(ip_fname='/tmp/_my_ip_address'):
    urls2check = ['http://ipv4.icanhazip.com/', 'http://checkip.amazonaws.com/']
    if os.path.exists(ip_fname):
        with open(ip_fname, 'r') as fh:
            return fh.read().strip()
    for url2check in urls2check:
        ip = urllib2.urlopen(url2check, timeout=15).read().strip()
        if ip:
            with open(ip_fname, 'w') as fh:
                fh.write(ip)
            return ip


def _send_email(sender, subject, body, to):
    global SES_KEY, SES_SECRET
    conn = boto.ses.connect_to_region(
        'us-east-1',
        aws_access_key_id=SES_KEY,
        aws_secret_access_key=SES_SECRET)
    conn.send_email(source=sender, subject=subject, body=body, to_addresses=to)


def _get_last_file_received(upload_dir):
    last_file_name = None
    last_file_dt = None
    for f in os.listdir(upload_dir):
        if not '.xml' in f:
            continue
        f = os.path.join(upload_dir, f)
        dt = os.path.getmtime(f)
        dt = datetime.datetime.utcfromtimestamp(dt)
        if last_file_name is None:
            last_file_name = f
            last_file_dt = dt
        if dt > last_file_dt:
            last_file_name = f
            last_file_dt = dt
    return {'file': last_file_name, 'modified_utc': last_file_dt}


def main():
    global UPLOAD_DIR, THRESHOLD, EMAIL_TO, EMAIL_BODY, EMAIL_SUBJ, DEBUG, EMAIL_FROM
    modified = _get_last_file_received(UPLOAD_DIR)
    if modified:
        fname = modified['file']
        utc = modified['modified_utc']
        if fname and utc:
            print('Latest file: %s' % fname)
            if utc < datetime.datetime.utcnow() - datetime.timedelta(days=THRESHOLD):
                EMAIL_BODY = EMAIL_BODY.format(last_file_received_name=fname,
                                               last_file_received_date=utc,
                                               threshold=THRESHOLD)
                _send_email(sender=EMAIL_FROM, subject=EMAIL_SUBJ, body=EMAIL_BODY, to=EMAIL_TO)
                print('  ALERT SENT')


if __name__ == '__main__':
    main()