from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta, date
from orders.models import Order
from accounts.models import User
from .models import Notice, Notification
from .forms import NoticeForm


PERIOD_LABELS = {
    'today': '오늘',
    'week': '이번 주',
    'month': '이번 달',
    'custom': '선택 기간',
}


def _parse_period(request):
    """GET 파라미터에서 기간 범위를 파싱"""
    today = timezone.now().date()
    period = request.GET.get('period', 'month')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if date_from and date_to:
        start_date = date.fromisoformat(date_from)
        end_date = date.fromisoformat(date_to)
        period = 'custom'
    elif period == 'today':
        start_date = today
        end_date = today
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    else:
        period = 'month'
        start_date = today.replace(day=1)
        end_date = today

    return start_date, end_date, period, date_from or '', date_to or ''


@login_required
def index(request):
    user = request.user
    today = timezone.now().date()

    if user.is_admin or user.is_accountant:
        return admin_dashboard(request, today)
    elif user.is_manager:
        return manager_dashboard(request, today)
    elif user.is_agency:
        return agency_dashboard(request, today)
    else:
        return redirect('orders:order_grid')


def _common_stats(orders, period_paid):
    """공통 상태별 현황 + 물량 통계 (입금확인 기준)"""
    return {
        'status_submitted': orders.filter(status='submitted').count(),
        'status_paid': orders.filter(status='paid').count(),
        'status_processing': orders.filter(status='processing').count(),
        'status_completed': orders.filter(status='completed').count(),
        'period_items': period_paid.aggregate(s=Sum('total_quantity'))['s'] or 0,
        'total_items': orders.filter(confirmed_at__isnull=False).exclude(status='cancelled').aggregate(s=Sum('total_quantity'))['s'] or 0,
        'notices': Notice.objects.filter(is_active=True)[:5],
    }


def _period_context(request, start_date, end_date, period, date_from, date_to):
    """기간 필터 관련 context"""
    return {
        'current_period': period,
        'period_label': PERIOD_LABELS.get(period, '이번 달'),
        'date_from': date_from,
        'date_to': date_to,
    }


def admin_dashboard(request, today):
    start_date, end_date, period, date_from, date_to = _parse_period(request)

    user = request.user
    all_ids = user.get_all_order_user_ids()
    descendant_ids = user.get_descendant_ids()

    orders = Order.objects.filter(user_id__in=all_ids)
    paid_orders = orders.filter(confirmed_at__isnull=False)
    period_paid = paid_orders.filter(confirmed_at__date__gte=start_date, confirmed_at__date__lte=end_date)

    descendant_users = User.objects.filter(id__in=descendant_ids)

    context = {
        'total_users': descendant_users.count(),
        'total_managers': descendant_users.filter(role='manager').count(),
        'total_agencies': descendant_users.filter(role='agency').count(),
        'total_sellers': descendant_users.filter(role='seller').count(),
        'period_orders': period_paid.count(),
        'period_amount': period_paid.aggregate(s=Sum('total_amount'))['s'] or 0,
        'pending_orders': orders.filter(status='submitted').count(),
        'recent_orders': orders.select_related('user', 'product')[:10],
        **_common_stats(orders, period_paid),
        **_period_context(request, start_date, end_date, period, date_from, date_to),
    }
    return render(request, 'dashboard/admin.html', context)


def manager_dashboard(request, today):
    start_date, end_date, period, date_from, date_to = _parse_period(request)

    user = request.user
    all_ids = user.get_all_order_user_ids()
    agency_count = User.objects.filter(parent=user, role='agency').count()

    orders = Order.objects.filter(user_id__in=all_ids)
    paid_orders = orders.filter(confirmed_at__isnull=False)
    period_paid = paid_orders.filter(confirmed_at__date__gte=start_date, confirmed_at__date__lte=end_date)

    context = {
        'agency_count': agency_count,
        'period_orders': period_paid.count(),
        'period_amount': period_paid.aggregate(s=Sum('total_amount'))['s'] or 0,
        'recent_orders': orders.select_related('user', 'product')[:10],
        **_common_stats(orders, period_paid),
        **_period_context(request, start_date, end_date, period, date_from, date_to),
    }
    return render(request, 'dashboard/manager.html', context)


def agency_dashboard(request, today):
    start_date, end_date, period, date_from, date_to = _parse_period(request)

    user = request.user
    child_ids = list(User.objects.filter(parent=user).values_list('id', flat=True))
    all_ids = child_ids + [user.id]
    orders = Order.objects.filter(user_id__in=all_ids)
    paid_orders = orders.filter(confirmed_at__isnull=False)
    period_paid = paid_orders.filter(confirmed_at__date__gte=start_date, confirmed_at__date__lte=end_date)

    context = {
        'balance': user.balance,
        'seller_count': len(child_ids),
        'period_orders': period_paid.count(),
        'period_amount': period_paid.aggregate(s=Sum('total_amount'))['s'] or 0,
        'recent_orders': orders.select_related('user', 'product')[:10],
        **_common_stats(orders, period_paid),
        **_period_context(request, start_date, end_date, period, date_from, date_to),
    }
    return render(request, 'dashboard/agency.html', context)


