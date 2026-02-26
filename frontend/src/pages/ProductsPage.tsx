import { useState, useEffect } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import { formatCurrency, formatDateTime } from '@/utils/format';
import type { Product } from '@/types';
import { productsApi } from '@/api/products';

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    productsApi
      .list({ size: 100 })
      .then((data) => {
        if (!cancelled) {
          setProducts(data.items);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '상품 목록을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
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

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {error}
        </div>
      )}

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
