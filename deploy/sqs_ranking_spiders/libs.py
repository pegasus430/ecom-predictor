import codecs
import csv
import json
import os
import json
import datetime

import boto
from boto.s3.key import Key


def convert_json_to_csv(filepath, logger=None):
    """ Receives path to .JL file (without trailing .jl) """
    json_filepath = filepath + '.jl'
    if logger is not None:
        logger.info("Convert %s to .csv", json_filepath)
    field_names = set()
    items = []
    with codecs.open(json_filepath, "r", "utf-8") as jsonfile:
        for line in jsonfile:
            item = json.loads(line.strip())
            items.append(item)
            fields = [name for name, val in item.items()]
            field_names = field_names | set(fields)

    csv.register_dialect(
        'json',
        delimiter=',',
        doublequote=True,
        quoting=csv.QUOTE_ALL)

    csv_filepath = filepath + '.csv'

    with open(csv_filepath, "w") as csv_out_file:
        csv_out_file.write(codecs.BOM_UTF8)
        writer = csv.writer(csv_out_file, 'json')
        writer.writerow(list(field_names))
        for item in items:
            vals = []
            for name in field_names:
                val = item.get(name, '')
                if name == 'description' and val and isinstance(val, basestring):
                    val = val.replace("\n", '\\n')
                if isinstance(val, unicode):
                    val = val.encode('utf-8')
                vals.append(val)
            writer.writerow(vals)
    return csv_filepath


def _get_file_age(fname):
    today = datetime.datetime.now()
    modified_date = datetime.datetime.fromtimestamp(os.path.getmtime(fname))
    return (today - modified_date).total_seconds()


def _download_autoscale_groups(logging=None):
    amazon_bucket_name = "sc-settings"
    config_filename = "autoscale_groups.cfg"
    S3_CONN = boto.connect_s3(is_secure=False)
    S3_BUCKET = S3_CONN.get_bucket(amazon_bucket_name, validate=False)
    k = Key(S3_BUCKET)
    k.key = config_filename
    value = json.loads(k.get_contents_as_string())
    if logging is not None:
        logging.info('Retrieved autoscale groups config: %s' % value)
    return value


def get_autoscale_groups(local_fname='/tmp/_sc_autoscale_groups.cfg', max_age=600, logging=None):
    """ Pass logging var if you want logs """
    if not os.path.exists(local_fname) \
            or (os.path.exists(local_fname) and _get_file_age(local_fname) > max_age):
        # update values
        groups = _download_autoscale_groups(logging=logging)
        with open(local_fname, 'w') as fh:
            fh.write(json.dumps(groups))
        return groups
    else:
        with open(local_fname, 'r') as fh:
            return json.loads(fh.read())