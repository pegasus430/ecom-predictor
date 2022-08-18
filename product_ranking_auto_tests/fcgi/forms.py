import os
from subprocess import check_output
from django import forms
from django.conf import settings


class ReloadFcgiForm(forms.Form):
    method = forms.ChoiceField(
        choices=(('threaded', 'threaded'), ('prefork', 'prefork')),
        initial='threaded'
    )
    pidfile = forms.CharField(
        min_length=4, max_length=50, initial='/tmp/fcgi.pid')
    host = forms.IPAddressField(initial='127.0.0.1')
    port = forms.IntegerField(min_value=1, max_value=10000, initial=8001)
    minspare = forms.IntegerField(min_value=1, max_value=9, initial=4)
    maxspare = forms.IntegerField(min_value=2, max_value=10, initial=5)
    socket = forms.CharField(min_length=4, max_length=50, required=False)
    protocol = forms.ChoiceField(
        choices=(('fcgi', 'fcgi'), ('scgi', 'scgi'), ('ajp', 'ajp')),
        initial='fcgi', required=False
    )
    maxrequests = forms.IntegerField(
        min_value=0, max_value=100000, required=False)
    maxchildren = forms.IntegerField(min_value=1, max_value=10, required=False)

    def reload_fcgi(self):
        options = ' '.join(
            ['%s=%s' % (k, v) for k, v in self.cleaned_data.iteritems() if v]
        )
        manage_py = os.path.join(settings.BASE_DIR, 'manage.py')
        command_name = 'runfcgi'
        python_path = check_output('which python', shell=True).strip()
        cmd = ('kill `cat {pidfile}` && {python_path} {manage_py} '
               '{command_name} {options}').format(
            pidfile=self.cleaned_data['pidfile'], **locals())
        check_output(cmd, shell=True)