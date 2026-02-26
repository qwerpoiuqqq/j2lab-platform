import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import OrderDetailComponent from '@/components/features/orders/OrderDetail';
import Button from '@/components/common/Button';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import type { Order, OrderItem } from '@/types';
import { ordersApi } from '@/api/orders';

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [order, setOrder] = useState<Order | null>(null);
  const [items, setItems] = useState<OrderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadOrder = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await ordersApi.get(Number(id));
      setOrder(data);
      setItems(data.items || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '주문을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrder();
  }, [id]);

  const handleAction = async (action: string) => {
    if (!id) return;
    setActionLoading(true);
    try {
      let updated: Order;
      switch (action) {
        case 'submit':
          updated = await ordersApi.submit(Number(id));
          break;
        case 'confirm-payment':
          updated = await ordersApi.confirmPayment(Number(id));
          break;
        case 'reject': {
          const reason = prompt('반려 사유를 입력하세요:');
          if (!reason) {
            setActionLoading(false);
            return;
          }
          updated = await ordersApi.reject(Number(id), reason);
          break;
        }
        case 'cancel':
          updated = await ordersApi.cancel(Number(id));
          break;
        default:
          setActionLoading(false);
          return;
      }
      setOrder(updated);
      setItems(updated.items || []);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '작업에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading || !order) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="bg-white rounded-xl border border-gray-200 h-48" />
        <div className="bg-white rounded-xl border border-gray-200 h-64" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/orders')}
          icon={<ArrowLeftIcon className="h-4 w-4" />}
        >
          목록으로
        </Button>
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">
          {error}
        </div>
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
        actionLoading={actionLoading}
      />
    </div>
  );
}
