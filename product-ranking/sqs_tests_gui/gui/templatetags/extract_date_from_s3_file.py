import re

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def extract_date_from_s3_file(context, fname):
    match = re.search(r'\/(\d{4}\-\d{1,2}\-\d{1,2})\/', fname)
    if match:
        return match.group(1)