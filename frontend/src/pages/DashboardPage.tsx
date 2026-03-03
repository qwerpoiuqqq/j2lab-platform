import { useState, useEffect } from 'react';
import StatsCards from '@/components/features/dashboard/StatsCards';
import PipelineChart from '@/components/features/dashboard/PipelineChart';
import RecentOrders from '@/components/features/dashboard/RecentOrders';
import DeadlineAlerts from '@/components/features/dashboard/DeadlineAlerts';
import KeywordWarnings from '@/components/features/dashboard/KeywordWarnings';
import RegistrationFunnel from '@/components/features/dashboard/RegistrationFunnel';
import WeeklyTrendChart from '@/components/features/dashboard/WeeklyTrendChart';
import OrderStatusSummary from '@/components/features/dashboard/OrderStatusSummary';
import SubAccountOrders from '@/components/features/orders/SubAccountOrders';
import { dashboardApi } from '@/api/dashboard';
import type { DashboardSummary, EnhancedDashboard } from '@/types';

const ROLE_CONFIG: Record<string, { title: string; description: string }> = {
  system_admin: { title: '관리자 대시보드', description: '전체 운영 현황과 처리가 필요한 항목을 한눈에 확인하세요.' },
  company_admin: { title: '관리자 대시보드', description: '전체 운영 현황과 처리가 필요한 항목을 한눈에 확인하세요.' },
  order_handler: { title: '담당자 업무 현황', description: '처리가 필요한 주문과 진행 상태를 확인하세요.' },
  distributor: { title: '총판 접수 현황', description: '하부계정 접수건과 매출 현황을 확인하세요.' },
  sub_account: { title: '내 접수 현황', description: '접수한 주문의 진행 상태를 확인하세요.' },
};

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [enhanced, setEnhanced] = useState<EnhancedDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([dashboardApi.getSummary(), dashboardApi.getEnhanced()])
      .then(([summaryData, enhancedData]) => {
        if (!cancelled) {
          setSummary(summaryData);
          setEnhanced(enhancedData);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '대시보드를 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading || !summary) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-4 h-20" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 h-64" />
          <div className="bg-white rounded-xl border border-gray-200 h-64" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">
        {error}
      </div>
    );
  }

  const role = summary.user_role;
  const config = ROLE_CONFIG[role] ?? ROLE_CONFIG.sub_account;
  const isAdmin = role === 'system_admin' || role === 'company_admin';
  const isHandler = role === 'order_handler';
  const isDistributor = role === 'distributor';
  const canSeeCampaigns = isAdmin || isHandler;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{config.title}</h1>
        <p className="mt-1 text-sm text-gray-500">{config.description}</p>
      </div>

      {/* Stats cards (role-based) */}
      <StatsCards
        ordersByStatus={summary.orders_by_status}
        pipelineOverview={summary.pipeline_overview}
        activeCampaigns={isAdmin ? summary.active_campaigns : undefined}
        todayRevenue={summary.today_revenue}
        totalOrders={summary.total_orders}
        role={role}
      />

      {/* Row 2: Weekly trend + Order status (admin only) */}
      {isAdmin && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {enhanced && <WeeklyTrendChart data={enhanced.weekly_trend} />}
          <OrderStatusSummary ordersByStatus={summary.orders_by_status} />
        </div>
      )}

      {/* Pipeline + Recent orders */}
      {canSeeCampaigns && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PipelineChart data={summary.pipeline_overview} />
          <RecentOrders orders={summary.recent_orders} />
        </div>
      )}

      {/* Distributor: Sub-account order management */}
      {(isDistributor || isAdmin) && (
        <SubAccountOrders />
      )}

      {/* Distributor/sub_account: Order status + Recent */}
      {!canSeeCampaigns && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <OrderStatusSummary ordersByStatus={summary.orders_by_status} />
          <RecentOrders orders={summary.recent_orders} />
        </div>
      )}

      {/* Alerts section (role-based) */}
      {enhanced && (
        <div className={`grid grid-cols-1 ${isAdmin ? 'lg:grid-cols-3' : isHandler ? 'lg:grid-cols-2' : ''} gap-6`}>
          <DeadlineAlerts deadlines={enhanced.upcoming_deadlines} />
          {canSeeCampaigns && (
            <KeywordWarnings warnings={enhanced.keyword_warnings} />
          )}
          {isAdmin && (
            <RegistrationFunnel queue={enhanced.registration_queue} />
          )}
        </div>
      )}
    </div>
  );
}
