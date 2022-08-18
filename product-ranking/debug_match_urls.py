#
# Using this, you can compare output of 2 different versions of the same spider.
# It will compare the data for the same URLs, and print out differences.
#

from pprint import pprint
import json
import argparse
import urlparse

import colorama  # pip install colorama


def parse_cmd_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--f1")  # input .JL file 1
    parser.add_argument("--f2")  # input .JL file 2
    # strip_get_args=True OR strip_get_args=1 OR strip_get_args=get_param1,get_param2,session,page
    parser.add_argument(
        "--strip_get_args", default=False, required=False)  # exclude GET args from URL?
    parser.add_argument(
        "--exclude_fields", default=False
    )  # do not compare these fields (separator: comma)
    parser.add_argument(
        "--skip_urls", default=None
    )  # skip URLs containing this substring
    parser.add_argument(
        "--remove_false_values", default=True
    )  # remove fields containing values that are Python's boolean "false"
    parser.add_argument(
        "--exclude_duplicates", default=True
    )
    return parser.parse_args()


def _strip_get_args(url, strip_get_args):
    # 1st case - strip ALL GET params
    if strip_get_args is True or str(strip_get_args) in ('true', 'True', '1'):
        return url.rsplit('?', 1)[0]
    # 2nd case - remove only specified params
    result_url = ''
    parsed = urlparse.urlparse(url)
    params = urlparse.parse_qs(parsed.query)
    result_url += parsed.scheme + '://' + parsed.netloc + parsed.path + '?'
    for param_name in params.keys():
        if param_name in strip_get_args.split(','):
            continue
        for param_value in params[param_name]:
            result_url += '%s=%s&' % (param_name, param_value)
    while result_url.endswith('&'):
        result_url = result_url[0:-1]
    return result_url


def unify_br(br):
    return br.replace("u'", '').replace("'", '').replace(' ', '')


def _parse_exclude_fields_from_arg(arg):
    return [f.strip() for f in arg.split(',')]


def _list_diff(l1, l2):
    result = []
    for _l in l1:
        if not _l in l2:
            result.append(_l)
    if _l in l2:
        if not _l in l1:
            result.append(_l)
    return list(set(result))


def _collect_errors(errors, prefix='', is_first=True):
    results = []
    if isinstance(errors, dict):
        for k, v in errors.iteritems():
            results.extend(_collect_errors(v, '%s - %s' % (prefix, k), False))
    else:  # list
        if not is_first and len(errors) == 2:
            results.append({prefix: errors})
        else:
            for error in errors:
                if isinstance(error, dict):
                    for k, v in error.iteritems():
                        results.extend(_collect_errors(v, '%s - %s' % (prefix, k), False))
                else:  # list
                    results.append({prefix: error})
    return results


def _compare_dicts(d1, d2, exclude_fields, remove_false_values=None):
    results = []
    if not d1 or not d2:
        return results
    if exclude_fields is None:
        exclude_fields = []

    if remove_false_values:
        d1 = {k: v for k, v in d1.items() if v}
        d2 = {k: v for k, v in d2.items() if v}

    if isinstance(d1, list) and isinstance(d2, list):
        len1 = len(d1)
        len2 = len(d2)
        if len1 != len2:
            return {'different length': [len1, len2]}
        t1 = d1[:]
        t2 = d2[:]
        l = len(t1)
        for i in xrange(l-1, -1, -1):
            v1 = t1[i]
            if v1 in t2:
                t2.remove(v1)
                t1.remove(v1)
        if t1 or t2:
            results.append({'Not matching lists': [t1, t2]})

    if isinstance(d1, dict) and isinstance(d2, dict):
        e_f = set(exclude_fields)
        keys1 = set(d1.keys()) - e_f
        keys2 = set(d2.keys()) - e_f
        # check their length (missing fields?)
        if keys1 != keys2:
            return {'field sets': [list(keys1-keys2), list(keys2-keys1)]}
        for k in keys1:
            v1, v2 = d1[k], d2[k]
            if isinstance(v1, (list, dict)) and isinstance(v2, (list, dict)):
                res = _compare_dicts(v1, v2, exclude_fields)
                if res:
                    # if isinstance(res, dict):
                        # results.append(res)
                    # else:
                    results.append({k: res})
            elif v1 != v2:
                results.append({k: [v1, v2]})
    return results


def _get_mismatching_fields(d1, d2, exclude_fields):
    result = []
    if d1.keys() is None or d2.keys() is None:
        return []
    if exclude_fields is None:
        exclude_fields = []
    # check their length (missing fields?)
    keys1 = set([key for key in d1.keys() if not key in exclude_fields])
    keys2 = set([key for key in d2.keys() if not key in exclude_fields])
    if len(keys1) != len(keys2):
        return 'length: %s' % [
            f for f in list(keys1)+list(keys2)
            if f not in keys1 or f not in keys2
        ]
    if keys1 != keys2:
        return 'field_names: ' + str(_list_diff(keys1, keys2))
    # now compare values
    for k1, v1 in [(key,value) for key,value in d1.items()
                   if not key in exclude_fields]:
        v2 = d2[k1]
        if k1 == 'buyer_reviews':
            v1 = unify_br(str(v1))
            v2 = unify_br(str(v2))
        if v1 != v2:
            result.append({k1: [v1, v2]})
    return result


