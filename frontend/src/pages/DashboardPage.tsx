import { useState, useEffect } from 'react';
import StatsCards from '@/components/features/dashboard/StatsCards';
import PipelineChart from '@/components/features/dashboard/PipelineChart';
import RecentOrders from '@/components/features/dashboard/RecentOrders';
import { dashboardApi } from '@/api/dashboard';
import type { DashboardSummary } from '@/types';

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    dashboardApi
      .getSummary()
      .then((data) => {
        if (!cancelled) {
          setSummary(data);
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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 h-24" />
          ))}
        </div>
        <div className="bg-white rounded-xl border border-gray-200 h-80" />
        <div className="bg-white rounded-xl border border-gray-200 h-60" />
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">대시보드</h1>
        <p className="mt-1 text-sm text-gray-500">
          플랫폼 운영 현황을 한눈에 확인하세요.
        </p>
      </div>

      <StatsCards
        totalOrders={summary.total_orders}
        activeCampaigns={summary.active_campaigns}
        pendingOrders={summary.pending_orders}
        todayRevenue={summary.today_revenue}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PipelineChart data={summary.pipeline_overview} />
        <RecentOrders orders={summary.recent_orders} />
      </div>
    </div>
  );
}
