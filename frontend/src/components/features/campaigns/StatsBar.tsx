import type { CampaignDashboardStats } from '@/types';

interface StatsBarProps {
  stats: CampaignDashboardStats | null;
  loading: boolean;
}

const ITEMS = [
  { key: 'total' as const, label: '전체', color: 'border-l-blue-500', textColor: 'text-blue-600' },
  { key: 'active' as const, label: '진행중', color: 'border-l-green-500', textColor: 'text-green-600' },
  { key: 'exhausted_today' as const, label: '오늘 소진', color: 'border-l-orange-500', textColor: 'text-orange-600' },
  { key: 'keyword_warnings' as const, label: '키워드 경고', color: 'border-l-red-500', textColor: 'text-red-600' },
];

export default function StatsBar({ stats, loading }: StatsBarProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {ITEMS.map((item) => (
        <div
          key={item.key}
          className={`bg-surface rounded-xl border border-border p-5 border-l-4 ${item.color}`}
        >
          <div className="text-sm text-gray-400 mb-1">{item.label}</div>
          <div className={`text-2xl font-bold ${item.textColor}`}>
            {loading ? (
              <div className="h-8 w-12 bg-surface-raised rounded animate-pulse" />
            ) : (
              stats?.[item.key] ?? 0
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
