from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def split_name(value):
    if " " in value:
        names = value.split()
        return {'first_name': names[0], 'last_name': names[-1]}
    else:
        return {'first_name': value, 'last_name': ""}


@register.filter
@stringfilter
def trim(value):
    return value.strip()
