import { useMemo, useState } from 'react';
import Tabs from '../components/common/Tabs';
import StatsBar from '../components/Dashboard/StatsBar';
import SchedulerStatus from '../components/Dashboard/SchedulerStatus';
import FilterBar from '../components/Dashboard/FilterBar';
import CampaignTable from '../components/Dashboard/CampaignTable';
import { useAccounts, useAgencies, useDashboardStats } from '../hooks/useAccounts';
import { useCampaigns } from '../hooks/useCampaigns';

export default function DashboardPage() {
  const [activeAccount, setActiveAccount] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const { accounts } = useAccounts();
  const { agencies } = useAgencies();

  const accountId = activeAccount === 'all' ? undefined : Number(activeAccount);
  const { stats, loading: statsLoading } = useDashboardStats(accountId);
  const {
    campaigns,
    loading: campaignsLoading,
    page,
    pages,
    updateFilters,
    setPage,
    reload,
  } = useCampaigns({ account_id: accountId });

  const tabs = [
    { key: 'all', label: '전체', count: stats?.total_campaigns },
    ...accounts.map((a) => ({
      key: String(a.id),
      label: a.user_id,
      count: a.campaign_count,
    })),
  ];

  const handleAccountChange = (key: string) => {
    setActiveAccount(key);
    const accId = key === 'all' ? undefined : Number(key);
    updateFilters({ account_id: accId });
  };

  const handleFilter = (f: { agency_name?: string; status?: string; search?: string }) => {
    setSearchTerm(f.search || '');
    updateFilters({ agency_name: f.agency_name, status: f.status });
  };

  const filteredCampaigns = useMemo(() => {
    if (!searchTerm) return campaigns;
    const term = searchTerm.toLowerCase();
    return campaigns.filter((c) => c.place_name.toLowerCase().includes(term));
  }, [campaigns, searchTerm]);

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-xl font-bold">대시보드</h1>

      <Tabs tabs={tabs} activeKey={activeAccount} onChange={handleAccountChange} />

      <StatsBar stats={stats} loading={statsLoading} />

      <SchedulerStatus />

      <FilterBar agencies={agencies} onFilter={handleFilter} />

      <CampaignTable
        campaigns={filteredCampaigns}
        loading={campaignsLoading}
        page={page}
        pages={pages}
        onPageChange={setPage}
        onRefresh={reload}
      />
    </div>
  );
}
