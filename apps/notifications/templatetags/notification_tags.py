from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def unread_notifications(context):
    request = context.get("request")
    if not request or not request.user.is_authenticated:
        return 0
    return request.user.notifications.filter(is_read=False).count()
