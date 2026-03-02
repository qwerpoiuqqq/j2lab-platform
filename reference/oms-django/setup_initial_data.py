"""초기 데이터 생성 스크립트"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from products.models import Product, PricePolicy
from decimal import Decimal

# 1. 관리자 계정
admin, created = User.objects.get_or_create(
    username='admin',
    defaults={
        'role': 'admin',
        'company_name': '제이투랩',
        'is_staff': True,
        'is_superuser': True,
    }
)
if created:
    admin.set_password('admin1234')
    admin.save()
    print('관리자 계정 생성: admin / admin1234')

# 2. 대행사 계정
agency, created = User.objects.get_or_create(
    username='agency1',
    defaults={
        'role': 'agency',
        'company_name': '테스트 대행사',
        'balance': Decimal('1000000'),
        'parent': admin,
    }
)
if created:
    agency.set_password('test1234')
    agency.save()
    print('대행사 계정 생성: agency1 / test1234 (잔액: 1,000,000원)')

# 3. 셀러 계정
seller, created = User.objects.get_or_create(
    username='seller1',
    defaults={
        'role': 'seller',
        'company_name': '테스트 셀러',
        'balance': Decimal('500000'),
        'parent': agency,
    }
)
if created:
    seller.set_password('test1234')
    seller.save()
    print('셀러 계정 생성: seller1 / test1234 (잔액: 500,000원)')

# 4. 샘플 상품
product1, created = Product.objects.get_or_create(
    code='NAVER_BLOG',
    defaults={
        'name': '네이버 블로그 트래픽',
        'description': '네이버 블로그 방문자 트래픽',
        'base_price': Decimal('100'),
        'schema': [
            {'name': 'url', 'label': '블로그 URL', 'type': 'url', 'required': True},
            {'name': 'keyword', 'label': '검색 키워드', 'type': 'text', 'required': True},
            {'name': 'count', 'label': '방문수', 'type': 'number', 'required': True},
        ],
    }
)
if created:
    print(f'상품 생성: {product1.name}')

product2, created = Product.objects.get_or_create(
    code='INSTA_LIKE',
    defaults={
        'name': '인스타그램 좋아요',
        'description': '인스타그램 게시물 좋아요',
        'base_price': Decimal('50'),
        'schema': [
            {'name': 'url', 'label': '게시물 URL', 'type': 'url', 'required': True},
            {'name': 'count', 'label': '좋아요 수', 'type': 'number', 'required': True},
        ],
    }
)
if created:
    print(f'상품 생성: {product2.name}')

product3, created = Product.objects.get_or_create(
    code='YOUTUBE_VIEW',
    defaults={
        'name': '유튜브 조회수',
        'description': '유튜브 영상 조회수',
        'base_price': Decimal('200'),
        'schema': [
            {'name': 'url', 'label': '영상 URL', 'type': 'url', 'required': True},
            {'name': 'count', 'label': '조회수', 'type': 'number', 'required': True},
            {'name': 'speed', 'label': '속도', 'type': 'select', 'required': True, 'options': ['저속', '중속', '고속']},
        ],
    }
)
if created:
    print(f'상품 생성: {product3.name}')

# 5. 단가 정책
for product in [product1, product2, product3]:
    PricePolicy.objects.get_or_create(
        product=product,
        user=agency,
        defaults={'price': product.base_price * Decimal('0.8')},
    )
    PricePolicy.objects.get_or_create(
        product=product,
        user=seller,
        defaults={'price': product.base_price * Decimal('0.9')},
    )

print('\n단가 정책 설정 완료')
print('\n=== 초기 데이터 생성 완료 ===')
print('관리자: admin / admin1234')
print('대행사: agency1 / test1234')
print('셀러: seller1 / test1234')
