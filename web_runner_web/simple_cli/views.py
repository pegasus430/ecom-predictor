from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

import requests
import datetime
import json


@login_required
def index(request):
#    return HttpResponse("Here will be the main page")
    return render(request, 'simple_cli/index.html')


@login_required
def web_runner_status(request):
    """Display the status of Web Runner and Scrapyd"""

    try:
        base_url = settings.WEB_RUNNER_BASE_URL
        url = '%sstatus/' % base_url
        req = requests.get(url)
        web_runner_error = False
    except requests.exceptions.RequestException as e:
        web_runner_error = True

    
    error = {"webRunner": False, 
          "scrapyd_operational": "Don't know", 
          "spiders": "Don't know", 
          "scrapyd_projects": None, 
          "scrapyd_alive": "Don't know",
          "queue_status": "Don't know",
        }

    if web_runner_error:
        status = error
    else:
        if req.status_code == 200:
            status = req.json()
            
            # Decide the queue status accordin running, finished and pending 
            # tasks on summary queue
            summary_queue = status['summarized_queue']
            if summary_queue['pending'] > 0 and summary_queue['running'] == 0:
                status['queue_status'] = 'WARNING'
            else:
                status['queue_status'] = 'ok'
        else:
            status = error
    return render(request, 'simple_cli/web_runner_status.html', status)

@login_required
def web_runner_logs(request):
    """Display web runner logs"""

    context = {'logfiles': settings.WEB_RUNNER_LOG_FILES}
    return render(request, 'simple_cli/show_logs.html', context)


@login_required
def web_runner_logs_view(request, logfile_id):
    """Return the log files as files"""
    
    logfiles = settings.WEB_RUNNER_LOG_FILES
    try:
        filename = logfiles[int(logfile_id)]
    except IndexError:
        raise Http404("File does not exists")
        
    try:
        fh = open(filename, 'r')
    except:
        raise Http404("Issues open the log file")

    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    response.write(fh.read())

    return response


@login_required
def web_runner_lastrequests(request, n=None):
    """Display a table with the last n requests"""
 
    try:
        base_url = settings.WEB_RUNNER_BASE_URL
        url = '%slast_requests' % base_url
        if n:
            url += '?size=' + str(n)
        req = requests.get(url)
        error = False
    except requests.exceptions.RequestException as e:
        error = True
        return HttpResponse("There are issues connecting with Web Runner", status=502)

    default_url = False if n else True
    req_info = req.json()

    # decode the details field
    if req_info:
        for req in req_info:
            req['details'] = json.loads(req['details'])
    
    _process_request_to_display(req_info)
    context = {'last_requests': req_info,
      'now': datetime.datetime.utcnow(),
      'default_url': default_url}
    return render(request, 'simple_cli/last_requests.html', context)



@login_required
def web_runner_request_history(request, requestid):
    
    try:
        base_url = settings.WEB_RUNNER_BASE_URL
        url = '%srequest/%s/history/' % (base_url, requestid)
        req = requests.get(url)
        error = False
    except requests.exceptions.RequestException as e:
        error = True
        return HttpResponse("There are issues connecting with Web Runner", status=502)

    if not req.ok:
         return HttpResponse("There are issues getting the history", status=502)

    req_info = req.json()
    _process_history_to_display(req_info['history'])
    #context = {'last_requests': req_info,
    #  'now': datetime.datetime.utcnow()}
    return render(request, 'simple_cli/request_history.html', req_info)



def _process_history_to_display(history):
    """Transform history information to be displayed"""

    if not history:
        return

    for index in range(len(history)):
        try:
            date = datetime.datetime.strptime(history[index][0], 
                                              '%Y-%m-%d %H:%M:%S.%f')
            dateStr = date.strftime('%x %X')
            history[index][0] = dateStr + " (UTC)"
        except ValueError:
            pass

    return



def _process_request_to_display(reqList):
    """Transform an historic request list to be displayed 

    reqList is the output of /last_requests/ REST service
    This methods update the reqList list structure to;
     a) Replace the None objects to empty strings
     b) display the dates with the proper format
    """
    if reqList == None:
        return

    for index, req in enumerate(reqList):
        # Replace the None for empty string
        for key, value in req.items():
            if value==None:
                reqList[index][key] = ' '


        # Print the date in correct format:
        if 'creation' in req:
            try:
                date = datetime.datetime.strptime(req['creation'], '%Y-%m-%d %H:%M:%S.%f')
                dateStr = date.strftime('%x %X')
                reqList[index]['creation'] = dateStr + " (UTC)"
            except ValueError:
                pass

        # Converting params json to dictionary
        if 'params' in req:
            try:
                reqList[index]['params'] = json.loads(req['params'])
            except:
                pass
        
    return




# vim: set expandtab ts=4 sw=2:
