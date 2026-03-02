from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import User
from .forms import LoginForm, UserForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard:index')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def user_list(request):
    pass  # admin view - account management only

    if request.user.is_admin or request.user.is_accountant:
        # 경리는 상위 총관리자의 범위를 사용
        scope_user = request.user.parent if request.user.is_accountant and request.user.parent else request.user
        descendant_ids = set(scope_user.get_descendant_ids())

        # 책임자 → 대행사 → 셀러 3단계 트리
        managers = User.objects.filter(role='manager', is_active=True, id__in=descendant_ids).order_by('company_name')
        manager_groups = []
        assigned_agency_ids = set()

        for manager in managers:
            agencies = User.objects.filter(parent=manager, role='agency', is_active=True, id__in=descendant_ids).order_by('company_name')
            assigned_agency_ids.update(agencies.values_list('id', flat=True))

            agency_rows = []
            for agency in agencies:
                sellers = User.objects.filter(parent=agency, role='seller', is_active=True, id__in=descendant_ids).order_by('company_name')
                seller_rows = [{'user': s} for s in sellers]
                agency_rows.append({
                    'agency': agency,
                    'sellers': seller_rows,
                })

            manager_groups.append({
                'manager': manager,
                'agencies': agency_rows,
            })

        # 책임자 소속 없는 대행사 → 셀러 트리 (소속 내에서만)
        independent_agencies = User.objects.filter(
            role='agency', is_active=True, id__in=descendant_ids,
        ).exclude(id__in=assigned_agency_ids).order_by('company_name')
        indie_agency_groups = []
        assigned_seller_ids = set()

        for agency in independent_agencies:
            sellers = User.objects.filter(parent=agency, role='seller', is_active=True, id__in=descendant_ids).order_by('company_name')
            assigned_seller_ids.update(sellers.values_list('id', flat=True))
            seller_rows = [{'user': s} for s in sellers]
            indie_agency_groups.append({
                'agency': agency,
                'sellers': seller_rows,
            })

        # 총관리자 본인 (직속 경리 + 셀러 포함)
        admin_rows = []
        direct_accountants = User.objects.filter(parent=scope_user, role='accountant', is_active=True).order_by('company_name')
        accountant_rows = [{'user': a} for a in direct_accountants]
        direct_sellers = User.objects.filter(parent=scope_user, role='seller', is_active=True).order_by('company_name')
        seller_rows = [{'user': s} for s in direct_sellers]
        admin_seller_ids = set(direct_sellers.values_list('id', flat=True))
        admin_rows.append({
            'user': scope_user,
            'accountants': accountant_rows,
            'sellers': seller_rows,
        })

        # 소속 없는 셀러 (소속 내에서만)
        all_assigned_seller_ids = set()
        for mg in manager_groups:
            for ag in mg['agencies']:
                for sr in ag['sellers']:
                    all_assigned_seller_ids.add(sr['user'].id)
        for ag in indie_agency_groups:
            for sr in ag['sellers']:
                all_assigned_seller_ids.add(sr['user'].id)
        all_assigned_seller_ids.update(assigned_seller_ids)
        all_assigned_seller_ids.update(admin_seller_ids)

        independent_sellers = User.objects.filter(
            role='seller', is_active=True, id__in=descendant_ids,
        ).exclude(id__in=all_assigned_seller_ids).order_by('company_name')
        indie_rows = [{'user': s} for s in independent_sellers]

        return render(request, 'accounts/user_list.html', {
            'admin_rows': admin_rows,
            'manager_groups': manager_groups,
            'groups': indie_agency_groups,
            'indie_sellers': indie_rows,
        })

    elif request.user.is_manager:
        # 책임자: 소속 대행사 → 셀러 트리 (읽기만)
        agencies = User.objects.filter(parent=request.user, role='agency', is_active=True).order_by('company_name')
        groups = []
        for agency in agencies:
            sellers = User.objects.filter(parent=agency, role='seller', is_active=True).order_by('company_name')
            groups.append({
                'agency': agency,
                'sellers': [{'user': s} for s in sellers],
            })
        return render(request, 'accounts/user_list.html', {
            'manager_view_groups': groups,
        })

    elif request.user.is_agency:
        sellers = User.objects.filter(parent=request.user, is_active=True).order_by('company_name')
        return render(request, 'accounts/user_list.html', {
            'sellers': sellers,
        })

    else:
        return redirect('dashboard:index')


@login_required
def user_create(request):
    if not (request.user.is_admin or request.user.is_accountant or request.user.is_manager or request.user.is_agency):
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = UserForm(request.POST, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '사용자가 생성되었습니다.')
            return redirect('accounts:user_list')
    else:
        form = UserForm(request_user=request.user)
    return render(request, 'accounts/user_form.html', {'form': form, 'title': '사용자 생성'})


@login_required
def user_edit(request, pk):
    if not (request.user.is_admin or request.user.is_accountant or request.user.is_manager or request.user.is_agency):
        return redirect('dashboard:index')
    user = get_object_or_404(User, pk=pk)
    if request.user.is_admin or request.user.is_accountant or request.user.is_manager:
        scope_user = request.user.parent if request.user.is_accountant and request.user.parent else request.user
        descendant_ids = scope_user.get_descendant_ids()
        if user.pk not in descendant_ids:
            return redirect('dashboard:index')
    elif request.user.is_agency and user.parent != request.user:
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '사용자 정보가 수정되었습니다.')
            return redirect('accounts:user_list')
    else:
        form = UserForm(instance=user, request_user=request.user)
    return render(request, 'accounts/user_form.html', {'form': form, 'title': '사용자 수정', 'edit_user': user})


@login_required
@require_POST
def user_delete(request, pk):
    if not (request.user.is_admin or request.user.is_accountant or request.user.is_manager or request.user.is_agency):
        return redirect('dashboard:index')
    user = get_object_or_404(User, pk=pk)
    if request.user.is_admin or request.user.is_accountant or request.user.is_manager:
        scope_user = request.user.parent if request.user.is_accountant and request.user.parent else request.user
        descendant_ids = scope_user.get_descendant_ids()
        if user.pk not in descendant_ids:
            return redirect('dashboard:index')
    elif request.user.is_agency and user.parent != request.user:
        return redirect('dashboard:index')
    if user == request.user:
        messages.error(request, '자기 자신은 삭제할 수 없습니다.')
        return redirect('accounts:user_edit', pk=pk)
    if user.children.exists():
        messages.error(request, '하위 계정이 있는 사용자는 삭제할 수 없습니다.')
        return redirect('accounts:user_edit', pk=pk)
    user.delete()
    messages.success(request, '사용자가 삭제되었습니다.')
    return redirect('accounts:user_list')
