import { useState, useEffect, useMemo } from 'react';
import Button from '@/components/common/Button';
import Badge from '@/components/common/Badge';
import Modal from '@/components/common/Modal';
import { formatCurrency } from '@/utils/format';
import { pricesApi } from '@/api/prices';
import { categoriesApi } from '@/api/categories';
import type { Category } from '@/types';
import type { RoleMatrixRow, UserMatrixResponse } from '@/api/prices';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ROLE_LABELS: Record<string, string> = {
  company_admin: '경리',
  order_handler: '담당자',
  distributor: '총판',
  sub_account: '셀러',
};

const ROLE_COLORS: Record<string, string> = {
  company_admin: 'text-yellow-400',
  order_handler: 'text-orange-400',
  distributor: 'text-blue-400',
  sub_account: 'text-green-400',
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MatrixUser {
  id: string;
  name: string;
  role: string;
  email: string;
}

interface MatrixProduct {
  id: number;
  name: string;
  code: string;
  category?: string;
  base_price: number;
}

type Tab = 'role' | 'user';

// ---------------------------------------------------------------------------
// UserCard (유저별 단가 탭용)
// ---------------------------------------------------------------------------

function UserCard({
  user,
  priceCount,
  onConfigure,
}: {
  user: MatrixUser;
  priceCount: number;
  onConfigure: () => void;
}) {
  const roleColors: Record<string, string> = {
    distributor: 'bg-blue-500',
    sub_account: 'bg-green-500',
  };
  const roleLabels: Record<string, string> = {
    distributor: '총판',
    sub_account: '셀러',
  };

  return (
    <div className="bg-surface rounded-xl border border-border shadow-sm p-5 hover:shadow-md transition-shadow">
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`w-10 h-10 rounded-full ${roleColors[user.role] || 'bg-surface-raised'} flex items-center justify-center text-white font-bold text-sm`}
        >
          {user.name.charAt(0)}
        </div>
        <div>
          <h3 className="font-semibold text-gray-100">{user.name}</h3>
          <Badge variant={user.role === 'distributor' ? 'primary' : 'success'}>
            {roleLabels[user.role] || user.role}
          </Badge>
        </div>
      </div>
      <p className="text-sm text-gray-400 mb-1">{user.email}</p>
      <p className="text-sm text-gray-400 mb-3">
        {priceCount > 0 ? `${priceCount}개 개별 단가 설정됨` : '기본 단가 적용 중'}
      </p>
      <Button size="sm" variant="secondary" onClick={onConfigure} className="w-full">
        설정하기
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RoleMatrixTable (역할별 단가 탭용)
// ---------------------------------------------------------------------------

function RoleMatrixTable({
  rows,
  roles,
  onEdit,
}: {
  rows: RoleMatrixRow[];
  roles: { id: string; name: string }[];
  onEdit: (row: RoleMatrixRow, roleId: string) => void;
}) {
  if (rows.length === 0) {
    return (
      <div className="bg-surface rounded-xl border border-border p-8 text-center text-gray-400 text-sm">
        등록된 상품이 없습니다.
      </div>
    );
  }

  return (
    <div className="bg-surface rounded-xl border border-border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-raised">
              <th className="text-left px-4 py-3 text-gray-400 font-medium min-w-[200px]">
                상품명
              </th>
              <th className="text-right px-4 py-3 text-gray-400 font-medium whitespace-nowrap">
                기본 단가
              </th>
              {roles.map((role) => (
                <th
                  key={role.id}
                  className={`text-right px-4 py-3 font-medium whitespace-nowrap ${ROLE_COLORS[role.id] || 'text-gray-300'}`}
                >
                  {role.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr
                key={row.product_id}
                className={`border-b border-border-subtle hover:bg-surface-raised/50 transition-colors ${
                  idx % 2 === 0 ? '' : 'bg-surface-raised/20'
                }`}
              >
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-100">{row.product_name}</div>
                  {row.cost_price != null && (
                    <div className="text-xs text-gray-500 mt-0.5">
                      원가 {formatCurrency(row.cost_price)}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-right text-gray-300 font-mono whitespace-nowrap">
                  {formatCurrency(row.base_price)}
                </td>
                {roles.map((role) => {
                  const rolePrice = row.prices[role.id] ?? row.base_price;
                  const isCustom = rolePrice !== row.base_price;
                  const discountRate =
                    row.base_price > 0
                      ? Math.round((1 - rolePrice / row.base_price) * 100)
                      : 0;

                  return (
                    <td key={role.id} className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        onClick={() => onEdit(row, role.id)}
                        className={`inline-flex flex-col items-end gap-0.5 group hover:opacity-80 transition-opacity`}
                        title="클릭하여 편집"
                      >
                        <span
                          className={`font-mono font-medium ${
                            isCustom ? 'text-cyan-400' : 'text-gray-300'
                          }`}
                        >
                          {formatCurrency(rolePrice)}
                        </span>
                        {discountRate > 0 && (
                          <span className="text-xs text-red-400">-{discountRate}%</span>
                        )}
                        {discountRate < 0 && (
                          <span className="text-xs text-emerald-400">+{Math.abs(discountRate)}%</span>
                        )}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-2 border-t border-border-subtle bg-surface-raised/30">
        <p className="text-xs text-gray-500">
          <span className="text-cyan-400 font-medium">파란색</span> = 기본 단가와 다른 커스텀 단가.
          셀을 클릭하면 편집할 수 있습니다.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function PriceMatrixPage() {
  // ---- Tab ----
  const [activeTab, setActiveTab] = useState<Tab>('role');

  // ---- Role Matrix data ----
  const [roleRows, setRoleRows] = useState<RoleMatrixRow[]>([]);
  const [roleDefs, setRoleDefs] = useState<{ id: string; name: string }[]>([]);
  const [roleLoading, setRoleLoading] = useState(true);
  const [roleError, setRoleError] = useState<string | null>(null);

  // ---- User Matrix data ----
  const [matrixUsers, setMatrixUsers] = useState<MatrixUser[]>([]);
  const [matrixProducts, setMatrixProducts] = useState<MatrixProduct[]>([]);
  const [matrixPrices, setMatrixPrices] = useState<Record<string, Record<number, number>>>({});
  const [categories, setCategories] = useState<Category[]>([]);
  const [userLoading, setUserLoading] = useState(false);
  const [userError, setUserError] = useState<string | null>(null);

  // ---- Role edit modal ----
  const [roleEditOpen, setRoleEditOpen] = useState(false);
  const [roleEditRow, setRoleEditRow] = useState<RoleMatrixRow | null>(null);
  const [roleEditRoleId, setRoleEditRoleId] = useState<string>('');
  const [roleEditPrice, setRoleEditPrice] = useState<number>(0);
  const [roleEditSaving, setRoleEditSaving] = useState(false);

  // ---- User edit modal ----
  const [selectedUser, setSelectedUser] = useState<MatrixUser | null>(null);
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('__all__');
  const [editedPrices, setEditedPrices] = useState<Record<number, number>>({});
  const [userSaving, setUserSaving] = useState(false);

  // ---- Fetch role matrix ----
  useEffect(() => {
    let cancelled = false;
    setRoleLoading(true);
    setRoleError(null);

    pricesApi
      .getRoleMatrix()
      .then((res) => {
        if (cancelled) return;
        setRoleRows(res.rows);
        setRoleDefs(res.sellers);
        setRoleLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setRoleError(err?.response?.data?.detail || '역할별 단가를 불러오지 못했습니다.');
        setRoleLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // ---- Fetch user matrix (lazy: only when tab is first selected) ----
  const [userMatrixFetched, setUserMatrixFetched] = useState(false);

  useEffect(() => {
    if (activeTab !== 'user' || userMatrixFetched) return;

    let cancelled = false;
    setUserLoading(true);
    setUserError(null);

    Promise.all([
      pricesApi.getUserMatrix(),
      categoriesApi.list({ size: 100 }),
    ])
      .then(([matrixRes, categoriesRes]) => {
        if (cancelled) return;
        setMatrixUsers(matrixRes.users);
        setMatrixProducts(matrixRes.products);
        setMatrixPrices(matrixRes.prices);
        setCategories(categoriesRes.items);
        setUserLoading(false);
        setUserMatrixFetched(true);
      })
      .catch((err) => {
        if (cancelled) return;
        setUserError(err?.response?.data?.detail || '유저별 단가를 불러오지 못했습니다.');
        setUserLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeTab, userMatrixFetched]);

  // ---- Role edit handlers ----
  const handleOpenRoleEdit = (row: RoleMatrixRow, roleId: string) => {
    setRoleEditRow(row);
    setRoleEditRoleId(roleId);
    setRoleEditPrice(row.prices[roleId] ?? row.base_price);
    setRoleEditOpen(true);
  };

  const handleSaveRolePrice = async () => {
    if (!roleEditRow) return;
    setRoleEditSaving(true);
    try {
      await pricesApi.updatePrice(roleEditRow.product_id, {
        role: roleEditRoleId,
        price: roleEditPrice,
      });

      // Update local state
      setRoleRows((prev) =>
        prev.map((r) =>
          r.product_id === roleEditRow.product_id
            ? { ...r, prices: { ...r.prices, [roleEditRoleId]: roleEditPrice } }
            : r,
        ),
      );
      setRoleEditOpen(false);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setRoleEditSaving(false);
    }
  };

  // ---- User edit handlers ----
  const priceCounts = useMemo(() => {
    const baseMap = new Map(matrixProducts.map((p) => [p.id, p.base_price]));
    const counts: Record<string, number> = {};
    for (const [userId, prices] of Object.entries(matrixPrices)) {
      let custom = 0;
      for (const [pidStr, price] of Object.entries(prices)) {
        const base = baseMap.get(parseInt(pidStr)) || 0;
        if (price !== base) custom++;
      }
      counts[userId] = custom;
    }
    return counts;
  }, [matrixPrices, matrixProducts]);

  const handleConfigure = (user: MatrixUser) => {
    setSelectedUser(user);
    setUserModalOpen(true);
    setEditedPrices({});
    setSelectedCategory('__all__');
  };

  const currentUserPrices = useMemo(() => {
    if (!selectedUser) return {};
    return matrixPrices[selectedUser.id] || {};
  }, [selectedUser, matrixPrices]);

  const handleCloseUserModal = () => {
    setUserModalOpen(false);
    setSelectedUser(null);
    setEditedPrices({});
  };

  const handleSaveUserPrices = async () => {
    if (!selectedUser) return;
    setUserSaving(true);
    try {
      for (const [prodIdStr, price] of Object.entries(editedPrices)) {
        const productId = parseInt(prodIdStr);
        await pricesApi.updatePrice(productId, {
          user_id: selectedUser.id,
          price,
        });
      }

      setMatrixPrices((prev) => ({
        ...prev,
        [selectedUser.id]: { ...(prev[selectedUser.id] || {}), ...editedPrices },
      }));

      setEditedPrices({});
      handleCloseUserModal();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setUserSaving(false);
    }
  };

  const filteredProducts = useMemo(() => {
    if (!selectedCategory || selectedCategory === '__all__') return matrixProducts;
    return matrixProducts.filter((p) => p.category === selectedCategory);
  }, [matrixProducts, selectedCategory]);

  const hasUserChanges = Object.keys(editedPrices).length > 0;

  // =========================================================================
  // RENDER
  // =========================================================================

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">단가 설정</h1>
        <p className="mt-1 text-sm text-gray-400">
          역할별 기본 단가와 총판/셀러별 개별 단가를 관리합니다.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-raised rounded-xl p-1 w-fit">
        <button
          onClick={() => setActiveTab('role')}
          className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'role'
              ? 'bg-primary-600 text-white shadow-sm'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          역할별 단가
        </button>
        <button
          onClick={() => setActiveTab('user')}
          className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === 'user'
              ? 'bg-primary-600 text-white shadow-sm'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          유저별 단가
        </button>
      </div>

      {/* ================================================================= */}
      {/* Tab: 역할별 단가                                                  */}
      {/* ================================================================= */}
      {activeTab === 'role' && (
        <>
          {roleLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse bg-surface-raised rounded-xl h-14" />
              ))}
            </div>
          ) : roleError ? (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-red-400 text-sm">
              {roleError}
            </div>
          ) : (
            <>
              {/* Info banner */}
              <div className="bg-blue-900/20 border border-blue-800/40 rounded-lg px-4 py-3 text-sm text-blue-300">
                역할별 단가는 해당 역할의 모든 유저에게 기본 적용됩니다. 특정 유저에게 다른 단가를 적용하려면 <strong>유저별 단가</strong> 탭을 사용하세요.
              </div>

              <RoleMatrixTable
                rows={roleRows}
                roles={roleDefs}
                onEdit={handleOpenRoleEdit}
              />
            </>
          )}
        </>
      )}

      {/* ================================================================= */}
      {/* Tab: 유저별 단가                                                  */}
      {/* ================================================================= */}
      {activeTab === 'user' && (
        <>
          {userLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse bg-surface-raised rounded-xl h-40" />
              ))}
            </div>
          ) : userError ? (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-red-400 text-sm">
              {userError}
            </div>
          ) : matrixUsers.length === 0 ? (
            <div className="bg-surface rounded-xl border border-border p-8 text-center text-gray-400 text-sm">
              등록된 총판/셀러가 없습니다.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {matrixUsers.map((user) => (
                <UserCard
                  key={user.id}
                  user={user}
                  priceCount={priceCounts[user.id] || 0}
                  onConfigure={() => handleConfigure(user)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* ================================================================= */}
      {/* Role Edit Modal                                                   */}
      {/* ================================================================= */}
      <Modal
        isOpen={roleEditOpen}
        onClose={() => setRoleEditOpen(false)}
        title={
          roleEditRow
            ? `${roleEditRow.product_name} — ${ROLE_LABELS[roleEditRoleId] || roleEditRoleId} 단가`
            : '단가 편집'
        }
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRoleEditOpen(false)}>
              취소
            </Button>
            <Button onClick={handleSaveRolePrice} loading={roleEditSaving}>
              저장
            </Button>
          </>
        }
      >
        {roleEditRow && (
          <div className="space-y-4">
            <div className="bg-surface-raised rounded-lg px-4 py-3 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">상품</span>
                <span className="text-gray-200 font-medium">{roleEditRow.product_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">역할</span>
                <span className={`font-medium ${ROLE_COLORS[roleEditRoleId] || 'text-gray-300'}`}>
                  {ROLE_LABELS[roleEditRoleId] || roleEditRoleId}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">기본 단가</span>
                <span className="text-gray-300 font-mono">{formatCurrency(roleEditRow.base_price)}</span>
              </div>
              {roleEditRow.cost_price != null && (
                <div className="flex justify-between">
                  <span className="text-gray-400">원가</span>
                  <span className="text-gray-300 font-mono">{formatCurrency(roleEditRow.cost_price)}</span>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                {ROLE_LABELS[roleEditRoleId] || roleEditRoleId} 단가 (원)
              </label>
              <input
                type="number"
                min={0}
                value={roleEditPrice}
                onChange={(e) => setRoleEditPrice(parseInt(e.target.value) || 0)}
                className="w-full px-3 py-2 border border-border-strong rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200 text-right font-mono"
                autoFocus
              />
              {roleEditRow.base_price > 0 && roleEditPrice !== roleEditRow.base_price && (
                <p className="mt-1 text-xs text-gray-500">
                  기본 단가 대비{' '}
                  <span className={roleEditPrice < roleEditRow.base_price ? 'text-red-400' : 'text-emerald-400'}>
                    {roleEditPrice < roleEditRow.base_price ? '-' : '+'}
                    {Math.abs(Math.round((1 - roleEditPrice / roleEditRow.base_price) * 100))}%
                  </span>
                </p>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* ================================================================= */}
      {/* User Price Settings Modal                                         */}
      {/* ================================================================= */}
      <Modal
        isOpen={userModalOpen}
        onClose={handleCloseUserModal}
        title={selectedUser ? `${selectedUser.name}님의 단가 설정` : '단가 설정'}
        size="xl"
        footer={
          <>
            <Button variant="secondary" onClick={handleCloseUserModal}>
              취소
            </Button>
            <Button onClick={handleSaveUserPrices} loading={userSaving} disabled={!hasUserChanges}>
              저장
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {/* Category Tabs */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedCategory('__all__')}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                selectedCategory === '__all__'
                  ? 'bg-primary-600 text-white'
                  : 'bg-surface-raised text-gray-400 hover:text-gray-200'
              }`}
            >
              전체
            </button>
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.name)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  selectedCategory === cat.name
                    ? 'bg-primary-600 text-white'
                    : 'bg-surface-raised text-gray-400 hover:text-gray-200'
                }`}
              >
                {cat.name}
              </button>
            ))}
          </div>

          {/* Product price rows */}
          {filteredProducts.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              해당 카테고리에 상품이 없습니다.
            </div>
          ) : (
            <div className="space-y-2">
              {filteredProducts.map((product) => {
                const effectivePrice = currentUserPrices[product.id] ?? product.base_price;
                const currentPrice = editedPrices[product.id] ?? effectivePrice;
                const discountRate =
                  product.base_price > 0
                    ? Math.round((1 - currentPrice / product.base_price) * 100)
                    : 0;
                const isCustom = currentPrice !== product.base_price;

                return (
                  <div
                    key={product.id}
                    className={`flex items-center gap-3 p-3 rounded-lg ${
                      isCustom ? 'bg-blue-900/20' : 'bg-surface-raised'
                    }`}
                  >
                    <span className="flex-1 text-sm font-medium text-gray-100">
                      {product.name}
                    </span>
                    <span className="text-xs text-gray-400 bg-surface px-2 py-1 rounded whitespace-nowrap">
                      기본 {formatCurrency(product.base_price)}
                    </span>
                    <input
                      type="number"
                      value={currentPrice}
                      onChange={(e) =>
                        setEditedPrices((prev) => ({
                          ...prev,
                          [product.id]: parseInt(e.target.value) || 0,
                        }))
                      }
                      className="w-32 px-3 py-2 text-right text-sm border border-border-strong rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200 font-mono"
                    />
                    {discountRate > 0 && (
                      <span className="text-xs text-red-400 font-medium min-w-[60px] text-right">
                        -{discountRate}%
                      </span>
                    )}
                    {discountRate < 0 && (
                      <span className="text-xs text-emerald-400 font-medium min-w-[60px] text-right">
                        +{Math.abs(discountRate)}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
