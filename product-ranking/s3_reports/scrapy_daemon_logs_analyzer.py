#
# This script downloads all the scrapy_daemon logs and analyzes them (searches for some occurences)
#

import os
import gzip
import datetime

import boto
from boto.s3.key import Key


CWD = os.path.dirname(os.path.abspath(__file__))


def get_log_key_names(input_file, date):
    result = []

    total_lines_processed = 0
    lines_processed = 0

    date = date.strftime('%d-%m-%Y' + '____')

    if '.gz' in input_file.lower()[-5:]:
        fh = gzip.open(input_file, 'rb')
    else:
        fh = open(input_file, 'r')

    for line in fh:
        total_lines_processed += 1

        if date in line:
            if 'remote_instance_starter2.log' not in line:
                continue

            result.append(line.strip())

            #print line
            lines_processed += 1

    fh.close()

    return result, total_lines_processed, lines_processed


def download():
    bucket_listing = os.path.join(
        CWD, '..', 'sqs_tests_gui', 'gui', 'management', 'commands', '_amazon_listing.txt')

    _date = raw_input(
        'Enter a date you want to analyze logs for [YYYY-MM-DD, default is %s]: ' % datetime.datetime.utcnow().date())
    if not _date:
        _date = datetime.datetime.utcnow().date()
    else:
        _date = datetime.datetime.strptime(_date, '%Y-%m-%d')

    bucket_listing2 = raw_input(
        'Enter the filename where the listing of the bucket is [default %s]: ' % bucket_listing)

    if not bucket_listing2:
        bucket_listing2 = bucket_listing

    if not os.path.exists(bucket_listing2):
        print('Error! The listing file you entered does not exist.')

    output_dir = os.path.join(CWD, '_downloaded_s3_keys')
    output_dir2 = raw_input('Enter dir for downloaded keys [%s]: ' % output_dir)
    if not output_dir2:
        output_dir2 = output_dir

    if not os.path.exists(output_dir2):
        os.makedirs(output_dir2)

    logs, total_lines_processed, lines_processed = get_log_key_names(bucket_listing2, _date)

    print('Found %s files, downloading...' % len(logs))

    connection = boto.connect_s3()
    bucket = connection.get_bucket('spyder-bucket')

    for i, log in enumerate(logs):
        if i % 100 == 0:
            print('  file %s of %s' % (i, len(logs)))
        fname = log.replace('<Key: spyder-bucket,', '').replace('>', '').strip()
        key = Key(bucket)
        key.key = fname
        key.get_contents_to_filename(os.path.join(output_dir2, fname.replace('/', '.')))

    #pprint(report)

    #pprint(transform_report_by_spider(report))


def analyze():
    found_errors = {}

    output_dir = os.path.join(CWD, '_downloaded_s3_keys')
    output_dir2 = raw_input('Enter dir for downloaded keys [%s]: ' % output_dir)
    if not output_dir2:
        output_dir2 = output_dir

    for file in os.listdir(output_dir2):
        with open(os.path.join(output_dir2, file), 'r') as fh:
            for i, line in enumerate(fh):
                if 'error' in line.lower():
                    if file not in found_errors:
                        found_errors[file] = {}
                    found_errors[file]['line'] = i+1
                    found_errors[file]['text'] = line.strip()

    return found_errors


if __name__ == '__main__':
    is_download = raw_input('Download files? y/n: ')
    if is_download.lower().strip() == 'y':
        download()

    is_analyze = raw_input('Analyze errors? y/n: ')
    if is_analyze.lower().strip() == 'y':
        errors = analyze()

        from pprint import pprint
        pprint(errors)
