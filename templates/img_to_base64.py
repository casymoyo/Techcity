from django import template
import base64
import requests

register = template.Library()
@register.filter
def to_base64(url):
    return "data:image/png;base64, " + str(base64.b64encode(requests.get(url).content))