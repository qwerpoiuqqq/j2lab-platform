import { useNavigate } from 'react-router-dom';
import type { Order } from '@/types';
import { formatCurrency, formatRelativeTime } from '@/utils/format';
import { getUnifiedStatus } from '@/components/features/orders/OrderList';

interface RecentOrdersProps {
  orders: Order[];
}

export default function RecentOrders({ orders }: RecentOrdersProps) {
  const navigate = useNavigate();

  return (
    <div className="bg-white rounded-2xl border border-border-subtle shadow-sm">
      <div className="px-5 py-4 border-b border-border-subtle flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-primary-500" />
          <h3 className="text-[15px] font-bold text-gray-100">최근 주문</h3>
        </div>
        <button
          onClick={() => navigate('/orders')}
          className="text-[12px] text-primary-500 hover:text-primary-600 font-semibold transition-colors"
        >
          전체보기
        </button>
      </div>
      <div className="divide-y divide-border-subtle">
        {orders.length === 0 ? (
          <div className="px-5 py-10 text-center text-[13px] text-gray-500">
            최근 주문이 없어요
          </div>
        ) : (
          orders.map((order) => {
            const unified = getUnifiedStatus(order);
            return (
              <div
                key={order.id}
                onClick={() => navigate(`/orders/${order.id}`)}
                className="px-5 py-3.5 flex items-center justify-between hover:bg-surface-raised/50 cursor-pointer transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-gray-100 truncate">
                    {order.order_number}
                  </p>
                  <p className="text-[11px] text-gray-500 mt-0.5">
                    {order.user?.name || '-'} · {formatRelativeTime(order.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-2.5 shrink-0">
                  <span className="text-[13px] font-bold text-gray-100 tabular-nums">
                    {formatCurrency(order.total_amount)}
                  </span>
                  <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full ring-1 ring-inset ${unified.color}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${unified.dotColor}`} />
                    {unified.label}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
