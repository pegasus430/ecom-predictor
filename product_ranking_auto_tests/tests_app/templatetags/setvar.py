from django import template

register = template.Library()

@register.assignment_tag
def setvar(val):
    return val