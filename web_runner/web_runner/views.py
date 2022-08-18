from __future__ import division, absolute_import, unicode_literals

from itertools import repeat, starmap
import datetime
import logging
import numbers

import pyramid.httpexceptions as exc
from pyramid.view import view_config
import subprocess32 as subprocess

from web_runner.config_util import find_command_config_from_name, \
    find_command_config_from_path, find_spider_config_from_path, SpiderConfig, \
    render_spider_config
from web_runner.scrapyd import ScrapydJobHelper, Scrapyd, \
    ScrapydJobStartError, ScrapydJobException
from web_runner.util import encode_ids, decode_ids, get_request_status, \
    string2datetime, dict_filter
import web_runner.db

# Minimum number of seconds responses are considered fresh.
# This will be used liberally so that clients with cache will behave better.
MIN_CACHE_FRESHNESS = 30

# Cache freshness for results.
RESULT_CACHE_FRESHNESS = 3600

SCRAPYD_BASE_URL_KEY = 'spider._scrapyd.base_url'


LOG = logging.getLogger(__name__)


FINISH = web_runner.util.FINISH
UNAVAILABLE = web_runner.util.UNAVAILABLE
RUNNING = web_runner.util.RUNNING
PENDING = web_runner.util.PENDING


# TODO Move command handling logic to a CommandMediator.


def command_start_view(request):
    """Schedules running a command plus spiders."""
    settings = request.registry.settings
    cfg_template = find_command_config_from_path(settings, request.path)

    spider_cfgs = starmap(
        render_spider_config,
        zip(
            cfg_template.spider_configs,
            cfg_template.spider_params,
            repeat(request.params),
        )
    )

    scrapyd = Scrapyd(settings[SCRAPYD_BASE_URL_KEY])

    spider_job_ids = []
    try:
        for spider_cfg, spider_params in zip(
                spider_cfgs, cfg_template.spider_params):
            all_params = dict(spider_params)
            all_params.update(request.params)

            jobid = ScrapydJobHelper(settings, spider_cfg, scrapyd).start_job(
                all_params)
            spider_job_ids.append(jobid)
            LOG.info(
                "For command at '%s', started crawl job with id '%s'.",
                cfg_template.name,
                jobid,
            )
    except ScrapydJobStartError as e:
        raise exc.HTTPBadGateway(
            "Failed to start a required crawl for command '{}'."
            " Scrapyd was not OK, it was '{}': {}".format(
                cfg_template.name, e.status, e.message)
        )
    except ScrapydJobException as e:
        raise exc.HTTPBadGateway(
            "For command {}, unexpected error when contacting Scrapyd:"
            " {}".format(cfg_template.name, e.message)
        )

    command_name = request.path.strip('/')
    id = request.route_path(
        "command pending jobs",
        name=cfg_template.name,
        jobid=encode_ids(spider_job_ids),
        _query=request.params,
    )

    # Storing the request in the internal DB
    dbinterf = web_runner.db.DbInterface(
        settings['db_filename'], recreate=False)
    dbinterf.new_command(
        command_name,
        dict(request.params),
        spider_job_ids,
        request.remote_addr,
        id=id,
    )
    dbinterf.close()

    raise exc.HTTPFound(
        location=id,
        detail="Command '{}' started with {} crawls.".format(
            cfg_template.name, len(spider_job_ids))
    )


@view_config(route_name='command pending jobs', request_method='GET',
             http_cache=MIN_CACHE_FRESHNESS)
