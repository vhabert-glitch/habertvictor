from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(form, key):
    """Access a form field by name, returns the BoundField widget."""
    try:
        return form[key]
    except (KeyError, TypeError):
        return ''


@register.filter(name='add')
def add_strings(value, arg):
    """Concatenate two strings."""
    return str(value) + str(arg)
