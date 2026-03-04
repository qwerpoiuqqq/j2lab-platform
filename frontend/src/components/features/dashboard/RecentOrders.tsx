import { useNavigate } from 'react-router-dom';
import type { Order } from '@/types';
import Badge from '@/components/common/Badge';
import {
  formatCurrency,
  formatRelativeTime,
  getOrderStatusLabel,
} from '@/utils/format';

interface RecentOrdersProps {
  orders: Order[];
}

function getStatusBadgeVariant(status: string) {
  const map: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    draft: 'default',
    submitted: 'info',
    payment_confirmed: 'success',
    processing: 'warning',
    completed: 'success',
    cancelled: 'danger',
    rejected: 'danger',
  };
  return map[status] || 'default';
}

export default function RecentOrders({ orders }: RecentOrdersProps) {
  const navigate = useNavigate();

  return (
    <div className="bg-surface rounded-xl border border-border">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between">
        <h3 className="text-base font-semibold text-gray-100">최근 주문</h3>
        <button
          onClick={() => navigate('/orders')}
          className="text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          전체보기
        </button>
      </div>
      <div className="divide-y divide-border">
        {orders.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-gray-400">
            최근 주문이 없습니다.
          </div>
        ) : (
          orders.map((order) => (
            <div
              key={order.id}
              onClick={() => navigate(`/orders/${order.id}`)}
              className="px-5 py-3.5 flex items-center justify-between hover:bg-surface-raised cursor-pointer transition-colors"
            >
              <div className="flex items-center gap-4 min-w-0">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-100 truncate">
                    {order.order_number}
                  </p>
                  <p className="text-xs text-gray-400">
                    {order.user?.name || '알 수 없음'} &middot;{' '}
                    {formatRelativeTime(order.created_at)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-sm font-medium text-gray-100">
                  {formatCurrency(order.total_amount)}
                </span>
                <Badge variant={getStatusBadgeVariant(order.status)}>
                  {getOrderStatusLabel(order.status)}
                </Badge>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
