from django import template

register = template.Library()

@register.filter
def split_name(value):
    if " " in value:
        names = value.split()
        return {'first_name': names[0], 'last_name': names[-1]}
    else:
        return {'first_name': value, 'last_name': ""}
