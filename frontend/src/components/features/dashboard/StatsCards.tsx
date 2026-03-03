import {
  InboxArrowDownIcon,
  BoltIcon,
  ArrowPathIcon,
  MegaphoneIcon,
  CurrencyDollarIcon,
  ClipboardDocumentListIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import { formatCurrency, formatNumber } from '@/utils/format';
import type { PipelineOverview, UserRole } from '@/types';

interface StatsCardsProps {
  ordersByStatus: Record<string, number>;
  pipelineOverview: PipelineOverview[];
  activeCampaigns?: number;
  todayRevenue: number;
  totalOrders?: number;
  role?: UserRole;
}

export default function StatsCards({
  ordersByStatus,
  pipelineOverview,
  activeCampaigns,
  todayRevenue,
  totalOrders,
  role,
}: StatsCardsProps) {
  const pendingPayment = (ordersByStatus['submitted'] ?? 0);
  const settingReady = pipelineOverview
    .filter((p) => p.stage === 'payment_confirmed')
    .reduce((s, p) => s + p.count, 0);
  const inProgress = pipelineOverview
    .filter((p) =>
      ['extraction_queued', 'extracting', 'extraction_done', 'auto_assign', 'assignment_confirmed', 'registration_queued', 'registering'].includes(p.stage),
    )
    .reduce((s, p) => s + p.count, 0);
  const pendingOrders = (ordersByStatus['submitted'] ?? 0) + (ordersByStatus['payment_confirmed'] ?? 0);

  const allStats = {
    pendingPayment: {
      name: '입금 대기',
      value: formatNumber(pendingPayment),
      icon: InboxArrowDownIcon,
      iconColor: 'text-amber-600',
      iconBg: 'bg-amber-100',
      ringColor: pendingPayment > 0 ? 'ring-2 ring-amber-200' : '',
    },
    settingReady: {
      name: '세팅 가능',
      value: formatNumber(settingReady),
      icon: BoltIcon,
      iconColor: 'text-blue-600',
      iconBg: 'bg-blue-100',
      ringColor: settingReady > 0 ? 'ring-2 ring-blue-200' : '',
    },
    inProgress: {
      name: '진행중',
      value: formatNumber(inProgress),
      icon: ArrowPathIcon,
      iconColor: 'text-indigo-600',
      iconBg: 'bg-indigo-100',
      ringColor: '',
    },
    activeCampaigns: {
      name: '운영중 캠페인',
      value: formatNumber(activeCampaigns ?? 0),
      icon: MegaphoneIcon,
      iconColor: 'text-green-600',
      iconBg: 'bg-green-100',
      ringColor: '',
    },
    todayRevenue: {
      name: '오늘 매출',
      value: formatCurrency(todayRevenue),
      icon: CurrencyDollarIcon,
      iconColor: 'text-purple-600',
      iconBg: 'bg-purple-100',
      ringColor: '',
    },
    totalOrders: {
      name: '전체 접수',
      value: formatNumber(totalOrders ?? 0),
      icon: ClipboardDocumentListIcon,
      iconColor: 'text-gray-600',
      iconBg: 'bg-gray-100',
      ringColor: '',
    },
    pendingOrders: {
      name: '대기중',
      value: formatNumber(pendingOrders),
      icon: ClockIcon,
      iconColor: 'text-orange-600',
      iconBg: 'bg-orange-100',
      ringColor: pendingOrders > 0 ? 'ring-2 ring-orange-200' : '',
    },
  };

  let stats;
  switch (role) {
    case 'distributor':
      stats = [allStats.totalOrders, allStats.pendingOrders, allStats.todayRevenue];
      break;
    case 'sub_account':
      stats = [allStats.totalOrders, allStats.pendingOrders];
      break;
    case 'order_handler':
      stats = [allStats.pendingPayment, allStats.settingReady, allStats.inProgress];
      break;
    default: // system_admin, company_admin
      stats = [
        allStats.pendingPayment,
        allStats.settingReady,
        allStats.inProgress,
        ...(activeCampaigns !== undefined ? [allStats.activeCampaigns] : []),
        allStats.todayRevenue,
      ];
      break;
  }

  const gridCols =
    stats.length <= 3 ? 'lg:grid-cols-3' : stats.length === 4 ? 'lg:grid-cols-4' : 'lg:grid-cols-5';

  return (
    <div className={`grid grid-cols-2 sm:grid-cols-3 ${gridCols} gap-4`}>
      {stats.map((stat) => (
        <div
          key={stat.name}
          className={`bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-shadow ${stat.ringColor}`}
        >
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl ${stat.iconBg}`}>
              <stat.icon className={`h-5 w-5 ${stat.iconColor}`} />
            </div>
            <div>
              <p className="text-xs text-gray-500">{stat.name}</p>
              <p className="text-xl font-bold text-gray-900">{stat.value}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
