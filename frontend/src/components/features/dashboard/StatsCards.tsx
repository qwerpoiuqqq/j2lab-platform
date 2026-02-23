import {
  ClipboardDocumentListIcon,
  MegaphoneIcon,
  ClockIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline';
import { formatCurrency, formatNumber } from '@/utils/format';

interface StatsCardsProps {
  totalOrders: number;
  activeCampaigns: number;
  pendingOrders: number;
  todayRevenue: number;
}

export default function StatsCards({
  totalOrders,
  activeCampaigns,
  pendingOrders,
  todayRevenue,
}: StatsCardsProps) {
  const stats = [
    {
      name: '총 주문',
      value: formatNumber(totalOrders),
      icon: ClipboardDocumentListIcon,
      color: 'bg-blue-50 text-blue-600',
      iconBg: 'bg-blue-100',
    },
    {
      name: '활성 캠페인',
      value: formatNumber(activeCampaigns),
      icon: MegaphoneIcon,
      color: 'bg-green-50 text-green-600',
      iconBg: 'bg-green-100',
    },
    {
      name: '대기 주문',
      value: formatNumber(pendingOrders),
      icon: ClockIcon,
      color: 'bg-yellow-50 text-yellow-600',
      iconBg: 'bg-yellow-100',
    },
    {
      name: '오늘 매출',
      value: formatCurrency(todayRevenue),
      icon: CurrencyDollarIcon,
      color: 'bg-purple-50 text-purple-600',
      iconBg: 'bg-purple-100',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <div
          key={stat.name}
          className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow"
        >
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl ${stat.iconBg}`}>
              <stat.icon className={`h-6 w-6 ${stat.color.split(' ')[1]}`} />
            </div>
            <div>
              <p className="text-sm text-gray-500">{stat.name}</p>
              <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
