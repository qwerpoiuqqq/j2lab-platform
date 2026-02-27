import type { Company } from '@/types';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import { PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';
import { formatDateTime } from '@/utils/format';

interface CompanyListProps {
  companies: Company[];
  loading?: boolean;
  onEdit?: (company: Company) => void;
  onDelete?: (company: Company) => void;
}

export default function CompanyList({ companies, loading, onEdit, onDelete }: CompanyListProps) {
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
    ...((onEdit || onDelete)
      ? [
          {
            key: 'actions' as keyof Company,
            header: '작업',
            render: (c: Company) => (
              <div className="flex items-center gap-1">
                {onEdit && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onEdit(c); }}
                    className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                    title="수정"
                  >
                    <PencilSquareIcon className="h-4 w-4" />
                  </button>
                )}
                {onDelete && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(c); }}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                    title="삭제"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                )}
              </div>
            ),
          },
        ]
      : []),
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
