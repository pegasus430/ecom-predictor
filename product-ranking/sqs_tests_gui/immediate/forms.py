from django import forms
from . import find_sites


class SiteChoiceField(forms.ChoiceField):

    def valid_value(self, value):
        return True


class ImmediateForm(forms.Form):
    url = forms.CharField(label='Product URL')
    site = SiteChoiceField(label='Site', required=False, widget=forms.HiddenInput())

    def clean(self):
        site = self.cleaned_data.get('site')

        if not site:
            url = self.cleaned_data.get('url')

            if url:
                sites = find_sites(url)

                if not sites:
                    raise forms.ValidationError('Site was not found for url: {}'.format(url))

                if len(sites) > 1:
                    self.fields['site'].widget = forms.Select()
                    self.fields['site'].choices = [(site, site) for site in sites]

                    raise forms.ValidationError('There are more then one site for url: {}'.format(url))

                self.cleaned_data['site'] = sites[0]
