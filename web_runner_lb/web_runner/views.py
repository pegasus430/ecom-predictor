from __future__ import division, absolute_import, unicode_literals

import logging
import pyramid.httpexceptions as exc
from pyramid.view import view_config
import re

# Minimum number of seconds responses are considered fresh.
# This will be used liberally so that clients with cache will behave better.
MIN_CACHE_FRESHNESS = 30

# Cache freshness for results.
RESULT_CACHE_FRESHNESS = 3600


LOG = logging.getLogger(__name__)


def command_start_view(request):
    """Redirect a command start througth the Load Balancer."""
    settings = request.registry.settings

    lb = settings.lb
    (resp, lb_server) = _redirect_request(lb, None, request)

    # Associate the jobid and the LB server
    if resp.status_code==301 or resp.status_code==302:
        # store the id
        try:
            re_out = re.search(r'\/pending\/([^\/]+)', resp.headers['Location'])
        except KeyError:
            # If no Location, no id to store
            re_out = None

        if re_out:
            jobid = re_out.group(1)
            lb.set_id(jobid, lb_server)

    return resp


@view_config(route_name='command pending jobs', request_method='GET',
             http_cache=MIN_CACHE_FRESHNESS)
def command_pending(request):
    """Redirect the command to the server that the scraper was executed."""
    settings = request.registry.settings

    lb = settings.lb
    (resp, lb_server) = _redirect_request(lb, r'\/pending\/([^\/]+)', request)

    return resp


@view_config(route_name='command job results', request_method='GET',
             http_cache=RESULT_CACHE_FRESHNESS)
def command_result(request):
    """Report result of job."""
    settings = request.registry.settings

    lb = settings.lb
    (resp, lb_server) = _redirect_request(lb, r'\/result\/([^\/]+)', request)

    return resp


@view_config(route_name='command history', request_method='GET',
             renderer='json', http_cache=MIN_CACHE_FRESHNESS)
def command_history(request):
    """Report command history"""
    settings = request.registry.settings

    lb = settings.lb
    (resp, lb_server) = _redirect_request(lb, r'\/history\/([^\/]+)', request)

    return resp



def spider_start_view(request):
    """Redirect a spider start througth the Load Balancer."""
    settings = request.registry.settings

    lb = settings.lb
    (resp, lb_server) = _redirect_request(lb, None, request)

    # Associate the jobid and the LB server
    if resp.status_code==301 or resp.status_code==302:
        # store the id
        try:
            re_out = re.search(r'\/job\/([^\/]+)', resp.headers['Location'])
        except KeyError:
            # If no Location, no id to store
            re_out = None

        if re_out:
            jobid = re_out.group(1)
            lb.set_id(jobid, lb_server)

    return resp


@view_config(route_name='spider pending jobs', request_method='GET',
             http_cache=MIN_CACHE_FRESHNESS)
def spider_pending_view(request):

    settings = request.registry.settings

    lb = settings.lb
    (resp, lb_server) = _redirect_request(lb, r'\/job\/([^\/]+)', request)

    return resp


@view_config(route_name='spider job results', request_method='GET')
def spider_results_view(request):

    # The process to get the result is exactly the same 
    # than getting 
    resp = spider_pending_view(request)

    # Erase the response 'Connection' header to avoid 
    # hop-by-hop assertion (PEP 3333)
    header_to_erase = [x for x in resp.headers.keys() 
                        if x.lower() == 'connection']
    for erase in header_to_erase:
        del(resp.headers[erase])

    return resp


@view_config(route_name='spider history', request_method='GET',
             renderer='json', http_cache=MIN_CACHE_FRESHNESS)
def spider_history_view(request):
    """Report spider history"""
    resp = spider_pending_view(request)
    return resp
    
 


def _redirect_request(lb, regexp, request):
    '''Redirect a request to the proper LB server

    input parameters:
     0) LBInterface object
     1) regexp: string containing a regular expression to get the LB id
          from the request url. If None is provider, the function will
          ask for a new LB server
     2) request: Pyramid request object

    Output parameters:
     Touple with 2 
    '''

    if regexp:
        # A specific server should be used
        re_out = re.search(regexp, request.url)
        if not re_out:
            # Not valid url.
            LOG.warn("No valid jobid on request %s" % request.url)
            raise exc.HTTPBadRequest("The job ID is invalid.")

        jobid = re_out.group(1)
        lb_server = lb.get_id(jobid)
    else:
        # A new server should be used
        # Get a server from the pool
        lb_server =lb.get_new_server(request)
        if not lb_server:
            # No server available. Raise error.
            LOG.error("No server available in LB for request %s" % request.url)
            raise exc.HTTPBadRequest("No server available on LB.")

    if not lb_server:
        # No server assigned for the operation.
        LOG.error("No server assigned in LB for request %s" % request.url)
        raise exc.HTTPBadRequest("No server assigned on LB.")

    # Redirect the request
    request.server_name = lb_server.host
    if lb_server.port:
        request.server_port = lb_server.port
    LOG.debug("Request redirected to server %s:%s. url=%s" %
      (lb_server.host, lb_server.port, request.url))
    resp = request.get_response()

    return (resp, lb_server)





# vim: set expandtab ts=4 sw=4:
