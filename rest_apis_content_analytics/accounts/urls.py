from django.conf.urls import patterns, url
from django.conf import settings

# Login
from views import UserLogin, UserLogout

urlpatterns = patterns(
    '',
    # Login
    url(r"^login/$", UserLogin, {'template_name': 'login.html'}, name='login'),
    url(r'^logout/$', UserLogout, {'next_page': settings.LOGIN_REDIRECT_URL}, name='logout'),
)