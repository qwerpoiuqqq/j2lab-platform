import { useState, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { campaignsApi } from '@/api/campaigns';
import { campaignAccountsApi } from '@/api/campaignAccounts';
import StatsBar from '@/components/features/campaigns/StatsBar';
import FilterBar from '@/components/features/campaigns/FilterBar';
import SchedulerStatus from '@/components/features/campaigns/SchedulerStatus';
import CampaignTable from '@/components/features/campaigns/CampaignTable';
import type { SuperapAccount } from '@/types';

export default function CampaignsPage() {
  const [activeAccount, setActiveAccount] = useState<string>('all');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [agencyFilter, setAgencyFilter] = useState<string>('');
  const [page, setPage] = useState(1);

  const accountId = activeAccount === 'all' ? undefined : Number(activeAccount);

  // Fetch accounts
  const { data: accountsData } = useQuery({
    queryKey: ['superap-accounts'],
    queryFn: () => campaignAccountsApi.list({ size: 100 }),
  });
  const accounts: SuperapAccount[] = accountsData?.items ?? [];

  // Fetch agencies
  const { data: agenciesData } = useQuery({
    queryKey: ['agencies'],
    queryFn: () => campaignAccountsApi.getAgencies(),
  });
  const agencies: string[] = agenciesData?.agencies ?? [];

  // Fetch stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['campaign-stats', accountId],
    queryFn: () => campaignsApi.getStats({ account_id: accountId }),
  });

  // Fetch campaigns
  const {
    data: campaignsData,
    isLoading: campaignsLoading,
    refetch,
  } = useQuery({
    queryKey: ['campaigns', page, accountId, statusFilter, agencyFilter, debouncedSearch],
    queryFn: () =>
      campaignsApi.list({
        page,
        size: 20,
        account_id: accountId,
        status: statusFilter || undefined,
        agency: agencyFilter || undefined,
        search: debouncedSearch || undefined,
      }),
  });

  const campaigns = campaignsData?.items ?? [];
  const totalPages = campaignsData?.pages ?? 1;
  const totalItems = campaignsData?.total ?? 0;

  // Account tabs
  const tabs: { key: string; label: string; count?: number }[] = [
    { key: 'all', label: '전체', count: stats?.total },
    ...accounts.map((a) => ({
      key: String(a.id),
      label: a.user_id_superap,
      count: a.campaign_count,
    })),
  ];

  const handleAccountChange = (key: string) => {
    setActiveAccount(key);
    setPage(1);
  };

  const handleFilter = useCallback(
    (f: { agency_name?: string; status?: string; search?: string }) => {
      const newSearch = f.search || '';
      setAgencyFilter(f.agency_name || '');
      setStatusFilter(f.status || '');
      setPage(1);
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
      searchTimerRef.current = setTimeout(() => {
        setDebouncedSearch(newSearch);
      }, 300);
    },
    [],
  );

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">캠페인 대시보드</h1>
        <p className="mt-1 text-sm text-gray-500">
          캠페인 현황을 모니터링하고 관리합니다.
        </p>
      </div>

      {/* Account tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleAccountChange(tab.key)}
            className={`
              flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors
              ${
                activeAccount === tab.key
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }
            `}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span
                className={`
                  text-xs px-1.5 py-0.5 rounded-full
                  ${
                    activeAccount === tab.key
                      ? 'bg-white/20 text-white'
                      : 'bg-gray-100 text-gray-500'
                  }
                `}
              >
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Stats */}
      <StatsBar stats={stats ?? null} loading={statsLoading} />

      {/* Scheduler Status */}
      <SchedulerStatus />

      {/* Filters */}
      <FilterBar agencies={agencies} onFilter={handleFilter} />

      {/* Campaign Table */}
      <CampaignTable
        campaigns={campaigns}
        loading={campaignsLoading}
        page={page}
        totalPages={totalPages}
        totalItems={totalItems}
        onPageChange={setPage}
        onRefresh={handleRefresh}
      />
    </div>
  );
}
