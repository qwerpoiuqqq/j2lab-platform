import { useNavigate } from 'react-router-dom';
import { getOrderStatusLabel } from '@/utils/format';

interface Props {
  ordersByStatus: Record<string, number>;
}

const STATUS_CONFIG: { key: string; color: string; bg: string }[] = [
  { key: 'draft', color: 'text-gray-600', bg: 'bg-gray-400' },
  { key: 'submitted', color: 'text-amber-600', bg: 'bg-amber-400' },
  { key: 'payment_confirmed', color: 'text-blue-600', bg: 'bg-blue-400' },
  { key: 'processing', color: 'text-indigo-600', bg: 'bg-indigo-400' },
  { key: 'completed', color: 'text-green-600', bg: 'bg-green-400' },
  { key: 'cancelled', color: 'text-red-600', bg: 'bg-red-400' },
  { key: 'rejected', color: 'text-red-600', bg: 'bg-red-400' },
];

export default function OrderStatusSummary({ ordersByStatus }: Props) {
  const navigate = useNavigate();
  const total = Object.values(ordersByStatus).reduce((s, v) => s + v, 0);
  const activeStatuses = STATUS_CONFIG.filter((s) => (ordersByStatus[s.key] ?? 0) > 0);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-900">주문 현황</h3>
        <button
          onClick={() => navigate('/orders')}
          className="text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          전체보기
        </button>
      </div>

      {total === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">주문이 없습니다.</p>
      ) : (
        <>
          {/* Bar */}
          <div className="flex h-3 rounded-full overflow-hidden mb-4">
            {activeStatuses.map((s) => {
              const count = ordersByStatus[s.key] ?? 0;
              const pct = total > 0 ? (count / total) * 100 : 0;
              return (
                <div
                  key={s.key}
                  className={`${s.bg} transition-all`}
                  style={{ width: `${pct}%` }}
                  title={`${getOrderStatusLabel(s.key)}: ${count}건`}
                />
              );
            })}
          </div>

          {/* Legend */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {STATUS_CONFIG.map((s) => {
              const count = ordersByStatus[s.key] ?? 0;
              if (count === 0) return null;
              return (
                <div
                  key={s.key}
                  className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/orders?status=${s.key}`)}
                >
                  <div className={`w-2.5 h-2.5 rounded-full ${s.bg}`} />
                  <span className="text-xs text-gray-600">{getOrderStatusLabel(s.key)}</span>
                  <span className={`text-xs font-bold ${s.color} ml-auto`}>{count}</span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
