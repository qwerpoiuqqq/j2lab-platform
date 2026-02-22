import { useState } from 'react';
import type { Agency } from '../../types';

interface FilterBarProps {
  agencies: Agency[];
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
  { value: 'pending_extend', label: '연장 대기' },
  { value: 'completed', label: '종료' },
];

export default function FilterBar({ agencies, onFilter }: FilterBarProps) {
  const [agency, setAgency] = useState('');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');

  const handleAgency = (v: string) => {
    setAgency(v);
    onFilter({ agency_name: v || undefined, status: status || undefined });
  };

  const handleStatus = (v: string) => {
    setStatus(v);
    onFilter({ agency_name: agency || undefined, status: v || undefined });
  };

  const handleSearch = () => {
    onFilter({ agency_name: agency || undefined, status: status || undefined, search: search || undefined });
  };

  return (
    <div className="flex items-center gap-3 bg-white rounded-lg shadow-sm p-3">
      <select
        value={agency}
        onChange={(e) => handleAgency(e.target.value)}
        className="border rounded-md px-3 py-1.5 text-sm"
      >
        <option value="">전체 대행사</option>
        {agencies.map((a) => (
          <option key={a.agency_name} value={a.agency_name}>
            {a.agency_name} ({a.campaign_count})
          </option>
        ))}
      </select>

      <select
        value={status}
        onChange={(e) => handleStatus(e.target.value)}
        className="border rounded-md px-3 py-1.5 text-sm"
      >
        {STATUS_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      <div className="flex-1 flex gap-2">
        <input
          type="text"
          placeholder="상호명 검색..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1 border rounded-md px-3 py-1.5 text-sm"
        />
        <button
          onClick={handleSearch}
          className="px-3 py-1.5 bg-blue-500 text-white text-sm rounded-md hover:bg-blue-600"
        >
          검색
        </button>
      </div>
    </div>
  );
}
