import type { User } from '@/types';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import { formatDateTime, getRoleLabel } from '@/utils/format';

interface UserListProps {
  users: User[];
  allUsers?: User[];
  loading?: boolean;
  onEdit?: (user: User) => void;
}

function getRoleBadgeVariant(role: string) {
  const map: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    system_admin: 'danger',
    company_admin: 'primary',
    order_handler: 'info',
    distributor: 'warning',
    sub_account: 'default',
  };
  return map[role] || 'default';
}

export default function UserList({ users, allUsers, loading, onEdit }: UserListProps) {
  const parentMap = new Map<string, User>();
  (allUsers || users).forEach((u) => parentMap.set(u.id, u));

  const columns: Column<User>[] = [
    {
      key: 'name',
      header: '이름',
      render: (u) => (
        <span className="font-medium text-gray-100">{u.name}</span>
      ),
    },
    {
      key: 'email',
      header: '이메일',
      render: (u) => <span className="text-gray-400">{u.email}</span>,
    },
    {
      key: 'role',
      header: '역할',
      render: (u) => (
        <Badge variant={getRoleBadgeVariant(u.role)}>
          {getRoleLabel(u.role)}
        </Badge>
      ),
    },
    {
      key: 'parent',
      header: '상위 유저',
      render: (u) => {
        if (!u.parent_id) return <span className="text-gray-400">-</span>;
        const parent = parentMap.get(u.parent_id);
        return parent ? (
          <span className="text-gray-400 text-sm">{parent.name}</span>
        ) : (
          <span className="text-gray-400 text-xs">{u.parent_id.slice(0, 8)}...</span>
        );
      },
    },
    {
      key: 'company',
      header: '소속 회사',
      render: (u) => (
        <span className="text-gray-400">{u.company?.name || '-'}</span>
      ),
    },
    {
      key: 'is_active',
      header: '상태',
      render: (u) => (
        <Badge variant={u.is_active ? 'success' : 'default'}>
          {u.is_active ? '활성' : '비활성'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: '가입일',
      render: (u) => (
        <span className="text-gray-400 text-xs">
          {formatDateTime(u.created_at)}
        </span>
      ),
    },
  ];

  return (
    <Table<User>
      columns={columns}
      data={users}
      keyExtractor={(u) => u.id}
      onRowClick={onEdit}
      loading={loading}
      emptyMessage="유저가 없습니다."
    />
  );
}
