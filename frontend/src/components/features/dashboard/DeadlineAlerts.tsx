import { Link } from 'react-router-dom';
import type { DeadlineAlert } from '@/types';

const urgencyStyles: Record<string, string> = {
  red: 'bg-red-900/30 text-red-400 border-red-800/50',
  orange: 'bg-orange-900/30 text-orange-400 border-orange-800/50',
  yellow: 'bg-yellow-900/30 text-yellow-400 border-yellow-800/50',
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
      <div className="bg-surface rounded-xl border border-border p-5">
        <h3 className="text-sm font-semibold text-gray-100 mb-3">마감 임박 주문</h3>
        <p className="text-sm text-gray-400">7일 이내 마감 주문이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-surface rounded-xl border border-border p-5">
      <h3 className="text-sm font-semibold text-gray-100 mb-3">
        마감 임박 주문 <span className="text-gray-400 font-normal">({deadlines.length})</span>
      </h3>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {deadlines.map((d) => (
          <div
            key={d.order_id}
            className="flex items-center justify-between p-2.5 rounded-lg border border-border-subtle hover:bg-surface-raised"
          >
            <div className="flex items-center gap-2">
              <span
                className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${urgencyStyles[d.urgency]}`}
              >
                {urgencyLabels[d.urgency]}
              </span>
              <Link to={`/orders/${d.order_id}`} className="font-mono text-xs text-gray-300 hover:text-primary-600 hover:underline">{d.order_number}</Link>
            </div>
            <div className="text-right">
              <span className="text-xs text-gray-400">D-{d.days_remaining}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
