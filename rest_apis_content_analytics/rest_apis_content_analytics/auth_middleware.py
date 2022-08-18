#
# A custom middleware performing cross authentication between Django and Rest Framework
#

import base64

from django.contrib.auth import login, authenticate
from rest_framework import authentication


class AuthMiddleware(object):

    def process_response(self, request, response):
        # try to authenticate the user
        auth = authentication.get_authorization_header(request).split()

        #if not auth or auth[0].lower() != b'basic':
        #    return None

        if len(auth) == 1:
            #msg = _('Invalid basic header. No credentials provided.')
            return response
        elif len(auth) > 2:
            #msg = _('Invalid basic header. Credentials string should not contain spaces.')
            return response

        try:
            auth_parts = base64.b64decode(auth[1]).decode(authentication.HTTP_HEADER_ENCODING).partition(':')
        except (TypeError, UnicodeDecodeError, IndexError):
            # msg = _('Invalid basic header. Credentials not correctly base64 encoded.')
            return response

        userid, password = auth_parts[0], auth_parts[2]

        user_ = authenticate(username=userid, password=password)
        if user_ is not None:
            login(request, user_)

        return response
