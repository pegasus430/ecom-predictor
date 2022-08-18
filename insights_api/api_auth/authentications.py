import re

from django.contrib.auth.models import User
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from models import Users


class AccessKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        authenticate_header = request.META.get('HTTP_AUTHORIZATION')
        request.user = None
        print authenticate_header

        if not authenticate_header:
            raise AuthenticationFailed('Authorization header is needed')

        search = re.search('Token (.*)', authenticate_header, re.IGNORECASE)
        if not search:
            raise AuthenticationFailed('From format for Authorization header')

        try:
            user = Users.objects.get(access_key=search.group(1))
            # Associate user with request
            request.session['user_id'] = user.id
            # Return a dummy django auth user for the auth framework
            return (User.objects.get(username='dummy'), None)

        except Users.DoesNotExist:
            raise AuthenticationFailed('The access key is not valid')
