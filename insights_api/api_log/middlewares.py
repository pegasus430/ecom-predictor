import re
import time

from models import Query
from api_auth.models import Users


class LogQueryInformation():

    def __init__(self):
        ignore_paths_exp = [r'.*/admin/.*', r'.*/static/.*',
                            r'.*/favicon.ico$']
        self.ignore_paths = [re.compile(x) for x in ignore_paths_exp]

    def is_filter_path(self, path):
        return any(map((lambda x: x.match(path)), self.ignore_paths))

    def process_request(self, request):
        request.session['time'] = time.time()

    def process_response(self, request, response):
        path = request.get_full_path()
        user = None
        user_id = request.session.get('user_id', None)

        start_time = request.session.get('time')
        if start_time:
            run_time = time.time() - start_time
        else:
            run_time = -1

        if user_id:
            del request.session['user_id']
            user = Users.objects.get(pk=user_id)

        if not self.is_filter_path(path):
            data = {'remote_address': request.META['REMOTE_ADDR'],
                    'request_method': request.method,
                    'request_path': path,
                    'request_body': request.body,
                    'response_status': response.status_code,
                    'user': user,
                    'run_time': run_time}
            Query(**data).save()

        return response