def command_pending(request):
    """Report on running job status."""
    name = request.matchdict['name']
    encoded_job_ids = request.matchdict['jobid']
    try:
        job_ids = decode_ids(encoded_job_ids)
    except TypeError:
        # Malformed Job ID.
        raise exc.HTTPBadRequest("The job ID is invalid.")

    settings = request.registry.settings
    cfg_template = find_command_config_from_name(settings, name)

    spider_cfgs = starmap(
        render_spider_config,
        zip(
            cfg_template.spider_configs,
            cfg_template.spider_params,
            repeat(request.params),
        )
    )

    scrapyd = Scrapyd(settings[SCRAPYD_BASE_URL_KEY])

    running = 0
    for job_id, spider_cfg in zip(job_ids, spider_cfgs):
        scrapyd_helper = ScrapydJobHelper(settings, spider_cfg, scrapyd)
        status = scrapyd_helper.report_on_job(job_id)
        if status is ScrapydJobHelper.JobStatus.unknown:
            msg = "Job for spider '{}' with id '{}' has an unknown status." \
                " Aborting command run.".format(spider_cfg.spider_name, job_id)
            LOG.error(msg)
            raise exc.HTTPNotFound(msg)

        if status is not ScrapydJobHelper.JobStatus.finished:
            running += 1

    # Storing the request in the internal DB
    dbinterf = web_runner.db.DbInterface(
        settings['db_filename'], recreate=False)
    dbinterf.new_request_event(
        web_runner.db.COMMAND_STATUS, job_ids, request.remote_addr)
    dbinterf.close()

    if running:
        raise exc.HTTPAccepted(detail="Crawlers still running: %d" % running)
    else:
        raise exc.HTTPFound(
            location=request.route_path(
                "command job results",
                name=name,
                jobid=encoded_job_ids,
                _query=request.params,
            ),
            detail="Crawlers finished.")


@view_config(route_name='command job results', request_method='GET',
             http_cache=RESULT_CACHE_FRESHNESS)
def command_result(request):
    """Report result of job."""
    name = request.matchdict['name']
    encoded_job_ids = request.matchdict['jobid']
    try:
        job_ids = decode_ids(encoded_job_ids)
    except TypeError:
        # Malformed Job ID.
        raise exc.HTTPBadRequest("The job ID is invalid.")

    settings = request.registry.settings
    cfg_template = find_command_config_from_name(settings, name)

    spider_cfgs = starmap(
        render_spider_config,
        zip(
            cfg_template.spider_configs,
            cfg_template.spider_params,
            repeat(request.params),
        )
    )

    # Storing the request in the internal DB
    dbinterf = web_runner.db.DbInterface(
        settings['db_filename'], recreate=False)
    dbinterf.new_request_event(
        web_runner.db.COMMAND_RESULT, job_ids, request.remote_addr)
    dbinterf.close()

    scrapyd = Scrapyd(settings[SCRAPYD_BASE_URL_KEY])

    args = dict(request.params)
    for i, (job_id, spider_cfg) in enumerate(zip(job_ids, spider_cfgs)):
        fn = ScrapydJobHelper(
            settings, spider_cfg, scrapyd).retrieve_job_data_fn(job_id)
        args['spider %d' % i] = fn

    cmd_line = cfg_template.cmd.format(**args)
    LOG.info("Starting command: %s", cmd_line)
    process = subprocess.Popen(
        cmd_line,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )

    LOG.info("Waiting until conn timeout for command to finish...")
    stdout, stderr = process.communicate()
    LOG.info("Process finished.")

    if process.returncode != 0:
        msg = "The command terminated with an return value of %s." \
              " Process' standard error: %s" \
              % (process.returncode, stderr)
        LOG.warn(msg)
        raise exc.HTTPBadGateway(detail=msg)

    LOG.info("Command generated %s bytes.", len(stdout))
    request.response.content_type = cfg_template.content_type
    request.response.body = stdout
    return request.response


@view_config(route_name='command history', request_method='GET',
             renderer='json', http_cache=MIN_CACHE_FRESHNESS)
def command_history(request):
    """Report command history"""

    return _history_by_jobid(request, "command")


def spider_start_view(request):
    """Starts job in Scrapyd and redirects to the "spider pending jobs" view."""
    settings = request.registry.settings

    cfg_template = find_spider_config_from_path(settings, request.path)
    cfg = render_spider_config(cfg_template, request.params)

    scrapyd = Scrapyd(settings[SCRAPYD_BASE_URL_KEY])
    try:
        jobid = ScrapydJobHelper(settings, cfg, scrapyd).start_job(
            request.params)
        id = request.route_path("spider pending jobs", 
                                project=cfg.project_name,
                                spider=cfg.spider_name, jobid=jobid)

        # Storing the request in the internal DB.
        dbinterf = web_runner.db.DbInterface(
            settings['db_filename'], recreate=False)
        dbinterf.new_spider(
            cfg.spider_name,
            dict(request.params),
            jobid,
            request.remote_addr,
            id
        )
        dbinterf.close()

        raise exc.HTTPFound(
            location=id,
            detail="Job '%s' started." % jobid)
    except ScrapydJobStartError as e:
        raise exc.HTTPBadGateway(
            "Scrapyd error when starting job. Status '{}': {}".format(
                e.status, e.message))
    except ScrapydJobException as e:
        raise exc.HTTPBadGateway(
            "When contacting Scrapyd there was an unexpected error: {}".format(
                e.message))


@view_config(route_name='spider pending jobs', request_method='GET',
             http_cache=MIN_CACHE_FRESHNESS)
def spider_pending_view(request):
    project_name = request.matchdict['project']
    spider_name = request.matchdict['spider']
    job_id = request.matchdict['jobid']

    settings = request.registry.settings

    scrapyd = Scrapyd(settings[SCRAPYD_BASE_URL_KEY])
    status = ScrapydJobHelper(
        settings, SpiderConfig(spider_name, project_name), scrapyd
    ).report_on_job(job_id)

    # Storing the request in the internal DB
    dbinterf = web_runner.db.DbInterface(
        settings['db_filename'], recreate=False)
    dbinterf.new_request_event(
        web_runner.db.SPIDER_STATUS, (job_id,), request.remote_addr)
    dbinterf.close()

    if status is ScrapydJobHelper.JobStatus.finished:
        raise exc.HTTPFound(
            location=request.route_path(
                "spider job results",
                project=project_name,
                spider=spider_name,
                jobid=job_id,
            ),
            detail="Job finished.")

    if status is ScrapydJobHelper.JobStatus.unknown:
        msg = "Job for spider '{}/{}' with id '{}' has an unknown status." \
            " Aborting command run.".format(project_name, spider_name, job_id)
        LOG.error(msg)
        raise exc.HTTPNotFound(msg)

    state = 'Job state unknown.'
    if status is ScrapydJobHelper.JobStatus.pending:
        state = "Job still waiting to run"
    elif status is ScrapydJobHelper.JobStatus.running:
        state = "Job running."
    raise exc.HTTPAccepted(detail=state)


@view_config(route_name='spider job results', request_method='GET',
             http_cache=RESULT_CACHE_FRESHNESS)
def spider_results_view(request):
    settings = request.registry.settings

    project_name = request.matchdict['project']
    spider_name = request.matchdict['spider']
    job_id = request.matchdict['jobid']

    # Storing the request in the internal DB
    dbinterf = web_runner.db.DbInterface(
        settings['db_filename'], recreate=False)
    dbinterf.new_request_event(
        web_runner.db.SPIDER_RESULT,  (job_id,), request.remote_addr)
    dbinterf.close()

    scrapyd = Scrapyd(settings[SCRAPYD_BASE_URL_KEY])
    try:
        data_stream = ScrapydJobHelper(
            settings, SpiderConfig(spider_name, project_name), scrapyd
        ).retrieve_job_data(job_id)
        request.response.body_file = data_stream
        return request.response
    except ScrapydJobException as e:
        raise exc.HTTPBadGateway(
            detail="The content could not be retrieved: %s" % e)


@view_config(route_name='spider history', request_method='GET',
             renderer='json', http_cache=MIN_CACHE_FRESHNESS)
def spider_history_view(request):
    """Report spider history"""
    
    return _history_by_jobid(request, 'spider')
 

@view_config(route_name='status', request_method='GET', renderer='json',
             http_cache=MIN_CACHE_FRESHNESS)
def status(request):
    """Check the Web Runner and Scrapyd Status"""

    settings = request.registry.settings

    scrapyd_baseurl = settings[SCRAPYD_BASE_URL_KEY]
    scrapyd_interf = Scrapyd(scrapyd_baseurl)

    output = scrapyd_interf.get_operational_status()

    if request.params:
        items = [x.split(':', 1) for x in request.params.getall('return')]
        output = dict_filter(output, items)

        if 'application/json' in request.accept:
            pass
        elif 'text/plain' in request.accept:
            request.override_renderer = 'string'
            if len(output) != 1:
                raise exc.exception_response(406)
            else:
                output = output.values()[0]
                if not isinstance(output, numbers.Number) \
                        and type(output) != type('a'):
                    raise exc.exception_response(406)
                
        else:
            raise exc.exception_response(406)

    return output


@view_config(route_name='last request status', request_method='GET',
             renderer='json', http_cache=MIN_CACHE_FRESHNESS)
def last_request_status(request):
    """Returns the last requests requested.

    The request accepts an optional parameter size, which is the maximum number
    of items returned.
    """ 
    settings = request.registry.settings

    default_size = 10
    size_str = request.params.get('size', default_size)
    try:
        size = int(size_str)
    except ValueError:
        raise exc.HTTPBadGateway(detail="Size parameter has incorrect value")

    # Get last requests
    dbinterf = web_runner.db.DbInterface(
        settings['db_filename'], recreate=False)
    reqs = dbinterf.get_last_requests(size)
    dbinterf.close()

    # Get the jobid status dictionary.
    scrapyd_baseurl = settings[SCRAPYD_BASE_URL_KEY]
    scrapyd_interf = Scrapyd(scrapyd_baseurl)
    jobids_status = scrapyd_interf.get_jobs()
    
    # For each request, determine the request status gathering 
    # the information from all jobids related to it
    for req in reqs:
        req['status'] = get_request_status(req, jobids_status)

    return reqs


@view_config(route_name='request history', request_method='GET',
             renderer='json', http_cache=MIN_CACHE_FRESHNESS)
def request_history(request):
    """Returns the history of a request

    The view expects to receive a requestid.
    The view returns a dictionary with the following keys:
     * request: dictionary with main request infomation stored in the DB
     * jobids_info: dictionary whose key are all jobids related to
        requestid. The values is a dictionary with jobid information.
     * history: List with history content.
     * status: String with the requestid status

    Example of request:
        {'creation': u'2014-07-30 19:38:53.659982', 
         'params': u'{"searchterms_str": "laundry detergent", "group_name": "Gabo test1", "site": "walmart", "quantity": "100"}', 
         'requestid': 252, 
         'jobids': (u'236c257c182111e4906150465d4bc079',), 
         'remote_ip': u'127.0.0.1', 
         'group_name': u'Gabo test1', 
         'type': u'command', 
         'site': u'walmart', 
         'name': u'cat1'}

    Example of jobids_info:
        {u'17ae4f1c182111e4906150465d4bc079': {
            'spider': u'walmart_products', 
            'status': 'finished', 
            'start_time': u'2014-07-30 16:38:34.218200', 
            'end_time': u'2014-07-30 16:40:50.766396', 
            'id': u'17ae4f1c182111e4906150465d4bc079'}, 
         u'236c257c182111e4906150465d4bc079': {
            'spider': u'walmart_products', 
            'status': 'finished', 
            'start_time': '2014-07-30 16:38:54.116999', 
            'end_time': u'2014-07-30 16:41:06.851201', 
            'id': u'236c257c182111e4906150465d4bc079'}}

    Exanmple of history:
        [["2014-07-30 21:13:02.829964", "1 hour", "Request arrived from 127.0.0.1."],
        ["2014-07-30 21:16:02.829964", "1 hour", "Request Finished"]]
    """
    settings = request.registry.settings

    try:
        requestid = int(request.matchdict['requestid'])
    except ValueError:
        raise exc.HTTPBadGateway(detail="Request id is not valid")

    # Get request info
    dbinterf = web_runner.db.DbInterface(
        settings['db_filename'], recreate=False)
    request_info = dbinterf.get_request(requestid)
    operations_info = dbinterf.get_req_operations(requestid)
    dbinterf.close()

    if not request_info:
        # The requestid is not recognized
        raise exc.HTTPBadGateway(detail="No info from Request id")

    # Get the jobid status dictionary.
    scrapyd_baseurl = settings[SCRAPYD_BASE_URL_KEY]
    scrapyd_interf = Scrapyd(scrapyd_baseurl)
    jobids_status = scrapyd_interf.get_jobs()

    try:
        # Get only the jobids of the current request.
        jobids_info = {jobid: jobids_status[jobid]
                       for jobid in request_info['jobids']}
    except KeyError:
        jobids_info = None

    if jobids_info:
        history = _get_history(requestid, request_info, jobids_info, 
                               operations_info)
        status = get_request_status(request_info, jobids_status)
    else:
        history = None
        status = UNAVAILABLE

    info = {
        'request': request_info,
        'jobids_info': jobids_info,
        'history': history,
        'status': status,
    }
    return info


