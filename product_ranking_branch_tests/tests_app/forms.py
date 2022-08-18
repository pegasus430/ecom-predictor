from django import forms

from .models import TestRun


class ReadOnlyWidget(forms.widgets.Widget):
    def render(self, _, value, attrs=None):
        return '<b>%s</b>' % value


class TestRunForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(TestRunForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            for field in self.fields.keys():
                self.fields[field].widget = ReadOnlyWidget()

    class Meta:
        model = TestRun
        exclude = ['when_finished', 'status']