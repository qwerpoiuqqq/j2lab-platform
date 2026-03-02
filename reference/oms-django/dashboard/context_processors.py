def notifications(request):
    if request.user.is_authenticated:
        from dashboard.models import Notification
        unread_qs = Notification.objects.filter(user=request.user, is_read=False)
        unread_notifications = list(unread_qs[:10])
        return {
            'unread_notifications': unread_notifications,
            'unread_count': unread_qs.count(),
        }
    return {}