def seller_dashboard(request, today):
    start_date, end_date, period, date_from, date_to = _parse_period(request)

    user = request.user
    orders = Order.objects.filter(user=user)
    paid_orders = orders.filter(confirmed_at__isnull=False)
    period_paid = paid_orders.filter(confirmed_at__date__gte=start_date, confirmed_at__date__lte=end_date)

    context = {
        'balance': user.balance,
        'period_orders': period_paid.count(),
        'period_amount': period_paid.aggregate(s=Sum('total_amount'))['s'] or 0,
        'recent_orders': orders.select_related('product')[:10],
        **_common_stats(orders, period_paid),
        **_period_context(request, start_date, end_date, period, date_from, date_to),
    }
    return render(request, 'dashboard/seller.html', context)


@login_required
def deadline_calendar(request):
    """마감일 캘린더 페이지"""
    return render(request, 'dashboard/deadline_calendar.html')


@login_required
def api_deadline_events(request):
    """캘린더에 표시할 마감일 이벤트 JSON API"""
    user = request.user
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')

    orders = Order.objects.select_related('user', 'product').filter(
        deadline__isnull=False,
    ).exclude(status='cancelled')

    if start:
        orders = orders.filter(deadline__gte=start)
    if end:
        orders = orders.filter(deadline__lte=end)

    # 역할별 필터
    if user.is_admin or user.is_accountant or user.is_manager:
        orders = orders.filter(user_id__in=user.get_all_order_user_ids())
    elif user.is_agency:
        child_ids = list(User.objects.filter(parent=user).values_list('id', flat=True))
        orders = orders.filter(user_id__in=child_ids + [user.id])
    elif user.is_seller:
        orders = orders.filter(user=user)

    today = timezone.now().date()
    events = []
    for order in orders:
        company = order.user.company_name or order.user.username
        days_left = (order.deadline - today).days

        # 색상: 만료(빨강), 3일 이내(주황), 7일 이내(노랑), 여유(회색)
        if days_left < 0:
            color = '#ffeef0'
            text_color = '#d1344b'
            suffix = '만료됨'
        elif days_left <= 3:
            color = '#fff4e6'
            text_color = '#c05621'
            suffix = f'D-{days_left}'
        elif days_left <= 7:
            color = '#fefce8'
            text_color = '#a16207'
            suffix = f'D-{days_left}'
        else:
            color = '#f2f4f6'
            text_color = '#4e5968'
            suffix = f'D-{days_left}'

        events.append({
            'id': order.pk,
            'title': f'{company} / {order.total_quantity}타 / {order.product.name} / {order.deadline.strftime("%m.%d")}',
            'start': order.deadline.isoformat(),
            'color': color,
            'textColor': text_color,
            'url': f'/orders/{order.pk}/',
            'extendedProps': {
                'order_number': order.order_number,
                'company': company,
                'product': order.product.name,
                'status': order.get_status_display(),
                'item_count': order.item_count,
                'total_quantity': order.total_quantity,
                'total_amount': int(order.total_amount),
                'days_left': days_left,
                'deadline': order.deadline.isoformat(),
            },
        })

    return JsonResponse(events, safe=False)


# ── 알림 ──

@login_required
@require_POST
def notification_read(request, pk):
    """개별 알림 읽음 처리"""
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    return JsonResponse({'success': True})


@login_required
@require_POST
def notification_read_all(request):
    """전체 알림 읽음 처리"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


# ── 공지사항 ──

@login_required
def notice_list(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    notices = Notice.objects.select_related('created_by').all()
    return render(request, 'dashboard/notice_list.html', {'notices': notices})


@login_required
def notice_create(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = NoticeForm(request.POST)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.created_by = request.user
            notice.save()
            messages.success(request, '공지사항이 등록되었습니다.')
            return redirect('dashboard:notice_list')
    else:
        form = NoticeForm()
    return render(request, 'dashboard/notice_form.html', {'form': form, 'is_edit': False})


@login_required
def notice_edit(request, pk):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    notice = get_object_or_404(Notice, pk=pk)
    if request.method == 'POST':
        form = NoticeForm(request.POST, instance=notice)
        if form.is_valid():
            form.save()
            messages.success(request, '공지사항이 수정되었습니다.')
            return redirect('dashboard:notice_list')
    else:
        form = NoticeForm(instance=notice)
    return render(request, 'dashboard/notice_form.html', {'form': form, 'is_edit': True, 'notice': notice})


@login_required
def notice_delete(request, pk):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    if request.method == 'POST':
        notice = get_object_or_404(Notice, pk=pk)
        notice.delete()
        messages.success(request, '공지사항이 삭제되었습니다.')
    return redirect('dashboard:notice_list')
