"""
Custom template tags for static file handling.
Must live in an installed app (e.g. marketing) so Django discovers them.
"""
from django import template
from django.templatetags.static import static
from django.contrib.staticfiles.finders import find

register = template.Library()


@register.simple_tag
def static_exists_tag(path):
    """
    Check if a static file exists (tag version).
    Usage: {% static_exists_tag 'img/logo.png' %}
    """
    try:
        return find(path) is not None
    except Exception:
        return False


@register.filter(name="static_exists")
def static_exists_filter(path):
    """
    Check if a static file exists (filter version).
    Usage: {% if 'img/logo.png'|static_exists %}...{% endif %}
    """
    try:
        return find(path) is not None
    except Exception:
        return False
