import type { Company } from '@/types';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import { formatDateTime } from '@/utils/format';

interface CompanyListProps {
  companies: Company[];
  loading?: boolean;
}

export default function CompanyList({ companies, loading }: CompanyListProps) {
  const columns: Column<Company>[] = [
    {
      key: 'name',
      header: '회사명',
      render: (c) => (
        <span className="font-medium text-gray-900">{c.name}</span>
      ),
    },
    {
      key: 'code',
      header: '코드',
      render: (c) => (
        <span className="font-mono text-sm text-gray-600">{c.code}</span>
      ),
    },
    {
      key: 'is_active',
      header: '상태',
      render: (c) => (
        <Badge variant={c.is_active ? 'success' : 'default'}>
          {c.is_active ? '활성' : '비활성'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: '생성일',
      render: (c) => (
        <span className="text-gray-500 text-xs">
          {formatDateTime(c.created_at)}
        </span>
      ),
    },
  ];

  return (
    <Table<Company>
      columns={columns}
      data={companies}
      keyExtractor={(c) => c.id}
      loading={loading}
      emptyMessage="회사가 없습니다."
    />
  );
}
