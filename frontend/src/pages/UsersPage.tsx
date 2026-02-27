import { useState, useEffect, useMemo } from 'react';
import UserList from '@/components/features/users/UserList';
import UserForm from '@/components/features/users/UserForm';
import Pagination from '@/components/common/Pagination';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import Badge from '@/components/common/Badge';
import {
  PlusIcon,
  MagnifyingGlassIcon,
  ListBulletIcon,
  Squares2X2Icon,
  PencilSquareIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { getRoleLabel } from '@/utils/format';
import type { User, UserRole, Company, UpdateUserRequest } from '@/types';
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

const roleColors: Record<string, string> = {
  system_admin: 'text-red-600 bg-red-50',
  company_admin: 'text-blue-600 bg-blue-50',
  order_handler: 'text-green-600 bg-green-50',
  distributor: 'text-purple-600 bg-purple-50',
  sub_account: 'text-gray-600 bg-gray-50',
};

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
  const [viewMode, setViewMode] = useState<'list' | 'tree'>('list');

  // Edit modal
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editForm, setEditForm] = useState<UpdateUserRequest>({});
  const [editLoading, setEditLoading] = useState(false);

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

    return () => { cancelled = true; };
  }, [roleFilter, page, refreshKey]);

  useEffect(() => {
    companiesApi
      .list(1, 100)
      .then((data) => setCompanies(data.items))
      .catch(() => {});
  }, []);

  const filteredUsers = search
    ? users.filter((u) => {
        const s = search.toLowerCase();
        return u.name.toLowerCase().includes(s) || u.email.toLowerCase().includes(s);
      })
    : users;

  // Build tree structure for tree view
  const userTree = useMemo(() => {
    const rootUsers = filteredUsers.filter((u) => !u.parent_id);
    const childrenMap: Record<string, User[]> = {};
    filteredUsers.forEach((u) => {
      if (u.parent_id) {
        if (!childrenMap[u.parent_id]) childrenMap[u.parent_id] = [];
        childrenMap[u.parent_id].push(u);
      }
    });
    return { rootUsers, childrenMap };
  }, [filteredUsers]);

  const handleCreateUser = async (data: any) => {
    try {
      await usersApi.create(data);
      setShowCreateModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '유저 생성에 실패했습니다.');
    }
  };

  const openEdit = (user: User) => {
    setEditingUser(user);
    setEditForm({ name: user.name, phone: user.phone, role: user.role, is_active: user.is_active });
    setShowEditModal(true);
  };

  const handleUpdate = async () => {
    if (!editingUser) return;
    setEditLoading(true);
    try {
      await usersApi.update(editingUser.id, editForm);
      setShowEditModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '수정에 실패했습니다.');
    } finally {
      setEditLoading(false);
    }
  };

  const handleDelete = async (userId: string) => {
    if (!confirm('이 유저를 삭제하시겠습니까?')) return;
    try {
      await usersApi.delete(userId);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '삭제에 실패했습니다.');
    }
  };

  const renderTreeNode = (user: User, depth: number = 0) => (
    <div key={user.id}>
      <div
        className={`flex items-center justify-between px-4 py-2.5 hover:bg-gray-50 transition-colors`}
        style={{ paddingLeft: `${16 + depth * 24}px` }}
      >
        <div className="flex items-center gap-3">
          {depth > 0 && <span className="text-gray-300">└</span>}
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-900 text-sm">{user.name}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${roleColors[user.role] || ''}`}>
                {getRoleLabel(user.role)}
              </span>
              {!user.is_active && <Badge variant="default">비활성</Badge>}
            </div>
            <p className="text-xs text-gray-500">{user.email}{user.company ? ` · ${user.company.name}` : ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => openEdit(user)} className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded">
            <PencilSquareIcon className="h-4 w-4" />
          </button>
          <button onClick={() => handleDelete(user.id)} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded">
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
      {userTree.childrenMap[user.id]?.map((child) => renderTreeNode(child, depth + 1))}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">유저 관리</h1>
          <p className="mt-1 text-sm text-gray-500">유저 목록을 조회하고 관리합니다.</p>
        </div>
        <div className="flex gap-2">
          <div className="flex rounded-lg border border-gray-300 overflow-hidden">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-2 text-sm ${viewMode === 'list' ? 'bg-primary-500 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              <ListBulletIcon className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('tree')}
              className={`px-3 py-2 text-sm ${viewMode === 'tree' ? 'bg-primary-500 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              <Squares2X2Icon className="h-4 w-4" />
            </button>
          </div>
          <Button onClick={() => setShowCreateModal(true)} icon={<PlusIcon className="h-4 w-4" />}>
            유저 생성
          </Button>
        </div>
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
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value as UserRole | ''); setPage(1); }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          {roleFilterOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      {/* Content */}
      {viewMode === 'tree' ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm divide-y divide-gray-100">
          {loading ? (
            <div className="animate-pulse p-4 space-y-3">
              {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-gray-200 rounded" />)}
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="p-8 text-center text-gray-500 text-sm">유저가 없습니다.</div>
          ) : (
            userTree.rootUsers.map((user) => renderTreeNode(user))
          )}
        </div>
      ) : (
        <UserList users={filteredUsers} loading={loading} onEdit={(user) => { openEdit(user); }} />
      )}

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalItems={totalItems}
        pageSize={20}
      />

      {/* Create Modal */}
      <Modal isOpen={showCreateModal} onClose={() => setShowCreateModal(false)} title="유저 생성" size="md">
        <UserForm companies={companies} onSubmit={handleCreateUser} onCancel={() => setShowCreateModal(false)} />
      </Modal>

      {/* Edit Modal */}
      <Modal isOpen={showEditModal} onClose={() => setShowEditModal(false)} title="유저 수정" size="md">
        {editingUser && (
          <div className="space-y-4 p-1">
            <Input
              label="이름"
              value={editForm.name || ''}
              onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
            />
            <Input
              label="전화번호"
              value={editForm.phone || ''}
              onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
            />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">역할</label>
              <select
                value={editForm.role || editingUser.role}
                onChange={(e) => setEditForm({ ...editForm, role: e.target.value as UserRole })}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {roleFilterOptions.filter((o) => o.value).map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={editForm.is_active ?? editingUser.is_active}
                onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-gray-700">활성</span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setShowEditModal(false)}>취소</Button>
              <Button onClick={handleUpdate} loading={editLoading}>수정</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
