import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import OrderDetailComponent from '@/components/features/orders/OrderDetail';
import Button from '@/components/common/Button';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import type { Order, OrderItem } from '@/types';

// Mock data
const mockOrder: Order = {
  id: 1,
  order_number: 'ORD-20260223-0001',
  user_id: 'u1',
  user: { id: 'u1', email: 'dist@ilryu.co.kr', name: '김총판', role: 'distributor', balance: 500000, is_active: true, created_at: '2026-02-01T00:00:00Z' },
  company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
  status: 'submitted',
  payment_status: 'unpaid',
  total_amount: 350000,
  vat_amount: 35000,
  notes: '급하게 처리 부탁드립니다.',
  source: 'web',
  created_at: '2026-02-23T09:30:00Z',
};

const mockItems: OrderItem[] = [
  {
    id: 1,
    order_id: 1,
    product_id: 1,
    product: { id: 1, name: '네이버 트래픽 캠페인', code: 'traffic', base_price: 50000, daily_deadline: '18:00', deadline_timezone: 'Asia/Seoul', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    place_url: 'https://map.naver.com/v5/entry/place/1234567890',
    place_name: '맛있는 식당',
    quantity: 30,
    unit_price: 5000,
    subtotal: 150000,
    status: 'pending',
    created_at: '2026-02-23T09:30:00Z',
  },
  {
    id: 2,
    order_id: 1,
    product_id: 1,
    product: { id: 1, name: '네이버 트래픽 캠페인', code: 'traffic', base_price: 50000, daily_deadline: '18:00', deadline_timezone: 'Asia/Seoul', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    place_url: 'https://map.naver.com/v5/entry/place/9876543210',
    place_name: '멋진 카페',
    quantity: 20,
    unit_price: 5000,
    subtotal: 100000,
    status: 'pending',
    created_at: '2026-02-23T09:30:00Z',
  },
  {
    id: 3,
    order_id: 1,
    product_id: 2,
    product: { id: 2, name: '저장하기 캠페인', code: 'save', base_price: 30000, daily_deadline: '17:00', deadline_timezone: 'Asia/Seoul', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    place_url: 'https://map.naver.com/v5/entry/place/1234567890',
    place_name: '맛있는 식당',
    quantity: 50,
    unit_price: 2000,
    subtotal: 100000,
    status: 'pending',
    created_at: '2026-02-23T09:30:00Z',
  },
];

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [order, setOrder] = useState<Order | null>(null);
  const [items, setItems] = useState<OrderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [_actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    // TODO: Replace with actual API call
    setTimeout(() => {
      setOrder({ ...mockOrder, id: Number(id) });
      setItems(mockItems);
      setLoading(false);
    }, 300);
  }, [id]);

  const handleAction = async (action: string) => {
    setActionLoading(true);
    console.log(`Action: ${action} on order ${id}`);
    // TODO: Call actual API
    setTimeout(() => {
      setActionLoading(false);
    }, 500);
  };

  if (loading || !order) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="bg-white rounded-xl border border-gray-200 h-48" />
        <div className="bg-white rounded-xl border border-gray-200 h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/orders')}
          icon={<ArrowLeftIcon className="h-4 w-4" />}
        >
          목록으로
        </Button>
      </div>

      <OrderDetailComponent
        order={order}
        items={items}
        onSubmit={() => handleAction('submit')}
        onConfirmPayment={() => handleAction('confirm-payment')}
        onReject={() => handleAction('reject')}
        onCancel={() => handleAction('cancel')}
        actionLoading={_actionLoading}
      />
    </div>
  );
}
