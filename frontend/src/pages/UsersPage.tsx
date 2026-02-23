import { useState, useEffect } from 'react';
import UserList from '@/components/features/users/UserList';
import UserForm from '@/components/features/users/UserForm';
import Pagination from '@/components/common/Pagination';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import { PlusIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import type { User, UserRole, Company } from '@/types';

// Mock data
const mockUsers: User[] = [
  {
    id: 'u0',
    email: 'admin@j2lab.co.kr',
    name: '시스템관리자',
    role: 'system_admin',
    balance: 0,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'u1',
    email: 'admin@ilryu.co.kr',
    name: '일류 관리자',
    role: 'company_admin',
    company_id: 1,
    company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    balance: 10000000,
    is_active: true,
    created_at: '2026-01-05T00:00:00Z',
  },
  {
    id: 'u2',
    email: 'handler@ilryu.co.kr',
    name: '최담당',
    role: 'order_handler',
    company_id: 1,
    company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    balance: 0,
    is_active: true,
    created_at: '2026-01-10T00:00:00Z',
  },
  {
    id: 'u3',
    email: 'dist@ilryu.co.kr',
    name: '김총판',
    role: 'distributor',
    company_id: 1,
    company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    balance: 500000,
    is_active: true,
    created_at: '2026-02-01T00:00:00Z',
  },
  {
    id: 'u4',
    email: 'sub1@ilryu.co.kr',
    name: '이하부',
    role: 'sub_account',
    company_id: 1,
    company: { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    parent_id: 'u3',
    balance: 200000,
    is_active: true,
    created_at: '2026-02-05T00:00:00Z',
  },
  {
    id: 'u5',
    email: 'admin@j2lab.co.kr',
    name: '제이투 관리자',
    role: 'company_admin',
    company_id: 2,
    company: { id: 2, name: '제이투랩', code: 'j2lab', is_active: true, created_at: '2026-01-01T00:00:00Z' },
    balance: 5000000,
    is_active: true,
    created_at: '2026-01-03T00:00:00Z',
  },
];

const mockCompanies: Company[] = [
  { id: 1, name: '일류기획', code: 'ilryu', is_active: true, created_at: '2026-01-01T00:00:00Z' },
  { id: 2, name: '제이투랩', code: 'j2lab', is_active: true, created_at: '2026-01-01T00:00:00Z' },
];

const roleFilterOptions = [
  { value: '', label: '전체 역할' },
  { value: 'system_admin', label: '시스템 관리자' },
  { value: 'company_admin', label: '회사 관리자' },
  { value: 'order_handler', label: '접수 담당자' },
  { value: 'distributor', label: '총판' },
  { value: 'sub_account', label: '하부계정' },
];

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState<UserRole | ''>('');
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // TODO: Replace with actual API call
    const timer = setTimeout(() => {
      if (cancelled) return;
      let filtered = [...mockUsers];
      if (roleFilter) {
        filtered = filtered.filter((u) => u.role === roleFilter);
      }
      if (search) {
        const s = search.toLowerCase();
        filtered = filtered.filter(
          (u) =>
            u.name.toLowerCase().includes(s) ||
            u.email.toLowerCase().includes(s),
        );
      }
      setUsers(filtered);
      setLoading(false);
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [roleFilter, search, page, refreshKey]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">유저 관리</h1>
          <p className="mt-1 text-sm text-gray-500">
            유저 목록을 조회하고 관리합니다.
          </p>
        </div>
        <Button
          onClick={() => setShowCreateModal(true)}
          icon={<PlusIcon className="h-4 w-4" />}
        >
          유저 생성
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="이름, 이메일 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value as UserRole | '')}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          {roleFilterOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <UserList users={users} loading={loading} />

      {/* Pagination */}
      <Pagination
        page={page}
        totalPages={1}
        onPageChange={setPage}
        totalItems={mockUsers.length}
        pageSize={20}
      />

      {/* Create Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="유저 생성"
        size="md"
      >
        <UserForm
          companies={mockCompanies}
          onSubmit={(data) => {
            console.log('Create user:', data);
            setShowCreateModal(false);
            setRefreshKey((k) => k + 1);
          }}
          onCancel={() => setShowCreateModal(false)}
        />
      </Modal>
    </div>
  );
}
