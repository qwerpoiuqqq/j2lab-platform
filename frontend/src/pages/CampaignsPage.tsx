import { useState, useEffect } from 'react';
import CampaignList from '@/components/features/campaigns/CampaignList';
import Pagination from '@/components/common/Pagination';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import type { Campaign, CampaignStatus } from '@/types';

// Mock data
const mockCampaigns: Campaign[] = [
  {
    id: 1,
    campaign_code: 'CMP-20260220-001',
    place: { id: 1, name: '맛있는 식당', url: 'https://map.naver.com/v5/entry/place/1234567890', created_at: '2026-02-20T00:00:00Z' },
    status: 'active',
    start_date: '2026-02-20',
    end_date: '2026-03-22',
    daily_limit: 100,
    total_budget: 300000,
    keywords_count: 45,
    current_keyword: '강남역 맛집',
    last_rotation_at: '2026-02-23T08:00:00Z',
    created_at: '2026-02-20T00:00:00Z',
  },
  {
    id: 2,
    campaign_code: 'CMP-20260221-002',
    place: { id: 2, name: '멋진 카페', url: 'https://map.naver.com/v5/entry/place/9876543210', created_at: '2026-02-21T00:00:00Z' },
    status: 'active',
    start_date: '2026-02-21',
    end_date: '2026-03-23',
    daily_limit: 80,
    total_budget: 240000,
    keywords_count: 32,
    current_keyword: '신촌 카페',
    last_rotation_at: '2026-02-23T08:00:00Z',
    created_at: '2026-02-21T00:00:00Z',
  },
  {
    id: 3,
    campaign_code: 'CMP-20260219-003',
    place: { id: 3, name: '힐링 스파', url: 'https://map.naver.com/v5/entry/place/5555555555', created_at: '2026-02-19T00:00:00Z' },
    status: 'paused',
    start_date: '2026-02-19',
    end_date: '2026-03-21',
    daily_limit: 50,
    total_budget: 150000,
    keywords_count: 20,
    current_keyword: '홍대 스파',
    last_rotation_at: '2026-02-22T23:50:00Z',
    created_at: '2026-02-19T00:00:00Z',
  },
  {
    id: 4,
    campaign_code: 'CMP-20260215-004',
    place: { id: 4, name: '튼튼 헬스장', url: 'https://map.naver.com/v5/entry/place/7777777777', created_at: '2026-02-15T00:00:00Z' },
    status: 'completed',
    start_date: '2026-02-15',
    end_date: '2026-02-22',
    daily_limit: 120,
    total_budget: 360000,
    keywords_count: 55,
    created_at: '2026-02-15T00:00:00Z',
  },
  {
    id: 5,
    campaign_code: 'CMP-20260223-005',
    place: { id: 5, name: '예쁜 네일샵', url: 'https://map.naver.com/v5/entry/place/8888888888', created_at: '2026-02-23T00:00:00Z' },
    status: 'pending_registration',
    start_date: '2026-02-24',
    end_date: '2026-03-26',
    daily_limit: 60,
    total_budget: 180000,
    keywords_count: 0,
    created_at: '2026-02-23T00:00:00Z',
  },
];

const statusOptions = [
  { value: '', label: '전체 상태' },
  { value: 'pending_registration', label: '등록대기' },
  { value: 'registering', label: '등록중' },
  { value: 'active', label: '활성' },
  { value: 'paused', label: '일시정지' },
  { value: 'completed', label: '완료' },
  { value: 'failed', label: '실패' },
  { value: 'cancelled', label: '취소' },
];

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<CampaignStatus | ''>('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    // TODO: Replace with actual API call
    const timer = setTimeout(() => {
      if (cancelled) return;
      let filtered = [...mockCampaigns];
      if (statusFilter) {
        filtered = filtered.filter((c) => c.status === statusFilter);
      }
      if (search) {
        const s = search.toLowerCase();
        filtered = filtered.filter(
          (c) =>
            c.campaign_code?.toLowerCase().includes(s) ||
            c.place?.name?.toLowerCase().includes(s),
        );
      }
      setCampaigns(filtered);
      setLoading(false);
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [statusFilter, search, page]);

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
          onChange={(e) => setStatusFilter(e.target.value as CampaignStatus | '')}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <CampaignList campaigns={campaigns} loading={loading} />

      {/* Pagination */}
      <Pagination
        page={page}
        totalPages={2}
        onPageChange={setPage}
        totalItems={mockCampaigns.length}
        pageSize={20}
      />
    </div>
  );
}
