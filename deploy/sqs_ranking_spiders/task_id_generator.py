import datetime
import random
import string
import json
import os


DATA_FILENAME = 'hash_datestamp_data'

def get_random_hash(length=28):
    return ''.join(
        random.choice(string.ascii_lowercase + string.digits)
        for _ in range(length)
    )

def generate_hash_datestamp_data():
    f = open(DATA_FILENAME, 'w')
    # for job name
    random_hash = get_random_hash()
    # for job name
    datestamp = datetime.datetime.utcnow().strftime('%d-%m-%Y')
    # for amazon S3 path
    folders_path = "/" + datetime.datetime.utcnow().strftime('%Y/%m/%d') + "/"
    data = {
        'random_hash': random_hash,
        'datestamp': datestamp,
        'folders_path': folders_path,
    }
    f.write(json.dumps(data))
    f.close()

def load_data_from_hash_datestamp_data():
    with open(DATA_FILENAME, 'r') as fh:
        json_data = json.loads(fh.read())
        return json_data
