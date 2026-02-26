import { useState, useEffect } from 'react';
import UserList from '@/components/features/users/UserList';
import UserForm from '@/components/features/users/UserForm';
import Pagination from '@/components/common/Pagination';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import { PlusIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import type { User, UserRole, Company } from '@/types';
import { usersApi } from '@/api/users';
import { companiesApi } from '@/api/companies';

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
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [roleFilter, setRoleFilter] = useState<UserRole | ''>('');
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    usersApi
      .list({
        page,
        size: 20,
        role: roleFilter || undefined,
      })
      .then((data) => {
        if (!cancelled) {
          setUsers(data.items);
          setTotalPages(data.pages);
          setTotalItems(data.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '유저 목록을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [roleFilter, page, refreshKey]);

  // Load companies for create modal
  useEffect(() => {
    companiesApi
      .list(1, 100)
      .then((data) => setCompanies(data.items))
      .catch(() => {});
  }, []);

  // Client-side search filter
  const filteredUsers = search
    ? users.filter((u) => {
        const s = search.toLowerCase();
        return (
          u.name.toLowerCase().includes(s) ||
          u.email.toLowerCase().includes(s)
        );
      })
    : users;

  const handleCreateUser = async (data: any) => {
    try {
      await usersApi.create(data);
      setShowCreateModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '유저 생성에 실패했습니다.');
    }
  };

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
          onChange={(e) => {
            setRoleFilter(e.target.value as UserRole | '');
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        >
          {roleFilterOptions.map((opt) => (
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
      <UserList users={filteredUsers} loading={loading} />

      {/* Pagination */}
      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalItems={totalItems}
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
          companies={companies}
          onSubmit={handleCreateUser}
          onCancel={() => setShowCreateModal(false)}
        />
      </Modal>
    </div>
  );
}
