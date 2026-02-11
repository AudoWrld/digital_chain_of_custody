from django import template
import re

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def replace(value, args):
    """Replace old with new in a string. Usage: {{ value|replace:"old"":"new" }}"""
    if not value or not args:
        return value
    parts = args.split(":")
    if len(parts) != 2:
        return value
    old, new = parts
    return value.replace(old, new)


@register.filter
def slugify_status(value):
    """Convert status to CSS-friendly format"""
    if not value:
        return ""
    return value.lower().replace(" ", "-")
