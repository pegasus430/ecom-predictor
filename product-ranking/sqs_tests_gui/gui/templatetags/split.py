from django import template

register = template.Library()


@register.filter(name='split')
def split(value, arg):
    return value.split(arg)
