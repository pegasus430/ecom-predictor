#
# Check if there are any warnings, and send emails
#

import os
import sys

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto


# people who should receive this alerts
SEND_TO = ()

# alert thresholds
MIN_TIME = 5  # in seconds
MAX_TIME = 30*60  # in seconds


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..'))
from monitoring import (MONITORING_HOST, SIMMETRICA_CONFIG,
                        return_average_for_last_days)
from settings_ses import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY


def get_working_time_events():
    result = []
    with open(SIMMETRICA_CONFIG, 'r') as fh:
        for line in fh:
            if 'name:' not in line:
                continue
            if 'working_time' not in line:
                continue
            result.append(line.strip().rsplit(' ', 1)[1].strip())
    return result


def send_ses(fromaddr, subject, body, recipient, attachment=None,
             filename=''):
    """Send an email via the Amazon SES service.

    Example:
      send_ses('me@example.com, 'greetings', "Hi!", 'you@example.com)

    Return:
      If 'ErrorResponse' appears in the return message from SES,
      return the message, otherwise return an empty '' string.
    """
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = fromaddr
    msg['To'] = recipient
    msg.attach(MIMEText(body))
    if attachment:
        part = MIMEApplication(attachment)
        part.add_header('Content-Disposition', 'attachment',
                        filename=filename)
        msg.attach(part)
    conn = boto.connect_ses(aws_access_key_id=AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    result = conn.send_raw_email(msg.as_string())
    return result if 'ErrorResponse' in result else ''


def send_email(warning_msg):
    subject = 'Ranking spiders alert'
    body = warning_msg
    for to in SEND_TO:
        send_ses(fromaddr='noreply@'+MONITORING_HOST, subject=subject,
                 body=body, recipient=to.strip())


if __name__ == '__main__':
    events = get_working_time_events()
    for event in events:
        avg_time = return_average_for_last_days(event)
        if avg_time is None:
            continue
        if avg_time < MIN_TIME:
            send_email(event + ' is less than '+str(MIN_TIME)+' seconds')
        if avg_time > MAX_TIME:
            send_email(event + ' is more than '+str(MAX_TIME)+' seconds')