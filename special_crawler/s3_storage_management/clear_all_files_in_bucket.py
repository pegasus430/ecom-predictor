import sys
import smtplib
from boto.s3.connection import S3Connection
from email.mime.multipart import MIMEMultipart
from email.utils import COMMASPACE, formatdate

queue_names_list = ["dev_scrape",
                    "test_scrape",
                    "demo_scrape",
                    "production_scrape",
                    "unit_test_scrape",
                    "integration_test_scrape",
                    "walmart-fullsite_scrape"]

s3 = S3Connection('AKIAJPOFQWU54DCMDKLQ', '/aebM4IZ97NEwVnfS6Jys6sKVvDXa6eDZsB2X7gP')

queue_name = sys.argv[1]

response_message = ""

if queue_name in queue_names_list:
    bucket = None
    bucket_name = 'contentanalytcis.inc.ch.s3.{0}'.format(queue_name)

    if s3.lookup(bucket_name):
        bucket = s3.get_bucket(bucket_name)
    else:
        bucket = None

    if bucket:
        try:
            rs = bucket.list()
            key_list = [key.name for key in rs]

            deleted_key_count = 0
            bucket_length = len(key_list)

            result = bucket.delete_keys(key_list)

            rs = bucket.list()
            key_list = [key.name for key in rs]

            deleted_key_count = bucket_length - len(key_list)

            print "bucket name: " + bucket_name
            response_message += ("bucket name: " + bucket_name + "\n")
            print "bucket length: " + str(bucket_length)
            response_message += ("bucket length: " + str(bucket_length) + "\n")
            print "deleted key count: " + str(deleted_key_count)
            response_message += ("deleted key count: " + str(deleted_key_count) + "\n")
        except:
            print "Error occurred while working s3."
            response_message = "Error occurred while working s3. It seems there are other processes working in the s3 storage of the queue '" + queue_name + "'"
    else:
        print "There's no bucket named '" + bucket_name + "'."
        response_message = "There's no bucket named '" + bucket_name + "'."
else:
    print "Invalid queue name '" + queue_name + "'."
    response_message = "Invalid queue name '" + queue_name + "'."


subject = "Cleaned content health aws s3 storage for queue '" + queue_name + "'"
fromaddr = "jenkins@contentanalyticsinc.com"
toaddrs = ["support@contentanalyticsinc.com"] # must be a list
msg = """\
From: %s
To: %s
Subject: %s

%s
""" % (fromaddr, ", ".join(toaddrs), subject, response_message)

print "Message length is " + repr(len(msg))

#Change according to your settings
smtp_server = 'email-smtp.us-east-1.amazonaws.com'
smtp_username = 'AKIAI2XV5DZO5VTJ6LXQ'
smtp_password = 'AgWhl58LTqq36BpcFmKPs++24oz6DuS/J1k2GrAmp1T6'
smtp_port = '587'
smtp_do_tls = True

server = smtplib.SMTP(
    host = smtp_server,
    port = smtp_port,
    timeout = 10
)
server.set_debuglevel(10)
server.starttls()
server.ehlo()
server.login(smtp_username, smtp_password)
server.sendmail(fromaddr, toaddrs, msg)
print server.quit()