# vim:fileencoding=UTF-8

from __future__ import division, absolute_import, unicode_literals
from future_builtins import *

import logging
import urlparse
import os.path
import time
import thread
import urllib
import urllib2
import bz2
import datetime

import enum
import pyramid.httpexceptions as exc
import requests
import requests.exceptions
import repoze.lru


def is_plain_json_list(fname):
    with open(fname, 'r') as fh:
        cont = fh.read(1024)
    cont = cont.strip()
    if not cont:
        return True  # treat empty files as json lists
    return cont[0] == '{'


def local2utc(string, format='%Y-%m-%d %H:%M:%S.%f'):
    """Convert a string with localtime to UTC"""
    try:
        offset = datetime.datetime.utcnow() - datetime.datetime.now()
        local_datetime = datetime.datetime.strptime(string, format)
        result_utc_datetime = local_datetime + offset
        ret = result_utc_datetime.strftime(format)
    except ValueError:
        ret = None

    return ret



LOG = logging.getLogger(__name__)


def unbzip(f1, f2):
    try:
        f = bz2.BZ2File(f1)
        cont = f.read()
    except:
        return False
    f.close()
    with open(f2, 'wb') as fh:
        fh.write(cont)
    return True


def fix_double_bzip_in_file(fname):
    if not is_plain_json_list(fname):
        result1 = unbzip(fname, fname)
        while result1:
            result1 = unbzip(fname, fname)


class ScrapydJobException(Exception):
    """Base ScrapydMediator exception."""

    def __init__(self, message):
        super(ScrapydJobException, self).__init__()

        self.message = message


class ScrapydJobStartError(ScrapydJobException):
    """The job failed to start."""

    def __init__(self, status, message):
        super(ScrapydJobException, self).__init__(message)

        self.status = status


def _post_params_to_sqs_tests_gui(params):
    url = 'http://52.1.192.8/add-job/'  # TODO: change to hostname
    data = urllib.urlencode(params)
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req, timeout=7)
    _ = response.read()


class ScrapydJobHelper(object):

    SCRAPYD_ITEMS_PATH = 'spider._scrapyd.items_path'

    _VERIFICATION_DELAY = 1

    class JobStatus(enum.Enum):
        unknown = 0
        running = 1
        finished = 2
        pending = 3

    def __init__(self, settings, spider_config, scrapyd):
        if spider_config is None:
            raise exc.HTTPNotFound("Unknown resource.")

        self.scrapyd = scrapyd
        self.scrapyd_items_path = settings[ScrapydJobHelper.SCRAPYD_ITEMS_PATH]

        self.config = spider_config

    def start_job(self, params):
        """Returns the job ID of the started Scrapyd job.

        :param params: Parameters for the job to be started.
        """
        try:
            spider_name = self.config.spider_name.format(**params)
            project_name = self.config.project_name.format(**params)
        except KeyError as e:
            raise ScrapydJobException("Parameter %s is required." % e)

        # Add an appropriate SQS job
        # TODO: removeme after production switches to SQS!
        try:
            _post_params_to_sqs_tests_gui(params)
        except Exception as e:
            LOG.warn(
                "Scrapyd failed to post params. " + str(e))
            pass  # just ignore for now

        return self.scrapyd.schedule_job(project_name, spider_name, params)

    def _report_on_job_without_retry(self, jobid, fresh=False):
        """Returns the status of a job."""
        jobs = self.scrapyd.get_jobs([self.config.project_name], fresh)

        try:
            job = jobs[jobid]

            status = ScrapydJobHelper.JobStatus[job['status']]
        except KeyError:
            if os.path.exists(self.retrieve_job_data_fn(jobid)):
                LOG.warn(
                    "Scrapyd doesn't know the job but the file is present.")
                status = ScrapydJobHelper.JobStatus.finished
            else:
                status = ScrapydJobHelper.JobStatus.unknown

        return status

    def report_on_job(self, jobid, timeout=30, max_retries=2):
        """Returns the status of a job."""
        current_try = 0
        end_time = time.time() + timeout
        status = None
        while True:
            # Ask for a fresh response if it's not the first iteration.
            status = self._report_on_job_without_retry(
                jobid, fresh=current_try != 0)
            if status is ScrapydJobHelper.JobStatus.unknown \
                    and current_try < max_retries \
                    and end_time > time.time():
                LOG.info(
                    "Waiting %gs before retrying to get job status for '%s'."
                    " (%d)",
                    ScrapydJobHelper._VERIFICATION_DELAY,
                    jobid,
                    current_try,
                )
                time.sleep(ScrapydJobHelper._VERIFICATION_DELAY)
            else:
                break

            current_try += 1

        return status

    def retrieve_job_data(self, jobid):
        """Returns a file like object with the job's result."""
        job_output_file = self.retrieve_job_data_fn(jobid)
        fix_double_bzip_in_file(job_output_file)
        try:
            if not is_plain_json_list(job_output_file):
                return bz2.BZ2File(job_output_file)
            else:
                return open(job_output_file)
        except IOError as e:
            msg = "Failed to open data file: %s" % e
            LOG.exception(msg)
            raise ScrapydJobException(msg)

    def retrieve_job_data_fn(self, jobid):
        """Returns the path to the job's data file."""
        path = os.path.normpath(os.path.expanduser(
            self.scrapyd_items_path.format(
                project_name=self.config.project_name,
                spider_name=self.config.spider_name,
            )
        ))
        return os.path.join(path, "%s.jl" % jobid)


