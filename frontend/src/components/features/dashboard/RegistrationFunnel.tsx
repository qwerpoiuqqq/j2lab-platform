interface RegistrationQueueItem {
  status: string;
  registration_step: string;
  count: number;
}

interface Props {
  queue: RegistrationQueueItem[];
}

const statusLabels: Record<string, string> = {
  pending: '대기',
  queued: '큐잉',
  registering: '등록 중',
};

export default function RegistrationFunnel({ queue }: Props) {
  const totalCount = queue.reduce((sum, item) => sum + item.count, 0);

  if (queue.length === 0) {
    return (
      <div className="bg-surface rounded-xl border border-border p-5">
        <h3 className="text-sm font-semibold text-gray-100 mb-3">등록 대기열</h3>
        <p className="text-sm text-gray-400">등록 대기 중인 캠페인이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-surface rounded-xl border border-border p-5">
      <h3 className="text-sm font-semibold text-gray-100 mb-3">
        등록 대기열 <span className="text-gray-400 font-normal">({totalCount})</span>
      </h3>
      <div className="space-y-2">
        {queue.map((item, idx) => {
          const pct = totalCount > 0 ? Math.round((item.count / totalCount) * 100) : 0;
          return (
            <div key={idx}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-400">
                  {statusLabels[item.status] || item.status}
                  {item.registration_step ? ` / ${item.registration_step}` : ''}
                </span>
                <span className="font-medium text-gray-100">{item.count}</span>
              </div>
              <div className="h-2 bg-surface-raised rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary-500 rounded-full transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
