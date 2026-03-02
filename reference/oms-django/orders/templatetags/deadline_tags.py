from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def deadline_dday(deadline_date):
    if not deadline_date:
        return ''
    today = timezone.now().date()
    diff = (deadline_date - today).days

    if diff < 0:
        return mark_safe(
            f'<span class="badge bg-danger">D+{abs(diff)} 만료</span>'
        )
    elif diff == 0:
        return mark_safe(
            '<span class="badge bg-warning text-dark">D-Day</span>'
        )
    elif diff <= 3:
        return mark_safe(
            f'<span class="badge" style="background:#fd7e14">D-{diff}</span>'
        )
    elif diff <= 7:
        return mark_safe(
            f'<span class="badge bg-warning text-dark">D-{diff}</span>'
        )
    else:
        return mark_safe(
            f'<span class="badge bg-primary">D-{diff}</span>'
        )