class Scrapyd(object):
    """Class to interact with Scrapyd."""

    _CACHE = repoze.lru.ExpiringLRUCache(100, 10)
    _CACHE_LOCK = thread.allocate_lock()

    def __init__(self, url):
        self.scrapyd_url = url

    def _post(self, resource, data):
        url = urlparse.urljoin(self.scrapyd_url, resource)

        try:
            response = requests.post(url, data)
            LOG.debug(
                "POST to scrapyd resource %s got: %s",
                url,
                response.content,
            )

            result = response.json()

            # Check result response is successful.
            if result['status'].lower() != "ok":
                LOG.error("Scrapyd was not OK: %r", result)
                raise exc.HTTPBadGateway(
                    "Scrapyd was not OK, it was '{status}': {message}".format(
                        **result))

            # If the job was created, before returning the cache must be
            # invalidated.
            # There is no need to get _CACHE_LOCK as clearing it does not
            # introduce a race condition.
            self._CACHE.clear()

            return result
        except requests.exceptions.RequestException as e:
            msg = "Error contacting Scrapyd: %s" % e
            LOG.error(msg)
            raise exc.HTTPBadGateway(msg)

    @staticmethod
    def _make_uncached_request(url):
        try:
            response = requests.get(url)
            LOG.debug(
                "Requested from scrapyd resource %s and got: %s",
                url,
                response.content,
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            msg = "Error contacting Scrapyd: %s" % e
            LOG.error(msg)
            raise exc.HTTPBadGateway(msg)

    def _make_request(self, resource, fresh=False, cache_time=None, **query):
        """Makes a request to the configured Scrapyd instance for the resource
        passing the given query string.

        :param resource: The resource to request.
        :type resource: unicode
        :param fresh: Whether to invalidate the cache.
        :type fresh: bool
        :param cache_time: For how many seconds a fresh response would be valid.
        :type cache_time: int
        :param query: The query string parameters.
        :return: The structure from the decoded JSON.
        """
        url = urlparse.urljoin(self.scrapyd_url, resource)
        if query:
            url += '?' + urllib.urlencode(query)

        if fresh:
            LOG.debug("Invalidated cache for %r.", url)
            Scrapyd._CACHE.invalidate(url)
            result = None
        else:
            result = Scrapyd._CACHE.get(url)

        if result is not None:
            LOG.debug("Cache hit for %r.", url)
        else:
            LOG.debug("Cache miss for %r.", url)
            # Will get exclusive access to the cache.
            with Scrapyd._CACHE_LOCK:
                # Before we got access, it may have been populated.
                result = Scrapyd._CACHE.get(url)
                if result is not None:
                    LOG.debug("Cache hit after locking for %r.", url)
                else:
                    result = Scrapyd._make_uncached_request(url)

                    Scrapyd._CACHE.put(url, result, timeout=cache_time)

        # Check result response is successful.
        if result['status'].lower() != "ok":
            LOG.error("Scrapyd was not OK: %r", result)
            raise exc.HTTPBadGateway(
                "Scrapyd was not OK, it was '{status}': {message}".format(
                    **result))

        return result

    def is_alive(self):
        """Returns whether scrapyd is alive."""
        try:
            req = requests.get(self.scrapyd_url)
        except requests.exceptions.RequestException:
            return False

        return req.status_code == 200

    def get_projects(self):
        """Returns a list of Scrapyd projects."""
        projects_data = self._make_request('listprojects.json', cache_time=120)

        return projects_data['projects']

    def get_spiders(self, project):
        assert project, "A project is required."

        spiders_data = self._make_request(
            "listspiders.json", cache_time=120, project=project)

        return spiders_data['spiders']

    def get_jobs(self, projects=None, fresh=False):
        """Return jobs associated to a project.

        The function returns a dictionary whose key is a job's ID and the value
        is a dictionary of Scrapyd's listjobs request structure with the
        addition of the `status` key. For a finished  job, it looks like this:

        {
            "status": "finished",
            "id": "2f16646cfcaf11e1b0090800272a6d06",
            "spider": "spider3",
            "start_time": "2012-09-12 10:14:03.594664",
            "end_time": "2012-09-12 10:24:03.594664"
        }

        :param projects: The list of project to query. If it is None, all
                         projects will be queried.
        :type projects: list
        :param fresh: If cached entries should not be used. This parameter will
                      not cause to fetch fresh projects.
        :type fresh: bool
        :rtype: dict
        """
        if not projects:
            projects = self.get_projects()

        jobs_by_id = {}
        for project in projects:
            jobs_by_status = self._make_request(
                'listjobs.json', fresh, project=project)

            for job_status, jobs in jobs_by_status.items():
                if job_status == "status":
                    continue  # This is not a real status, ironically.

                for job in jobs:
                    # Convert the date from local to UTC
                    if 'start_time' in job:
                        job['start_time'] = local2utc(job['start_time'])
                    if 'end_time' in job:
                        job['end_time'] = local2utc(job['end_time'])

                    job['status'] = job_status

                    job_id = job['id']
                    jobs_by_id[job_id] = job

        return jobs_by_id

    def schedule_job(self, project, spider, params):
        """Schedules a spider and returns its job ID.

        :param project: Project where to find the spider.
        :type project: str
        :param spider: Name of the spider for which to start a job.
        :type spider: str
        :param params: Parameters for the job to be started.
        :type params: dict
        :rtype: str
        """
        # Convert to a list of pairs to handle multivalued parameters.
        data = list(filter(
            lambda (k, _): k not in {'project', 'spider'},
            params.items()
        ))
        data.append(('project', project))
        data.append(('spider', spider))

        result = self._post('schedule.json', data)

        return result['jobid']

    def get_queues(self, projects=None):
        """Returns the scrapyd queue status.

        The function returns a dictionary whose key a project. The value
        is another dictionary with 'running', 'finished' and 'pending' queues.
        Also, there is another key called 'summary', with the total queues.

        :param projects: The list of project to query. If it is None, all
                         projects will be queried.
        :return: A list with the requested queues and the aggregate of the
                 states of all queues.
        :rtype: tuple
        """
        if not projects:
            projects = self.get_projects()

        summary = {'running': 0, 'finished': 0, 'pending': 0}
        queues = {}
        for project in projects:
            jobs_data = self._make_request('listjobs.json', project=project)

            queues[project] = {}
            for status in ('running', 'finished', 'pending'):
                queues[project][status] = len(jobs_data[status])
                summary[status] += len(jobs_data[status])

        return queues, summary

    def get_operational_status(self):
        """Returns a structure with a operational status summary for the
        Scrapyd instance as a dict.
        """
        alive = self.is_alive()
        if not alive:
            operational = False
            projects = None
            spiders = None
            queues = None
            summary_queues = None
        else:
            try:
                operational = True
                projects = self.get_projects()
                spiders = {proj: self.get_spiders(proj) for proj in projects}
                queues, summary_queues = self.get_queues(projects)
            except exc.HTTPError:
                operational = False
                projects = None
                spiders = None
                queues = None
                summary_queues = None

        status = {
            'scrapyd_alive': alive,
            'scrapyd_operational': operational,
            'scrapyd_projects': projects,
            'spiders': spiders,
            'queues': queues,
            'summarized_queue': summary_queues,
        }

        return status


# vim: set expandtab ts=4 sw=4:
