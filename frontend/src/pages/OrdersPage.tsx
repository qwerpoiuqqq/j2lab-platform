import { useState, useEffect, useCallback } from 'react';
import OrderList from '@/components/features/orders/OrderList';
import OrderForm from '@/components/features/orders/OrderForm';
import Pagination from '@/components/common/Pagination';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import { MagnifyingGlassIcon, PlusIcon } from '@heroicons/react/24/outline';
import type { Order, OrderStatus, Product } from '@/types';
import { useAuthStore } from '@/store/auth';

// Mock data
const mockOrders: Order[] = [
  {
    id: 1,
    order_number: 'ORD-20260223-0001',
    user_id: 'u1',
    user: { id: 'u1', email: 'dist@ilryu.co.kr', name: '김총판', role: 'distributor', balance: 500000, is_active: true, created_at: '2026-02-01T00:00:00Z' },
    company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    status: 'submitted',
    payment_status: 'unpaid',
    total_amount: 350000,
    vat_amount: 35000,
    source: 'web',
    created_at: '2026-02-23T09:30:00Z',
    item_count: 3,
  },
  {
    id: 2,
    order_number: 'ORD-20260223-0002',
    user_id: 'u2',
    user: { id: 'u2', email: 'sub@ilryu.co.kr', name: '이하부', role: 'sub_account', balance: 200000, is_active: true, created_at: '2026-02-05T00:00:00Z' },
    company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    status: 'payment_confirmed',
    payment_status: 'confirmed',
    total_amount: 150000,
    vat_amount: 15000,
    source: 'web',
    created_at: '2026-02-23T10:15:00Z',
    item_count: 1,
  },
  {
    id: 3,
    order_number: 'ORD-20260222-0015',
    user_id: 'u3',
    user: { id: 'u3', email: 'dist@j2lab.co.kr', name: '박총판', role: 'distributor', balance: 800000, is_active: true, created_at: '2026-01-15T00:00:00Z' },
    company: { id: 2, name: '제이투랩', code: 'j2lab', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    status: 'processing',
    payment_status: 'confirmed',
    total_amount: 500000,
    vat_amount: 50000,
    source: 'excel',
    created_at: '2026-02-22T14:20:00Z',
    item_count: 5,
  },
  {
    id: 4,
    order_number: 'ORD-20260222-0014',
    user_id: 'u1',
    user: { id: 'u1', email: 'dist@ilryu.co.kr', name: '김총판', role: 'distributor', balance: 500000, is_active: true, created_at: '2026-02-01T00:00:00Z' },
    company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    status: 'completed',
    payment_status: 'settled',
    total_amount: 280000,
    vat_amount: 28000,
    source: 'web',
    created_at: '2026-02-22T11:00:00Z',
    item_count: 2,
  },
  {
    id: 5,
    order_number: 'ORD-20260221-0010',
    user_id: 'u4',
    user: { id: 'u4', email: 'handler@ilryu.co.kr', name: '최담당', role: 'order_handler', balance: 0, is_active: true, created_at: '2026-02-01T00:00:00Z' },
    company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    status: 'cancelled',
    payment_status: 'unpaid',
    total_amount: 120000,
    vat_amount: 12000,
    source: 'web',
    created_at: '2026-02-21T16:45:00Z',
    item_count: 1,
  },
];

const mockProducts: Product[] = [
  {
    id: 1,
    name: '네이버 트래픽 캠페인',
    code: 'traffic',
    category: 'campaign',
    base_price: 50000,
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
    base_price: 30000,
    daily_deadline: '17:00',
    deadline_timezone: 'Asia/Seoul',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
  },
];

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
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<OrderStatus | ''>('');
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const canCreate = user && ['distributor', 'sub_account'].includes(user.role);

  const loadOrders = useCallback(() => {
    setLoading(true);
    // TODO: Replace with actual API call
    setTimeout(() => {
      let filtered = [...mockOrders];
      if (statusFilter) {
        filtered = filtered.filter((o) => o.status === statusFilter);
      }
      if (search) {
        const s = search.toLowerCase();
        filtered = filtered.filter(
          (o) =>
            o.order_number.toLowerCase().includes(s) ||
            o.user?.name?.toLowerCase().includes(s),
        );
      }
      setOrders(filtered);
      setLoading(false);
    }, 300);
  }, [statusFilter, search]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders, page]);

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
          onChange={(e) => setStatusFilter(e.target.value as OrderStatus | '')}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <OrderList orders={orders} loading={loading} />

      {/* Pagination */}
      <Pagination
        page={page}
        totalPages={3}
        onPageChange={setPage}
        totalItems={mockOrders.length}
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
          products={mockProducts}
          onSubmit={(data) => {
            console.log('Create order:', data);
            setShowCreateModal(false);
            loadOrders();
          }}
        />
      </Modal>
    </div>
  );
}
