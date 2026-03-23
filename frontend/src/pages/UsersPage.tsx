import { useState, useEffect, useMemo, useCallback } from 'react';
import UserList from '@/components/features/users/UserList';
import UserForm from '@/components/features/users/UserForm';
import Pagination from '@/components/common/Pagination';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import Badge from '@/components/common/Badge';
import { pricesApi, type UserMatrixResponse } from '@/api/prices';
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
import { useAuthStore } from '@/store/auth';

const PARENT_ROLE_MAP: Record<string, { parentRole: string; label: string }> = {
  distributor: { parentRole: 'order_handler', label: '상위 담당자' },
  sub_account: { parentRole: 'distributor', label: '상위 총판' },
};
const roleFilterOptions = [
  { value: '', label: '전체 역할' },
  { value: 'system_admin', label: '시스템 관리자' },
  { value: 'company_admin', label: '회사 관리자' },
  { value: 'order_handler', label: '운영자' },
  { value: 'distributor', label: '총판' },
  { value: 'sub_account', label: '하부계정' },
];

const roleColors: Record<string, string> = {
  system_admin: 'text-red-600 bg-red-900/20',
  company_admin: 'text-blue-400 bg-blue-900/20',
  order_handler: 'text-green-600 bg-green-900/20',
  distributor: 'text-purple-600 bg-purple-900/20',
  sub_account: 'text-gray-400 bg-surface-raised',
};

