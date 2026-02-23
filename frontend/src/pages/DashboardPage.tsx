import { useState, useEffect } from 'react';
import StatsCards from '@/components/features/dashboard/StatsCards';
import PipelineChart from '@/components/features/dashboard/PipelineChart';
import RecentOrders from '@/components/features/dashboard/RecentOrders';
import type { DashboardSummary } from '@/types';

// Mock data for development
const mockSummary: DashboardSummary = {
  total_orders: 156,
  active_campaigns: 42,
  pending_orders: 8,
  today_revenue: 2450000,
  orders_by_status: {
    draft: 3,
    submitted: 5,
    payment_confirmed: 12,
    processing: 28,
    completed: 98,
    cancelled: 7,
    rejected: 3,
  },
  campaigns_by_status: {
    pending_registration: 3,
    registering: 2,
    active: 42,
    paused: 5,
    completed: 28,
    failed: 1,
    cancelled: 2,
  },
  pipeline_overview: [
    { stage: 'order_received', count: 8 },
    { stage: 'payment_confirmed', count: 12 },
    { stage: 'extraction_queued', count: 4 },
    { stage: 'extracting', count: 2 },
    { stage: 'extraction_done', count: 6 },
    { stage: 'auto_assign', count: 3 },
    { stage: 'assignment_confirmed', count: 5 },
    { stage: 'registration_queued', count: 4 },
    { stage: 'registering', count: 2 },
    { stage: 'active', count: 42 },
    { stage: 'completed', count: 28 },
    { stage: 'failed', count: 1 },
  ],
  recent_orders: [
    {
      id: 1,
      order_number: 'ORD-20260223-0001',
      user_id: 'user-1',
      user: {
        id: 'user-1',
        email: 'distributor@ilryu.co.kr',
        name: '김총판',
        role: 'distributor',
        balance: 500000,
        is_active: true,
        created_at: '2026-02-01T00:00:00Z',
      },
      company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
      status: 'submitted',
      payment_status: 'unpaid',
      total_amount: 350000,
      vat_amount: 35000,
      source: 'web',
      created_at: '2026-02-23T09:30:00Z',
      item_count: 3,
    },
    {
      id: 2,
      order_number: 'ORD-20260223-0002',
      user_id: 'user-2',
      user: {
        id: 'user-2',
        email: 'sub@ilryu.co.kr',
        name: '이하부',
        role: 'sub_account',
        balance: 200000,
        is_active: true,
        created_at: '2026-02-05T00:00:00Z',
      },
      company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
      status: 'payment_confirmed',
      payment_status: 'confirmed',
      total_amount: 150000,
      vat_amount: 15000,
      source: 'web',
      created_at: '2026-02-23T10:15:00Z',
      item_count: 1,
    },
    {
      id: 3,
      order_number: 'ORD-20260222-0015',
      user_id: 'user-3',
      user: {
        id: 'user-3',
        email: 'dist@j2lab.co.kr',
        name: '박총판',
        role: 'distributor',
        balance: 800000,
        is_active: true,
        created_at: '2026-01-15T00:00:00Z',
      },
      company: { id: 2, name: '제이투랩', code: 'j2lab', is_active: true, created_at: '2026-01-01T00:00:00Z' },
      status: 'processing',
      payment_status: 'confirmed',
      total_amount: 500000,
      vat_amount: 50000,
      source: 'excel',
      created_at: '2026-02-22T14:20:00Z',
      item_count: 5,
    },
    {
      id: 4,
      order_number: 'ORD-20260222-0014',
      user_id: 'user-1',
      user: {
        id: 'user-1',
        email: 'distributor@ilryu.co.kr',
        name: '김총판',
        role: 'distributor',
        balance: 500000,
        is_active: true,
        created_at: '2026-02-01T00:00:00Z',
      },
      company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
      status: 'completed',
      payment_status: 'settled',
      total_amount: 280000,
      vat_amount: 28000,
      source: 'web',
      created_at: '2026-02-22T11:00:00Z',
      item_count: 2,
    },
    {
      id: 5,
      order_number: 'ORD-20260221-0010',
      user_id: 'user-4',
      user: {
        id: 'user-4',
        email: 'handler@ilryu.co.kr',
        name: '최담당',
        role: 'order_handler',
        balance: 0,
        is_active: true,
        created_at: '2026-02-01T00:00:00Z',
      },
      company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
      status: 'cancelled',
      payment_status: 'unpaid',
      total_amount: 120000,
      vat_amount: 12000,
      source: 'web',
      created_at: '2026-02-21T16:45:00Z',
      item_count: 1,
    },
  ],
};

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TODO: Replace with actual API call
    // dashboardApi.getSummary().then(setSummary)
    const timer = setTimeout(() => {
      setSummary(mockSummary);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
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
