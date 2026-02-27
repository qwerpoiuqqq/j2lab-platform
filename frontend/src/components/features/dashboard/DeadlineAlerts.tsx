import { Link } from 'react-router-dom';
import type { DeadlineAlert } from '@/types';

const urgencyStyles: Record<string, string> = {
  red: 'bg-red-100 text-red-800 border-red-200',
  orange: 'bg-orange-100 text-orange-800 border-orange-200',
  yellow: 'bg-yellow-100 text-yellow-800 border-yellow-200',
};

const urgencyLabels: Record<string, string> = {
  red: '긴급',
  orange: '주의',
  yellow: '예정',
};

interface Props {
  deadlines: DeadlineAlert[];
}

export default function DeadlineAlerts({ deadlines }: Props) {
  if (deadlines.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">마감 임박 주문</h3>
        <p className="text-sm text-gray-400">7일 이내 마감 주문이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">
        마감 임박 주문 <span className="text-gray-400 font-normal">({deadlines.length})</span>
      </h3>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {deadlines.map((d) => (
          <div
            key={d.order_id}
            className="flex items-center justify-between p-2.5 rounded-lg border border-gray-100 hover:bg-gray-50"
          >
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${urgencyStyles[d.urgency]}`}
              >
                {urgencyLabels[d.urgency]}
              </span>
              <Link to={`/orders/${d.order_id}`} className="font-mono text-xs text-gray-700 hover:text-primary-600 hover:underline">{d.order_number}</Link>
            </div>
            <div className="text-right">
              <span className="text-xs text-gray-500">D-{d.days_remaining}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
