from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count
import json
from .models import Product, PricePolicy, Category
from .forms import ProductForm, PricePolicyForm, CategoryForm
from accounts.models import User


@login_required
def product_list(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    products = Product.objects.select_related('category').all()
    return render(request, 'products/product_list.html', {'products': products})


@login_required
def product_create(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '상품이 생성되었습니다.')
            return redirect('products:product_list')
    else:
        form = ProductForm()
    return render(request, 'products/product_form.html', {'form': form, 'title': '상품 등록'})


@login_required
def product_edit(request, pk):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, '상품이 수정되었습니다.')
            return redirect('products:product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'products/product_form.html', {'form': form, 'title': '상품 수정'})


@login_required
def price_policy_list(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    policies = PricePolicy.objects.select_related('product', 'user').all()
    return render(request, 'products/price_policy_list.html', {'policies': policies})


@login_required
def price_matrix(request):
    """상품 x 업체 단가 매트릭스"""
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')
    products = Product.objects.filter(is_active=True).select_related('category').order_by('category__display_order', 'name')
    descendant_ids = request.user.get_descendant_ids()
    users = User.objects.filter(role__in=['agency', 'seller'], is_active=True, id__in=descendant_ids).order_by('role', 'company_name')
    policies = {
        (p.product_id, p.user_id): p
        for p in PricePolicy.objects.all()
    }

    matrix = []
    for u in users:
        row = {
            'user': u,
            'prices': []
        }
        for p in products:
            policy = policies.get((p.id, u.id))
            row['prices'].append({
                'product': p,
                'policy': policy,
                'price': int(policy.price) if policy and policy.price is not None else None,
                'reduction_rate': policy.reduction_rate if policy and policy.reduction_rate is not None else None,
            })
        row['configured_count'] = sum(
            1 for item in row['prices']
            if item['price'] is not None or item['reduction_rate'] is not None
        )
        matrix.append(row)

    return render(request, 'products/price_matrix.html', {
        'products': products,
        'categories': categories,
        'matrix': matrix,
    })


@login_required
@require_POST
def api_price_save(request):
    """AJAX로 단가 저장"""
    if not (request.user.is_admin or request.user.is_accountant):
        return JsonResponse({'error': 'forbidden'}, status=403)

    try:
        body = json.loads(request.body)
    except (TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid_json'}, status=400)

    product_id = body.get('product_id')
    user_id = body.get('user_id')
    price = body.get('price')
    reduction_rate = body.get('reduction_rate')

    product = get_object_or_404(Product, pk=product_id)
    user = get_object_or_404(User, pk=user_id)

    price_empty = price is None or price == ''
    rate_empty = reduction_rate is None or reduction_rate == ''

    # 둘 다 비어있으면 PricePolicy 삭제
    if price_empty and rate_empty:
        PricePolicy.objects.filter(product=product, user=user).delete()
        return JsonResponse({'status': 'deleted'})

    # 단가 파싱
    parsed_price = None
    if not price_empty:
        try:
            parsed_price = int(price)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'invalid_price'}, status=400)
        if parsed_price < 0:
            return JsonResponse({'error': 'invalid_price'}, status=400)

    # 감은 비율 파싱
    parsed_rate = None
    if not rate_empty:
        try:
            parsed_rate = int(reduction_rate)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'invalid_reduction_rate'}, status=400)
        if parsed_rate < 0 or parsed_rate > 100:
            return JsonResponse({'error': 'invalid_reduction_rate'}, status=400)

    defaults = {'price': parsed_price, 'reduction_rate': parsed_rate}
    policy, created = PricePolicy.objects.update_or_create(
        product=product, user=user,
        defaults=defaults,
    )
    return JsonResponse({
        'status': 'saved',
        'price': int(policy.price) if policy.price is not None else None,
        'reduction_rate': policy.reduction_rate,
    })


@login_required
def price_policy_create(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = PricePolicyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '단가 정책이 생성되었습니다.')
            return redirect('products:price_policy_list')
    else:
        form = PricePolicyForm()
    return render(request, 'products/price_policy_form.html', {'form': form, 'title': '단가 설정'})


@login_required
def price_policy_edit(request, pk):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    policy = get_object_or_404(PricePolicy, pk=pk)
    if request.method == 'POST':
        form = PricePolicyForm(request.POST, instance=policy)
        if form.is_valid():
            form.save()
            messages.success(request, '단가 정책이 수정되었습니다.')
            return redirect('products:price_policy_list')
    else:
        form = PricePolicyForm(instance=policy)
    return render(request, 'products/price_policy_form.html', {'form': form, 'title': '단가 수정'})


@login_required
def price_policy_delete(request, pk):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    policy = get_object_or_404(PricePolicy, pk=pk)
    if request.method == 'POST':
        policy.delete()
        messages.success(request, '단가 정책이 삭제되었습니다.')
    return redirect('products:price_policy_list')


@login_required
def api_product_schema(request, pk):
    product = get_object_or_404(Product, pk=pk)
    user = request.user
    # 해당 유저별 단가 조회 (admin은 원가, 그 외는 기본단가)
    default_price = product.cost_price if user.is_admin else product.base_price
    try:
        policy = PricePolicy.objects.get(product=product, user=user)
        price = int(policy.price) if policy.price is not None else int(default_price)
    except PricePolicy.DoesNotExist:
        price = int(default_price)
    return JsonResponse({
        'schema': product.schema,
        'price': price,
        'name': product.name,
        'description': product.description or '',
        'min_work_days': product.min_work_days,
        'max_work_days': product.max_work_days,
    })


# 카테고리 관리

@login_required
def category_list(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    categories = Category.objects.annotate(
        product_count=Count('products')
    ).all()
    return render(request, 'products/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '카테고리가 생성되었습니다.')
            return redirect('products:category_list')
    else:
        form = CategoryForm()
    return render(request, 'products/category_form.html', {'form': form, 'title': '카테고리 등록'})


@login_required
def category_edit(request, pk):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, '카테고리가 수정되었습니다.')
            return redirect('products:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'products/category_form.html', {'form': form, 'title': '카테고리 수정'})


@login_required
def category_delete(request, pk):
    if not (request.user.is_admin or request.user.is_accountant):
        return redirect('dashboard:index')
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        category.delete()
        messages.success(request, '카테고리가 삭제되었습니다.')
    return redirect('products:category_list')


@login_required
@require_POST
def category_reorder(request):
    if not (request.user.is_admin or request.user.is_accountant):
        return JsonResponse({'error': 'forbidden'}, status=403)
    try:
        order = json.loads(request.body).get('order', [])
        for i, pk in enumerate(order):
            Category.objects.filter(pk=int(pk)).update(display_order=i)
        return JsonResponse({'ok': True})
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid'}, status=400)


@login_required
def api_category_products(request, pk):
    """카테고리의 활성 상품 목록 JSON 반환"""
    category = get_object_or_404(Category, pk=pk, is_active=True)
    products = category.products.filter(is_active=True).order_by('name')
    data = []
    for p in products:
        # 사용자별 단가 조회 (admin은 원가, 그 외는 기본단가)
        default_price = p.cost_price if request.user.is_admin else p.base_price
        try:
            policy = PricePolicy.objects.get(product=p, user=request.user)
            price = int(policy.price) if policy.price is not None else int(default_price)
        except PricePolicy.DoesNotExist:
            price = int(default_price)
        data.append({
            'id': p.id,
            'name': p.name,
            'description': p.description or '',
            'price': price,
        })
    return JsonResponse({'products': data})

