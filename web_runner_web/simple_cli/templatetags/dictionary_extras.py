from django import template

register = template.Library()

@register.filter
def access(value, arg):
    return value[arg]
