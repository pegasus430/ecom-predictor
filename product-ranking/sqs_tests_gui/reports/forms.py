from django import forms


class ReportDateForm(forms.Form):
    date = forms.DateField(
        widget=forms.TextInput(attrs={'class': 'datepicker'})
    )
