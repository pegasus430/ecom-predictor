#
# A simple log parser for 'web_runner_access' logs
# This is just a draft! Feel free to modify it to make more complete
#

import sys
import re
import datetime
import urllib


def get_date(line):
    dt = re.search(r'\[([0-9]+\/[a-zA-Z]+\/[0-9]+:[0-9\:]+) ', line).group(1)
    return datetime.datetime.strptime(dt, '%d/%b/%Y:%H:%M:%S')


def get_site_name(line):
    return re.search(r'site\=([a-zA-Z_\-]+)', line).group(1)


def get_ip(line):
    return re.search(r'^\d+\.\d+\.\d+\.\d+ \-', line).group(0)\
        .replace('-', '').strip()


def get_searchterms(line):
    s = re.search(r'searchterms_str\=(.+?\&)', line)
    if s:
        s = s.group(1)
    else:
        s = re.search(r'searchterms_str\=(.+)$', line).group(1)
    return urllib.unquote_plus(s.replace('&', '').strip())


def get_group(line):
    g = re.search(r'group_name=([a-zA-Z0-9\+\-_]+?&)', line)
    if g:
        g = g.group(1)
    else:
        g = re.search(r'group_name=([a-zA-Z0-9\+\-_]+?)$', line)
        if g:
            g = g.group(1)
        else:
            g = re.search(r'group_name=([a-zA-Z0-9\+\-_]+?) ', line).group(1)
    return urllib.unquote_plus(g.replace('&', '').strip())


def line_is_crawling_task(line):
    return '/pending/' in line


def parse_line(line):
    line = line.strip()
    if not line_is_crawling_task(line):
        return
    date = get_date(line)
    site_name = get_site_name(line)
    ip = get_ip(line)
    try:
        search_terms = get_searchterms(line)
    except (IndexError, AttributeError):
        search_terms = ''
    try:
        group = get_group(line)
    except (IndexError, AttributeError):
        group = ''
    return locals()


if __name__ == '__main__':
    input_file = sys.argv[1]
    header_saved = False

    requests_by_day = {}

    for line in open(input_file, 'r'):
        line = line.strip()
        line_data = parse_line(line)
        if line_data and 'line' in line_data:
            del line_data['line']
        if line_data:
            #print line
            #print line_data
            if line_data['date'] < datetime.datetime.now() - datetime.timedelta(days=7):
                continue
            """
            if not header_saved:
                for key in line_data.keys():
                    print key + '|',
                header_saved = True
            print
            for _, value in line_data.items():
                print str(value) + '|',
            print
            """
            day = line_data['date'].date()

            if not day in requests_by_day:
                requests_by_day[day] = {}

            if not '_total' in requests_by_day[day]:
                requests_by_day[day]['_total'] = 0
            requests_by_day[day]['_total'] += 1

            if not line_data['site_name'] in requests_by_day[day]:
                requests_by_day[day][line_data['site_name']] = 0
            requests_by_day[day][line_data['site_name']] += 1

            if not line_data['ip'] in requests_by_day[day]:
                requests_by_day[day][line_data['ip']] = 0
            requests_by_day[day][line_data['ip']] += 1


from pprint import pprint
pprint(requests_by_day)