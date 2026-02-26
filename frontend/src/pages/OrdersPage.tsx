import { useState, useEffect } from 'react';
import OrderList from '@/components/features/orders/OrderList';
import OrderForm from '@/components/features/orders/OrderForm';
import Pagination from '@/components/common/Pagination';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import { MagnifyingGlassIcon, PlusIcon } from '@heroicons/react/24/outline';
import type { Order, OrderStatus, Product } from '@/types';
import { useAuthStore } from '@/store/auth';
import { ordersApi } from '@/api/orders';
import { productsApi } from '@/api/products';

const statusOptions: { value: string; label: string }[] = [
  { value: '', label: '전체 상태' },
  { value: 'draft', label: '임시저장' },
  { value: 'submitted', label: '접수완료' },
  { value: 'payment_confirmed', label: '입금확인' },
  { value: 'processing', label: '처리중' },
  { value: 'completed', label: '완료' },
  { value: 'cancelled', label: '취소' },
  { value: 'rejected', label: '반려' },
];

export default function OrdersPage() {
  const user = useAuthStore((s) => s.user);
  const [orders, setOrders] = useState<Order[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState<OrderStatus | ''>('');
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const canCreate = user && ['distributor', 'sub_account'].includes(user.role);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    ordersApi
      .list({
        page,
        size: 20,
        status: statusFilter || undefined,
      })
      .then((data) => {
        if (!cancelled) {
          setOrders(data.items);
          setTotalPages(data.pages);
          setTotalItems(data.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '주문 목록을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [statusFilter, page, refreshKey]);

  // Load products for create modal
  useEffect(() => {
    productsApi
      .list({ size: 100, is_active: true })
      .then((data) => setProducts(data.items))
      .catch(() => {});
  }, []);

  const handleCreateOrder = async (data: any) => {
    try {
      await ordersApi.create(data);
      setShowCreateModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '주문 생성에 실패했습니다.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">주문 관리</h1>
          <p className="mt-1 text-sm text-gray-500">
            주문 목록을 조회하고 관리합니다.
          </p>
        </div>
        {canCreate && (
          <Button
            onClick={() => setShowCreateModal(true)}
            icon={<PlusIcon className="h-4 w-4" />}
          >
            주문 생성
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="주문번호, 주문자 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as OrderStatus | '');
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Table */}
      <OrderList orders={orders} loading={loading} />

      {/* Pagination */}
      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalItems={totalItems}
        pageSize={20}
      />

      {/* Create Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="주문 생성"
        size="lg"
      >
        <OrderForm
          products={products}
          onSubmit={handleCreateOrder}
        />
      </Modal>
    </div>
  );
}
