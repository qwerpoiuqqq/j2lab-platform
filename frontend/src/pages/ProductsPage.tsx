import { useState, useEffect } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import { formatCurrency, formatDateTime } from '@/utils/format';
import type { Product } from '@/types';

// Mock data
const mockProducts: Product[] = [
  {
    id: 1,
    name: '네이버 트래픽 캠페인',
    code: 'traffic',
    category: 'campaign',
    description: '네이버 플레이스 트래픽 유입 캠페인. 일일 방문수 증가.',
    base_price: 50000,
    min_work_days: 7,
    max_work_days: 30,
    daily_deadline: '18:00',
    deadline_timezone: 'Asia/Seoul',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: '저장하기 캠페인',
    code: 'save',
    category: 'campaign',
    description: '네이버 플레이스 저장하기 캠페인. 저장수 증가.',
    base_price: 30000,
    min_work_days: 7,
    max_work_days: 30,
    daily_deadline: '17:00',
    deadline_timezone: 'Asia/Seoul',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 3,
    name: '월보장 패키지',
    code: 'monthly_guarantee',
    category: 'monthly',
    description: '월 단위 보장형 캠페인. 트래픽 + 저장 + 공유 통합.',
    base_price: 200000,
    min_work_days: 30,
    max_work_days: 30,
    daily_deadline: '18:00',
    deadline_timezone: 'Asia/Seoul',
    is_active: true,
    created_at: '2026-01-15T00:00:00Z',
  },
  {
    id: 4,
    name: '키워드 서비스',
    code: 'keyword_service',
    category: 'keyword_service',
    description: '키워드 추출 + 분석 단독 서비스.',
    base_price: 10000,
    daily_deadline: '18:00',
    deadline_timezone: 'Asia/Seoul',
    is_active: false,
    created_at: '2026-01-01T00:00:00Z',
  },
];

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TODO: Replace with actual API call
    setTimeout(() => {
      setProducts(mockProducts);
      setLoading(false);
    }, 300);
  }, []);

  const columns: Column<Product>[] = [
    {
      key: 'name',
      header: '상품명',
      render: (p) => (
        <div>
          <p className="font-medium text-gray-900">{p.name}</p>
          <p className="text-xs text-gray-500">{p.description}</p>
        </div>
      ),
    },
    {
      key: 'code',
      header: '코드',
      render: (p) => (
        <span className="font-mono text-sm text-gray-600">{p.code}</span>
      ),
    },
    {
      key: 'category',
      header: '카테고리',
      render: (p) => (
        <Badge variant="info">{p.category || '-'}</Badge>
      ),
    },
    {
      key: 'base_price',
      header: '기본가격',
      render: (p) => (
        <span className="font-medium text-gray-900">
          {formatCurrency(p.base_price)}
        </span>
      ),
    },
    {
      key: 'daily_deadline',
      header: '일일 마감',
      render: (p) => (
        <span className="text-gray-600">{p.daily_deadline}</span>
      ),
    },
    {
      key: 'is_active',
      header: '상태',
      render: (p) => (
        <Badge variant={p.is_active ? 'success' : 'default'}>
          {p.is_active ? '활성' : '비활성'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: '생성일',
      render: (p) => (
        <span className="text-gray-500 text-xs">
          {formatDateTime(p.created_at)}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">상품 관리</h1>
        <p className="mt-1 text-sm text-gray-500">
          상품 목록을 조회합니다.
        </p>
      </div>

      {/* Table */}
      <Table<Product>
        columns={columns}
        data={products}
        keyExtractor={(p) => p.id}
        loading={loading}
        emptyMessage="상품이 없습니다."
      />
    </div>
  );
}
