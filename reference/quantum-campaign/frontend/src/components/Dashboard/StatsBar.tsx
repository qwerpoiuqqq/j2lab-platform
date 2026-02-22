import type { DashboardStats } from '../../types';

interface StatsBarProps {
  stats: DashboardStats | null;
  loading: boolean;
}

const ITEMS = [
  { key: 'total_campaigns' as const, label: '전체', color: 'bg-blue-500' },
  { key: 'active_campaigns' as const, label: '진행중', color: 'bg-green-500' },
  { key: 'exhausted_today' as const, label: '오늘 소진', color: 'bg-orange-500' },
  { key: 'keyword_warnings' as const, label: '경고', color: 'bg-red-500' },
];

export default function StatsBar({ stats, loading }: StatsBarProps) {
  return (
    <div className="grid grid-cols-4 gap-4">
      {ITEMS.map((item) => (
        <div key={item.key} className="bg-white rounded-lg shadow-sm p-4">
          <div className="flex items-center gap-3">
            <div className={`w-2 h-10 rounded-full ${item.color}`} />
            <div>
              <div className="text-sm text-gray-500">{item.label}</div>
              <div className="text-2xl font-bold">
                {loading ? '-' : (stats?.[item.key] ?? 0)}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