def print_human_friendly(
        results, exclude_fields, indent=4,
        heading_color=colorama.Fore.RED,
        basic_color=colorama.Fore.GREEN
):
    if isinstance(results, dict):
        for k, v in results.iteritems():
            if k in exclude_fields:
                continue
            print ' '*indent, heading_color, k, basic_color
            print ' '*indent*2, colorama.Fore.YELLOW, '1.', basic_color,  v[0]
            print ' '*indent*2, colorama.Fore.YELLOW, '2.', basic_color,  v[1]
            print
    else:
        for element in results:
            if isinstance(element, dict):
                field, vals = element.items()[0]
                if field in exclude_fields:
                    continue
            else:  # string error code?
                field = 'Field sets are different!'
                vals = [field, ''] if isinstance(results, (list, tuple))\
                    else [results, '']
            print ' '*indent, heading_color, field, basic_color
            try:
                print ' '*indent*2, colorama.Fore.YELLOW, '1.', basic_color,  vals[0]
            except KeyError:
                print vals
            if len(vals) > 1:
                print ' '*indent*2, colorama.Fore.YELLOW, '2.', basic_color, vals[1]
            print


def collect_human_friendly(results, exclude_fields):
    output = []
    if exclude_fields is None:
        exclude_fields = []
    for element in results:
        if isinstance(element, dict):
            field, vals = element.items()[0]
            if field in exclude_fields:
                continue
        else:  # string error code?
            field = 'Field sets are different!'
            vals = [field, ''] if isinstance(results, (list, tuple))\
                else [results, '']
        #print ' '*indent, heading_color, field, basic_color
        output.append({
            'field': field,
            'f1': vals[0] if isinstance(vals, (list, tuple)) else vals,
            'f2': vals[1] if len(vals) > 1 else ''
        })
    return output


def _start_print():
    colorama.init()
    print colorama.Back.BLACK


def _finish_print():
    print colorama.Back.RESET


def _filter_duplicates(array):
    """ Completely removes products with duplicated urls
        (no single occurence remains) """
    result = []
    urls_count = {}
    # first pass - map urls
    for a in array:
        url = a.get('url', None)
        if not url in urls_count:
            urls_count[url] = 0
        urls_count[url] += 1
    # second pass - filter products out
    for a in array:
        url = a.get('url', None)
        if urls_count[url] > 1:
            continue
        result.append(a)
    return result


def match(f1, f2, fields2exclude=None, strip_get_args=None,
          skip_urls=None, remove_false_values=True,
          exclude_duplicates=False, print_output=True):
    total_urls = 0
    matched_urls = 0

    if print_output:
        _start_print()

    f1 = open(f1).readlines()
    f2 = open(f2).readlines()

    try:
        f1 = [json.loads(l.strip()) for l in f1 if l.strip()]
        f2 = [json.loads(l.strip()) for l in f2 if l.strip()]
    except ValueError:
        return {'diff': [], 'total_urls': 0, 'matched_urls': 0}

    if exclude_duplicates:
        f1 = _filter_duplicates(f1)
        f2 = _filter_duplicates(f2)

    result_mismatched = []

    for i, json1 in enumerate(f1):
        if not 'url' in json1:
            continue
        url1 = json1['url']
        if strip_get_args:
            url1 = _strip_get_args(url1, strip_get_args)

        total_urls += 1

        if skip_urls:
            if skip_urls in url1:
                continue

        for json2 in f2:
            if not json2:
                continue
            if not 'url' in json2.keys():
                continue
            url2 = json2['url']
            if strip_get_args:
                url2 = _strip_get_args(url2, strip_get_args)

            if url1 == url2:
                matched_urls += 1
                # mis_fields = _get_mismatching_fields(json1, json2,
                #                                      fields2exclude)
                mis_fields = _compare_dicts(
                    json1, json2, fields2exclude, remove_false_values)
                mis_fields = _collect_errors(mis_fields)
                if mis_fields:
                    if print_output:
                        print 'LINE', i
                        print 'URL', json1['url']
                        print colorama.Fore.GREEN
                        print_human_friendly(mis_fields, fields2exclude)
                        print colorama.Fore.RESET
                    else:
                        result_mismatched.append({
                            'line': i,
                            'diff': collect_human_friendly(mis_fields, fields2exclude),
                            'data1': json1,
                            'data2': json2,
                            'url': json1['url']
                        })

    if print_output:
        print 'TOTAL URLS:', total_urls
        print 'MATCHED URLS:', matched_urls

    if print_output:
        _finish_print()

    return {'diff': result_mismatched, 'total_urls': total_urls,
            'matched_urls': matched_urls}


if __name__ == '__main__':
    args = parse_cmd_args()
    fields2exclude = _parse_exclude_fields_from_arg(
        args.exclude_fields if args.exclude_fields else '')
    result = match(
        f1=args.f1, f2=args.f2,
        fields2exclude=fields2exclude,
        strip_get_args=args.strip_get_args,
        skip_urls=args.skip_urls,
        remove_false_values=not args.remove_false_values in ('0', 'false', 'False'),
        exclude_duplicates=True, print_output=True
    )