# FIXME Move this logic to a Repository in the model.
def _get_history(requestid, request_info, jobids_info, operations_info):
    """Build the history of a request

    Given a requestid, a dictionary with request information,
    a dictionary with the jobids status and a list of operations
    done over the request, _get_history builds
    a generator of history structure.
    history structure is a tuple of 3 possition:
     * 1st is the date
     * 2nd is the elapsed time sinse now
     * 3rd: a description
    """
    class Log:
        def __init__(self):
            self.date = None
            self.delta = None
            self.comment = None

        def __repr__(self):
            now = datetime.datetime.utcnow()
            self.delta = now - self.date
            # Erase the microseconds
            self.delta -= datetime.timedelta(
                microseconds=self.delta.microseconds)
            return [str(self.date), str(self.delta), self.comment]

        def setDate(self, dateStr):
            self.date = string2datetime(dateStr)

    history = []
    # Insert starting log
    creation = Log()
    creation.setDate(request_info['creation'])
    creation.comment = 'Request arrived from %s.' % request_info['remote_ip']
    history.append(creation)
 
    request_finished = True
    date_last_finished_spider = None
    for jobid in request_info['jobids']:
        status = jobids_info[jobid]['status']
        if status == FINISH:    
            # Note: I'm not able to know when the spider started if it has
            # not finished. Scrapyd does not provide that info.
            # Log when the spider started
            start_log = Log()
            start_log.setDate(jobids_info[jobid]['start_time'])
            start_log.comment = 'Spider %s started. \nid=%s' % \
                (jobids_info[jobid]['spider'], jobid)
            history.append(start_log)

            # Log when spider finished
            finish_log = Log()
            finish_log.setDate(jobids_info[jobid]['end_time'])
            spider_time = finish_log.date - start_log.date
            spider_time -= datetime.timedelta(
                microseconds=spider_time.microseconds)
            finish_log.comment = 'Spider %s finished. Took %s.' % (
                jobids_info[jobid]['spider'], spider_time)
            history.append(finish_log)

            # set what is the date of the last finished spider
            if (date_last_finished_spider is None or
                        date_last_finished_spider < finish_log.date):
                date_last_finished_spider = finish_log.date
        else:
            request_finished = False

    # Add the request finish status
    if request_finished:
        finish = Log()
        finish.date = date_last_finished_spider
        request_time = finish.date - creation.date
        request_time -= datetime.timedelta(
            microseconds=request_time.microseconds)
        finish.comment = 'Request finished. Took %s since created.' \
            % request_time
        history.append(finish)

    # Iterate over the operational information:
    for op in operations_info:
        (date, type, ip) = op
        op_log = Log()
        op_log.setDate(date)
        
        if type.find('status') >= 0:
            op_log.comment = 'Requesting status'
        elif type.find('result') >= 0:
            op_log.comment = 'Requesting results'
        else:
            op_log.comment = type

        if ip:
            op_log.comment += (' from %s.' % ip)
        else:
            op_log.comment += '.'
    
        history.append(op_log)

    # Sort the history by date
    sort_history = sorted(history, key=lambda x: x.date)
    return map((lambda x: x.__repr__()), sort_history)



def _history_by_jobid(request, request_type):
    """Returns the history of a request to be publish

    request_type can be: "spider" or "command"

    The view returns a dictionary with the following keys:
     * history: List with history content.
     * status: String with the requestid status

    Exanmple of history:
        [["2014-07-30 21:13:02.829964", "Request arrived from 127.0.0.1."],
        ["2014-07-30 21:16:02.829964", "Request Finished"]]
    """

    if request_type == 'command':
        name = request.matchdict['name']
        encoded_job_ids = request.matchdict['jobid']
        try:
            job_ids = decode_ids(encoded_job_ids)
        except TypeError:
            # Malformed Job ID.
            raise exc.HTTPBadRequest("The job ID is invalid.")
    elif request_type == 'spider':
        job_ids = (request.matchdict['jobid'],)

    settings = request.registry.settings
    #cfg_template = find_command_config_from_name(settings, name)

    # Get the associated requestId
    dbinterf = web_runner.db.DbInterface(
        settings['db_filename'], recreate=False)
    request_ids = dbinterf.get_requestid(job_ids)
    if len(request_ids) == 0:
        raise exc.HTTPBadRequest("The job ID does not exist.")
    elif len(request_ids) > 1:
        raise exc.HTTPBadRequest("Jobids belong to different request.")

    # Request the internal state history
    request.matchdict['requestid'] = request_ids[0]
    req_history = request_history(request)

    # Create the structure to returns
    ret = {
            'history': map((lambda x: (x[0], x[2])), req_history['history']),
            'status':  req_history['status'],
          }

    return ret

# vim: set expandtab ts=4 sw=4:
