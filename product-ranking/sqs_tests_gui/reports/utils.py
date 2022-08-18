import os
import sys
import threading
import copy
import csv
import tempfile
import base64


CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(CWD, '..', '..', 's3_reports'))

from jobs_per_server_per_site import dump_reports


SCRIPT_DIR = REPORTS_DIR = os.path.join(CWD, '..', '..', 's3_reports')
LIST_FILE = os.path.join(CWD, '..', 'gui', 'management', 'commands', "_amazon_listing.txt")


def get_report_fname(date):
    return os.path.join(REPORTS_DIR, 'sqs_jobs_%s.json.txt' % date.strftime('%Y-%m-%d'))


def run_report_generation(date):
    thread = threading.Thread(target=dump_reports, args=(LIST_FILE, date, get_report_fname(date)))
    thread.daemon = True
    thread.run()


def dicts_to_ordered_lists(dikt):
    if isinstance(dikt, (list, tuple)):
        dikt = dikt[0]
    result = copy.copy({})
    for key, value in dikt.items():
        value_list = copy.copy([])
        result[key] = value_list
        for val_key, val_val in value.items():
            result[key].append((val_key, val_val))
        result[key].sort(reverse=True, key=lambda i: i[1])
    return result


def report_to_csv(headers, rows_2_dimensions):
    t_file = tempfile.NamedTemporaryFile(suffix='.csv', delete=False)
    t_file.close()
    os.chmod(t_file.name, 0777)

    with open(t_file.name, 'wb') as fh:
        writer = csv.writer(fh, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
        for row_top, row_top_data in rows_2_dimensions:
            for row_bottom, value in row_top_data:
                writer.writerow([row_top, row_bottom, value])

    return t_file.name


def encrypt(string, key='d*)'):
    encoded_chars = []
    for i in xrange(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(ord(string[i]) + ord(key_c) % 256)
        encoded_chars.append(encoded_c)
    encoded_string = "".join(encoded_chars)
    return base64.urlsafe_b64encode(encoded_string)


def decrypt(string, key='d*)'):
    decoded_chars = []
    string = base64.urlsafe_b64decode(string)
    for i in xrange(len(string)):
        key_c = key[i % len(key)]
        encoded_c = chr(abs(ord(string[i]) - ord(key_c) % 256))
        decoded_chars.append(encoded_c)
    decoded_string = "".join(decoded_chars)
    return decoded_string
