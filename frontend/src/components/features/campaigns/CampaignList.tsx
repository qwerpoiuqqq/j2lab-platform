import { useNavigate } from 'react-router-dom';
import type { Campaign } from '@/types';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import { formatDate, formatNumber, getCampaignStatusLabel } from '@/utils/format';

interface CampaignListProps {
  campaigns: Campaign[];
  loading?: boolean;
}

function getStatusBadgeVariant(status: string) {
  const map: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    pending_registration: 'default',
    registering: 'info',
    active: 'success',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'danger',
  };
  return map[status] || 'default';
}

export default function CampaignList({ campaigns, loading }: CampaignListProps) {
  const navigate = useNavigate();

  const columns: Column<Campaign>[] = [
    {
      key: 'campaign_code',
      header: '캠페인 코드',
      render: (c) => (
        <span className="font-medium text-gray-900">
          {c.campaign_code || `#${c.id}`}
        </span>
      ),
    },
    {
      key: 'place',
      header: '플레이스',
      render: (c) => (
        <span className="text-gray-600">{c.place?.name || '-'}</span>
      ),
    },
    {
      key: 'period',
      header: '기간',
      render: (c) => (
        <span className="text-gray-600 text-xs">
          {c.start_date ? formatDate(c.start_date) : '-'} ~{' '}
          {c.end_date ? formatDate(c.end_date) : '-'}
        </span>
      ),
    },
    {
      key: 'daily_limit',
      header: '일일한도',
      render: (c) => (
        <span className="text-gray-600">{formatNumber(c.daily_limit)}</span>
      ),
    },
    {
      key: 'keywords_count',
      header: '키워드수',
      render: (c) => (
        <span className="text-gray-600">{c.keywords_count || 0}개</span>
      ),
    },
    {
      key: 'status',
      header: '상태',
      render: (c) => (
        <Badge variant={getStatusBadgeVariant(c.status)}>
          {getCampaignStatusLabel(c.status)}
        </Badge>
      ),
    },
  ];

  return (
    <Table<Campaign>
      columns={columns}
      data={campaigns}
      keyExtractor={(c) => c.id}
      onRowClick={(c) => navigate(`/campaigns/${c.id}`)}
      loading={loading}
      emptyMessage="캠페인이 없습니다."
    />
  );
}