export default function UsersPage() {
  const currentUser = useAuthStore((s) => s.user);
  const canEditUsers = currentUser?.role === 'system_admin' || currentUser?.role === 'company_admin';
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
  const [editParentCandidates, setEditParentCandidates] = useState<User[]>([]);
  const [editParentLoading, setEditParentLoading] = useState(false);
  const [editTab, setEditTab] = useState<'basic' | 'pricing'>('basic');
  const [userPriceProducts, setUserPriceProducts] = useState<UserMatrixResponse['products']>([]);
  const [userPriceMap, setUserPriceMap] = useState<Record<string, Record<string, number>>>({});
  const [editedUserPrices, setEditedUserPrices] = useState<Record<string, number>>({});
  const [priceCategory, setPriceCategory] = useState('__all__');
  const [userPriceLoading, setUserPriceLoading] = useState(false);
  const [userPriceSaving, setUserPriceSaving] = useState(false);

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

  const priceCategories = useMemo(() => {
    const names = new Set<string>();
    for (const product of userPriceProducts) {
      if (product.category) names.add(product.category);
    }
    return Array.from(names);
  }, [userPriceProducts]);

  const currentEditedRole = (editForm.role || editingUser?.role) as UserRole | undefined;
  const canConfigureUserPrices = !!editingUser && ['order_handler', 'distributor', 'sub_account'].includes(currentEditedRole || '');
  const currentUserPrices = editingUser ? (userPriceMap[editingUser.id] || {}) : {};
  const filteredPriceProducts = useMemo(() => {
    if (priceCategory === '__all__') return userPriceProducts;
    return userPriceProducts.filter((product) => product.category === priceCategory);
  }, [priceCategory, userPriceProducts]);

  const handleCreateUser = async (data: any) => {
    try {
      await usersApi.create(data);
      setShowCreateModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '유저 생성에 실패했습니다.');
    }
  };

  const loadParentCandidates = useCallback(async (role: string, companyId?: number) => {
    const config = PARENT_ROLE_MAP[role];
    if (!config) {
      setEditParentCandidates([]);
      return;
    }
    setEditParentLoading(true);
    try {
      const params: { role: string; company_id?: number; size: number } = {
        role: config.parentRole,
        size: 100,
      };
      if (companyId) params.company_id = companyId;
      const res = await usersApi.list(params);
      setEditParentCandidates(res.items);
    } catch {
      setEditParentCandidates([]);
    } finally {
      setEditParentLoading(false);
    }
  }, []);

  const openEdit = (user: User, tab: 'basic' | 'pricing' = 'basic') => {
    setEditingUser(user);
    setEditForm({
      name: user.name,
      phone: user.phone,
      role: user.role,
      parent_id: user.parent_id || undefined,
      is_active: user.is_active,
    });
    setEditTab(tab);
    setUserPriceProducts([]);
    setUserPriceMap({});
    setEditedUserPrices({});
    setPriceCategory('__all__');
    setShowEditModal(true);
    loadParentCandidates(user.role, user.company_id);
  };

  const openPriceEdit = (user: User) => {
    openEdit(user, 'pricing');
    // Eagerly load prices to avoid flash of empty state
    void loadUserPrices(user);
  };

  const closeEditModal = () => {
    setShowEditModal(false);
    setEditingUser(null);
    setEditTab('basic');
    setUserPriceProducts([]);
    setUserPriceMap({});
    setEditedUserPrices({});
    setPriceCategory('__all__');
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

  const loadUserPrices = useCallback(async (targetUser?: User | null) => {
    const user = targetUser || editingUser;
    if (!user) return;
    setUserPriceLoading(true);
    try {
      const data = await pricesApi.getUserMatrix();
      setUserPriceProducts(data.products);
      setUserPriceMap(data.prices);
      setEditedUserPrices(data.prices[user.id] || {});
    } catch (err: any) {
      alert(err?.response?.data?.detail || '단가 정보를 불러오지 못했습니다.');
    } finally {
      setUserPriceLoading(false);
    }
  }, [editingUser]);

  useEffect(() => {
    if (!showEditModal || editTab !== 'pricing' || !canConfigureUserPrices || !editingUser) return;
    // Skip if already loaded (e.g., from openPriceEdit eager load)
    if (userPriceProducts.length > 0 || userPriceLoading) return;
    void loadUserPrices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showEditModal, editTab, canConfigureUserPrices]);

  const hasPriceChanges = useMemo(() => {
    for (const product of userPriceProducts) {
      const effectivePrice = currentUserPrices[product.matrix_key] ?? product.base_price;
      const nextPrice = editedUserPrices[product.matrix_key] ?? effectivePrice;
      if (nextPrice !== effectivePrice) return true;
    }
    return false;
  }, [currentUserPrices, editedUserPrices, userPriceProducts]);

  const handleSaveUserPrices = async () => {
    if (!editingUser || !canConfigureUserPrices) return;
    setUserPriceSaving(true);
    try {
      for (const product of userPriceProducts) {
        const effectivePrice = currentUserPrices[product.matrix_key] ?? product.base_price;
        const nextPrice = editedUserPrices[product.matrix_key] ?? effectivePrice;
        if (nextPrice === effectivePrice) continue;

        await pricesApi.updatePrice(product.id, {
          user_id: editingUser.id,
          price: nextPrice,
          campaign_type: product.campaign_type_variant || undefined,
        });
      }

      const refreshed = await pricesApi.getUserMatrix();
      setUserPriceProducts(refreshed.products);
      setUserPriceMap(refreshed.prices);
      setEditedUserPrices(refreshed.prices[editingUser.id] || {});
    } catch (err: any) {
      alert(err?.response?.data?.detail || '단가 저장에 실패했습니다.');
    } finally {
      setUserPriceSaving(false);
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
        className={`flex items-center justify-between px-4 py-2.5 hover:bg-surface-raised transition-colors`}
        style={{ paddingLeft: `${16 + depth * 24}px` }}
      >
        <div className="flex items-center gap-3">
          {depth > 0 && <span className="text-gray-300">└</span>}
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-100 text-sm">{user.name}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${roleColors[user.role] || ''}`}>
                {getRoleLabel(user.role)}
              </span>
              {!user.is_active && <Badge variant="default">비활성</Badge>}
            </div>
            <p className="text-xs text-gray-400">{user.email}{user.company ? ` · ${user.company.name}` : ''}</p>
          </div>
        </div>
        {canEditUsers && (
          <div className="flex items-center gap-1">
            <button onClick={() => openEdit(user)} className="p-1.5 text-gray-400 hover:text-primary-400 hover:bg-primary-900/20 rounded">
              <PencilSquareIcon className="h-4 w-4" />
            </button>
            <button onClick={() => handleDelete(user.id)} className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-900/20 rounded">
              <TrashIcon className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
      {userTree.childrenMap[user.id]?.map((child) => renderTreeNode(child, depth + 1))}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">유저 관리</h1>
          <p className="mt-1 text-sm text-gray-400">유저 목록을 조회하고 관리합니다.</p>
        </div>
        <div className="flex gap-2">
          <div className="flex rounded-lg border border-border-strong overflow-hidden bg-surface text-gray-200">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-2 text-sm ${viewMode === 'list' ? 'bg-primary-500 text-white' : 'text-gray-400 hover:bg-surface-raised'}`}
            >
              <ListBulletIcon className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('tree')}
              className={`px-3 py-2 text-sm ${viewMode === 'tree' ? 'bg-primary-500 text-white' : 'text-gray-400 hover:bg-surface-raised'}`}
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
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-border-strong text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value as UserRole | ''); setPage(1); }}
          className="rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
        >
          {roleFilterOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-red-400 text-sm">{error}</div>
      )}

      {!canEditUsers && (
        <div className="rounded-lg border border-primary-800 bg-primary-900/20 p-3 text-sm text-primary-200">
          총판과 하부 계정 생성은 가능하지만, 기존 계정 수정과 비활성화는 회사 관리자 이상만 처리할 수 있습니다.
        </div>
      )}

      {/* Content */}
      {viewMode === 'tree' ? (
        <div className="bg-surface rounded-xl border border-border shadow-sm divide-y divide-border-subtle">
          {loading ? (
            <div className="animate-pulse p-4 space-y-3">
              {[1, 2, 3].map((i) => <div key={i} className="h-10 bg-surface-raised rounded" />)}
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">유저가 없습니다.</div>
          ) : (
            userTree.rootUsers.map((user) => renderTreeNode(user))
          )}
        </div>
      ) : (
        <UserList
          users={filteredUsers}
          allUsers={users}
          loading={loading}
          onEdit={canEditUsers ? (user) => { openEdit(user); } : undefined}
        />
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
      <Modal isOpen={showEditModal && canEditUsers} onClose={closeEditModal} title="유저 수정" size="xl">
        {editingUser && (
          <div className="space-y-5 p-1">
            <div className="rounded-xl border border-border bg-surface-raised p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-base font-semibold text-gray-100">{editingUser.name}</div>
                  <div className="mt-1 text-sm text-gray-400">{editingUser.email}</div>
                </div>
                <div className={`rounded px-2 py-1 text-xs ${roleColors[currentEditedRole || editingUser.role] || ''}`}>
                  {getRoleLabel(currentEditedRole || editingUser.role)}
                </div>
              </div>
            </div>

            <div className="flex gap-2 border-b border-border">
              <button
                type="button"
                onClick={() => setEditTab('basic')}
                className={`rounded-t-lg px-4 py-2 text-sm font-medium ${
                  editTab === 'basic'
                    ? 'border border-border border-b-surface bg-surface text-gray-100'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                기본 정보
              </button>
              {canConfigureUserPrices && (
                <button
                  type="button"
                  onClick={() => setEditTab('pricing')}
                  className={`rounded-t-lg px-4 py-2 text-sm font-medium ${
                    editTab === 'pricing'
                      ? 'border border-border border-b-surface bg-surface text-gray-100'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  단가 설정
                </button>
              )}
            </div>

            {editTab === 'basic' ? (
              <>
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
              <label className="block text-sm font-medium text-gray-300 mb-1">역할</label>
              <select
                value={currentEditedRole || editingUser.role}
                onChange={(e) => {
                  const newRole = e.target.value as UserRole;
                  setEditForm({ ...editForm, role: newRole, parent_id: undefined });
                  loadParentCandidates(newRole, editingUser.company_id);
                }}
                className="w-full rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
              >
                {roleFilterOptions.filter((o) => o.value).map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            {PARENT_ROLE_MAP[currentEditedRole || editingUser.role] && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  {PARENT_ROLE_MAP[currentEditedRole || editingUser.role].label}
                </label>
                <select
                  value={editForm.parent_id || ''}
                  onChange={(e) => setEditForm({ ...editForm, parent_id: e.target.value || null })}
                  className="w-full rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                  disabled={editParentLoading}
                >
                  <option value="">
                    {editParentLoading ? '로딩 중...' : '선택하세요'}
                  </option>
                  {editParentCandidates.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name} ({u.email})
                    </option>
                  ))}
                </select>
                {!editParentLoading && editParentCandidates.length === 0 && (
                  <p className="mt-1 text-xs text-amber-600">
                    해당 역할의 상위 유저가 없습니다.
                  </p>
                )}
              </div>
            )}
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={editForm.is_active ?? editingUser.is_active}
                onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                className="rounded border-border-strong text-primary-400 focus:ring-primary-400/40"
              />
              <span className="text-sm text-gray-300">활성</span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={closeEditModal}>취소</Button>
              <Button onClick={handleUpdate} loading={editLoading}>수정</Button>
            </div>
              </>
            ) : (
              <div className="space-y-4">
                <div className="rounded-xl border border-border bg-surface-raised p-4">
                  <div className="text-sm font-medium text-gray-100">단가 설정</div>
                  <p className="mt-1 text-xs text-gray-400">
                    사용자별 적용 단가를 직접 지정합니다. 일류 리워드는 트래픽과 저장하기가 따로 보입니다.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setPriceCategory('__all__')}
                    className={`rounded-full px-3 py-1.5 text-sm ${
                      priceCategory === '__all__'
                        ? 'bg-primary-500 text-white'
                        : 'bg-surface-raised text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    전체
                  </button>
                  {priceCategories.map((category) => (
                    <button
                      key={category}
                      type="button"
                      onClick={() => setPriceCategory(category)}
                      className={`rounded-full px-3 py-1.5 text-sm ${
                        priceCategory === category
                          ? 'bg-primary-500 text-white'
                          : 'bg-surface-raised text-gray-400 hover:text-gray-200'
                      }`}
                    >
                      {category}
                    </button>
                  ))}
                </div>

                {userPriceLoading ? (
                  <div className="rounded-xl border border-border bg-surface-raised p-6 text-center text-sm text-gray-400">
                    단가 정보를 불러오는 중입니다.
                  </div>
                ) : filteredPriceProducts.length === 0 ? (
                  <div className="rounded-xl border border-border bg-surface-raised p-6 text-center text-sm text-gray-400">
                    설정할 단가가 없습니다.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {filteredPriceProducts.map((product) => {
                      const effectivePrice = currentUserPrices[product.matrix_key] ?? product.base_price;
                      const currentPrice = editedUserPrices[product.matrix_key] ?? effectivePrice;
                      const deltaPercent =
                        product.base_price > 0
                          ? Math.round((1 - currentPrice / product.base_price) * 100)
                          : 0;

                      return (
                        <div key={product.matrix_key} className="flex items-center gap-3 rounded-xl border border-border bg-surface-raised p-3">
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-gray-100">{product.name}</div>
                            <div className="mt-1 text-xs text-gray-400">
                              기본 단가 {product.base_price.toLocaleString()}원
                            </div>
                          </div>
                          <input
                            type="number"
                            min={0}
                            value={currentPrice}
                            onChange={(e) =>
                              setEditedUserPrices((prev) => ({
                                ...prev,
                                [product.matrix_key]: parseInt(e.target.value, 10) || 0,
                              }))
                            }
                            className="w-32 rounded-lg border border-border-strong bg-surface px-3 py-2 text-right text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40"
                          />
                          <div className="w-16 text-right text-xs">
                            {deltaPercent > 0 && <span className="text-red-400">-{deltaPercent}%</span>}
                            {deltaPercent < 0 && <span className="text-emerald-400">+{Math.abs(deltaPercent)}%</span>}
                            {deltaPercent === 0 && <span className="text-gray-500">기본</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" onClick={closeEditModal}>취소</Button>
                  <Button
                    onClick={handleSaveUserPrices}
                    loading={userPriceSaving}
                    disabled={userPriceLoading || !hasPriceChanges}
                  >
                    저장하기
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
