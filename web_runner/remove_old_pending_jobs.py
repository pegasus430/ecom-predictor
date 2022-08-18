#
# Clears the queue of all the pending tasks. Be careful!
#

# TODO: integrate this code later into web_runner/scrapyd, now it's just a draft written in a hurry

import urllib
import requests
import json
import sys


BASE_HOST = 'http://localhost:6800'


def listprojects():
    cont = urllib.urlopen(BASE_HOST + '/listprojects.json').read()
    print cont
    cont = json.loads(cont)
    return cont['projects']


def listjobs(projects):
    jobs = []
    for p in projects:
        cont = urllib.urlopen(BASE_HOST + '/listjobs.json?project='+p.strip()).read()
        cont = json.loads(cont)
        for key, value in cont.items():
            if isinstance(value, (list, tuple)):
                for _job in value:
                    _job['_status'] = key
                    _job['_project'] = p.strip()
                    jobs.append(_job)
    return jobs


def canceljob(project, _id):
    cont = requests.post(BASE_HOST + '/cancel.json',
                         data={'project': project, 'job': _id}).text
    return json.loads(cont)


if __name__ == '__main__':
    if raw_input('Type YES to cancel all pending jobs: ').strip() != 'YES':
        print 'wrong answer, exit'
        sys.exit()

    projects = listprojects()
    print 'PROJECTS:', projects
    jobs = listjobs(projects)
    #print 'JOBS:', jobs
    for j in jobs:
        if j['_status'] != 'pending':
            continue
        print '    ', j['_status'], '- canceling',
        print canceljob(project=j['_project'], _id=j['id'])