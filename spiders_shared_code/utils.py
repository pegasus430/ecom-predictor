import json
import re
import time
import traceback

import boto


def get_raw_settings(retries=3, key_name="cache.json"):
    for attempt in range(retries):
        try:
            conn = boto.connect_s3()
            bucket = conn.get_bucket('settings.contentanalyticsinc.com')
            key = bucket.get_key(key_name)
            return json.loads(key.get_contents_as_string())
        except:
            # XXX CH has no logger and SC catchs stdout/err
            print 'Attempt: {}\n{}'\
                .format(attempt, traceback.format_exc())
            time.sleep(attempt * 2)  # Holdback 2 4 6


def compile_settings(raw_settings, domain=None):
    if raw_settings is None:
        return

    if domain is None:
        return

    settings = {}
    for key, data in reversed(raw_settings):
        if re.match(key, domain):
            settings = merge_dict(settings, data)
    return settings


def merge_dict(dict1, dict2):
    output = dict(dict1)
    for key, value in dict2.iteritems():
        if key in dict1:
            if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                output[key] = merge_dict(dict1[key], dict2[key])
                continue
        output[key] = value
    return output


def deep_search(needle, haystack):
    found = []

    if isinstance(haystack, dict):
        if needle in haystack.keys():
            found.append(haystack[needle])

        elif len(haystack.keys()) > 0:
            for key in haystack.keys():
                result = deep_search(needle, haystack[key])
                found.extend(result)

    elif isinstance(haystack, list):
        for node in haystack:
            result = deep_search(needle, node)
            found.extend(result)

    return found
