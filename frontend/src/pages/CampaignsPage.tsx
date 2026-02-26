import { useState, useEffect } from 'react';
import CampaignList from '@/components/features/campaigns/CampaignList';
import Pagination from '@/components/common/Pagination';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import type { Campaign, CampaignStatus } from '@/types';
import { campaignsApi } from '@/api/campaigns';

const statusOptions = [
  { value: '', label: '전체 상태' },
  { value: 'pending', label: '대기' },
  { value: 'queued', label: '대기열' },
  { value: 'registering', label: '등록중' },
  { value: 'active', label: '활성' },
  { value: 'paused', label: '일시정지' },
  { value: 'completed', label: '완료' },
  { value: 'failed', label: '실패' },
  { value: 'expired', label: '만료' },
];

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState<CampaignStatus | ''>('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    campaignsApi
      .list({
        page,
        size: 20,
        status: statusFilter || undefined,
      })
      .then((data) => {
        if (!cancelled) {
          setCampaigns(data.items);
          setTotalPages(data.pages);
          setTotalItems(data.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '캠페인 목록을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [statusFilter, page]);

  // Client-side search filter on loaded data
  const filteredCampaigns = search
    ? campaigns.filter((c) => {
        const s = search.toLowerCase();
        return (
          c.campaign_code?.toLowerCase().includes(s) ||
          c.place_name?.toLowerCase().includes(s)
        );
      })
    : campaigns;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">캠페인 관리</h1>
        <p className="mt-1 text-sm text-gray-500">
          캠페인 목록을 조회하고 상태를 관리합니다.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="캠페인 코드, 플레이스 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as CampaignStatus | '');
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Table */}
      <CampaignList campaigns={filteredCampaigns} loading={loading} />

      {/* Pagination */}
      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalItems={totalItems}
        pageSize={20}
      />
    </div>
  );
}
