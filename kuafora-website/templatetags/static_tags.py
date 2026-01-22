"""
Custom template tags for static file handling
"""
from django import template
from django.templatetags.static import static
from django.contrib.staticfiles.finders import find
import os

register = template.Library()


@register.simple_tag
def static_exists(path):
    """
    Check if a static file exists
    Usage: {% if 'img/logo.png'|static_exists %}...{% endif %}
    """
    try:
        return find(path) is not None
    except:
        return False


@register.filter
def static_exists_filter(path):
    """
    Filter version of static_exists
    """
    try:
        return find(path) is not None
    except:
        return False

