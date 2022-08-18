from django import template
from django.conf import settings

register = template.Library()


def is_production():
    is_production = getattr(settings, "IS_PRODUCTION")
    print "is_production %s " % is_production
    return getattr(settings, "IS_PRODUCTION")

register.assignment_tag(is_production)