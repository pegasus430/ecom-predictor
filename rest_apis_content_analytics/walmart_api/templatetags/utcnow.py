from datetime import datetime

from django import template
from django.template.defaultfilters import date


register = template.Library()


@register.simple_tag()
def utcnow(format):
    return date(datetime.utcnow(), format)
