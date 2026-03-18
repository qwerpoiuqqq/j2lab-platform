import { useState } from 'react';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import Button from '@/components/common/Button';

interface FilterBarProps {
  companies: { id: number; name: string }[];
  onFilter: (filters: { agency_name?: string; status?: string; search?: string }) => void;
}

const STATUS_OPTIONS = [
  { value: '', label: '전체 상태' },
  { value: 'active', label: '진행중' },
  { value: 'daily_exhausted', label: '일일소진' },
  { value: 'campaign_exhausted', label: '전체소진' },
  { value: 'deactivated', label: '중단' },
  { value: 'paused', label: '일시정지' },
  { value: 'pending', label: '대기중' },
  { value: 'queued', label: '대기열' },
  { value: 'registering', label: '등록중' },
  { value: 'pending_extend', label: '연장 대기' },
  { value: 'completed', label: '종료' },
  { value: 'failed', label: '실패' },
  { value: 'expired', label: '만료' },
];

export default function FilterBar({ companies, onFilter }: FilterBarProps) {
  const [company, setCompany] = useState('');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');

  const handleCompany = (v: string) => {
    setCompany(v);
    onFilter({ agency_name: v || undefined, status: status || undefined, search: search || undefined });
  };

  const handleStatus = (v: string) => {
    setStatus(v);
    onFilter({ agency_name: company || undefined, status: v || undefined, search: search || undefined });
  };

  const handleSearch = () => {
    onFilter({ agency_name: company || undefined, status: status || undefined, search: search || undefined });
  };

  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 bg-surface rounded-xl border border-border p-4">
      <select
        value={company}
        onChange={(e) => handleCompany(e.target.value)}
        className="rounded-lg border border-border-strong px-3 py-2 text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400"
      >
        <option value="">전체 회사</option>
        {companies.map((c) => (
          <option key={c.id} value={c.name}>
            {c.name}
          </option>
        ))}
      </select>

      <select
        value={status}
        onChange={(e) => handleStatus(e.target.value)}
        className="rounded-lg border border-border-strong px-3 py-2 text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400"
      >
        {STATUS_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      <div className="flex-1 flex gap-2">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="상호명 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-border-strong text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400"
          />
        </div>
        <Button variant="primary" size="sm" onClick={handleSearch}>
          검색
        </Button>
      </div>
    </div>
  );
}
