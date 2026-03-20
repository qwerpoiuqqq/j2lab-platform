import { useState, useEffect, useMemo } from 'react';
import Button from '@/components/common/Button';
import Badge from '@/components/common/Badge';
import Modal from '@/components/common/Modal';
import { formatCurrency } from '@/utils/format';
import { pricesApi } from '@/api/prices';
import { categoriesApi } from '@/api/categories';
import { productsApi } from '@/api/products';
import { campaignAccountsApi } from '@/api/campaignAccounts';
import { networkPresetsApi } from '@/api/networkPresets';
import { useAuthStore } from '@/store/auth';
import type { Category, Product, SuperapAccount, NetworkPreset } from '@/types';
import type { RoleMatrixRow } from '@/api/prices';

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

type Tab = 'role' | 'user' | 'margin';

// ---------------------------------------------------------------------------
// Margin color helper
// ---------------------------------------------------------------------------

function getMarginColor(marginPct: number): string {
  if (marginPct >= 40) return 'text-emerald-400';
  if (marginPct >= 20) return 'text-cyan-400';
  if (marginPct > 0) return 'text-amber-400';
  return 'text-red-400';
}

// ---------------------------------------------------------------------------
// MarginAnalysisTable
// ---------------------------------------------------------------------------

interface MarginRow {
  product: Product;
  accounts: SuperapAccount[];
  presets: NetworkPreset[];
}

function MarginAnalysisTable({
  rows,
  canEdit,
  onUpdateHiddenMarginRate,
}: {
  rows: MarginRow[];
  canEdit: boolean;
  onUpdateHiddenMarginRate: (productId: number, rate: number) => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState<number>(0);
  const [saving, setSaving] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const handleStartEdit = (product: Product) => {
    if (!canEdit) return;
    setEditingId(product.id);
    setEditValue(product.hidden_margin_rate ?? 0);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
  };

  const handleSaveEdit = async (productId: number) => {
    setSaving(true);
    try {
      await onUpdateHiddenMarginRate(productId, editValue);
      setEditingId(null);
    } catch {
      // error handled by parent
    } finally {
      setSaving(false);
    }
  };

  const toggleExpand = (productId: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(productId)) {
        next.delete(productId);
      } else {
        next.add(productId);
      }
      return next;
    });
  };

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
                기본 판매단가
              </th>
              <th className="text-right px-4 py-3 text-gray-400 font-medium whitespace-nowrap">
                참고원가
              </th>
              <th className="text-center px-4 py-3 text-gray-400 font-medium whitespace-nowrap">
                세팅 감산 비율
              </th>
              <th className="text-center px-4 py-3 text-gray-400 font-medium whitespace-nowrap">
                실세팅 비율
              </th>
              <th className="text-right px-4 py-3 text-gray-400 font-medium whitespace-nowrap">
                판매 마진율
              </th>
              <th className="text-center px-4 py-3 text-gray-400 font-medium whitespace-nowrap w-10">
                네트워크
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              const { product, accounts, presets } = row;
              const hiddenRate = product.hidden_margin_rate ?? 0;
              const actualSettingPct = 100 - hiddenRate;
              const basePrice = product.base_price;
              const costPrice = product.cost_price;
              const marginPct =
                basePrice > 0 && costPrice != null
                  ? ((basePrice - costPrice) / basePrice) * 100
                  : null;
              const isExpanded = expandedIds.has(product.id);
              const hasNetworkData = accounts.length > 0 || presets.length > 0;

              return (
                <>
                  <tr
                    key={product.id}
                    className={`border-b border-border-subtle hover:bg-surface-raised/50 transition-colors ${
                      idx % 2 === 0 ? '' : 'bg-surface-raised/20'
                    }`}
                  >
                    {/* 상품명 */}
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-100">{product.name}</div>
                      {product.code && (
                        <div className="text-xs text-gray-500 mt-0.5">{product.code}</div>
                      )}
                    </td>

                    {/* 기본 판매단가 */}
                    <td className="px-4 py-3 text-right text-gray-300 font-mono whitespace-nowrap">
                      {formatCurrency(basePrice)}
                    </td>

                    {/* 참고원가 */}
                    <td className="px-4 py-3 text-right font-mono whitespace-nowrap">
                      {costPrice != null ? (
                        <span className="text-gray-300">{formatCurrency(costPrice)}</span>
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>

                    {/* 세팅 감산 비율 */}
                    <td className="px-4 py-3 text-center">
                      {editingId === product.id ? (
                        <div className="flex items-center justify-center gap-1">
                          <input
                            type="number"
                            min={0}
                            max={100}
                            value={editValue}
                            onChange={(e) =>
                              setEditValue(Math.min(100, Math.max(0, parseInt(e.target.value) || 0)))
                            }
                            className="w-16 px-2 py-1 text-center text-xs border border-border-strong rounded bg-surface text-gray-200 font-mono focus:outline-none focus:ring-1 focus:ring-primary-400/40"
                            autoFocus
                          />
                          <span className="text-xs text-gray-400">%</span>
                          <button
                            onClick={() => handleSaveEdit(product.id)}
                            disabled={saving}
                            className="text-xs text-emerald-400 hover:text-emerald-300 font-medium px-1"
                          >
                            {saving ? '...' : '저장'}
                          </button>
                          <button
                            onClick={handleCancelEdit}
                            className="text-xs text-gray-500 hover:text-gray-300 px-1"
                          >
                            취소
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleStartEdit(product)}
                          disabled={!canEdit}
                          title={canEdit ? '클릭하여 수정' : undefined}
                          className={canEdit ? 'hover:opacity-80 transition-opacity' : 'cursor-default'}
                        >
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-900/40 text-purple-400">
                            {hiddenRate}%
                            {canEdit && (
                              <svg
                                className="w-3 h-3 opacity-60"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                                />
                              </svg>
                            )}
                          </span>
                        </button>
                      )}
                    </td>

                    {/* 실세팅 비율 */}
                    <td className="px-4 py-3 text-center">
                      <span className="text-sm text-gray-300">
                        {actualSettingPct}타/100타
                      </span>
                    </td>

                    {/* 판매 마진율 */}
                    <td className="px-4 py-3 text-right font-mono whitespace-nowrap">
                      {marginPct != null ? (
                        <span className={`font-semibold ${getMarginColor(marginPct)}`}>
                          {marginPct.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-gray-600">—</span>
                      )}
                    </td>

                    {/* 네트워크 토글 */}
                    <td className="px-4 py-3 text-center">
                      {hasNetworkData ? (
                        <button
                          onClick={() => toggleExpand(product.id)}
                          className="text-gray-500 hover:text-gray-300 transition-colors"
                          title="네트워크별 원가 보기"
                        >
                          <svg
                            className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M19 9l-7 7-7-7"
                            />
                          </svg>
                        </button>
                      ) : (
                        <span className="text-gray-700">—</span>
                      )}
                    </td>
                  </tr>

                  {/* 접이식 네트워크 패널 */}
                  {isExpanded && hasNetworkData && (
                    <tr key={`${product.id}-network`} className="bg-surface-raised/40">
                      <td colSpan={7} className="px-6 py-3">
                        <div className="space-y-2">
                          {accounts.length > 0 && (
                            <div>
                              <p className="text-xs text-gray-500 mb-1 font-medium uppercase tracking-wide">
                                슈퍼앱 계정별 원가
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {accounts.map((acc) => (
                                  <div
                                    key={acc.id}
                                    className="bg-surface rounded-lg border border-border-subtle px-3 py-1.5 text-xs"
                                  >
                                    <span className="text-gray-400 mr-1">{acc.user_id_superap}</span>
                                    <span className="text-cyan-400 font-mono">
                                      트래픽 {formatCurrency(acc.unit_cost_traffic)}
                                    </span>
                                    <span className="text-gray-600 mx-1">/</span>
                                    <span className="text-blue-400 font-mono">
                                      저장 {formatCurrency(acc.unit_cost_save)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {presets.length > 0 && (
                            <div>
                              <p className="text-xs text-gray-500 mb-1 font-medium uppercase tracking-wide">
                                네트워크 프리셋
                              </p>
                              <div className="flex flex-wrap gap-2">
                                {presets.map((preset) => (
                                  <div
                                    key={preset.id}
                                    className="bg-surface rounded-lg border border-border-subtle px-3 py-1.5 text-xs"
                                  >
                                    <span className="text-gray-400 mr-1">{preset.name}</span>
                                    {preset.cost_price != null ? (
                                      <span className="text-amber-400 font-mono">
                                        {formatCurrency(preset.cost_price)}
                                      </span>
                                    ) : (
                                      <span className="text-gray-600">원가 미설정</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-2 border-t border-border-subtle bg-surface-raised/30">
        <p className="text-xs text-gray-500">
          <span className="text-purple-400 font-medium">세팅 감산 비율</span> = 주문 타수 중 실제 세팅에서 제외되는 내부 비율.
          {canEdit && ' 클릭하면 수정할 수 있습니다 (system_admin 전용).'}
          {' '}
          <span className="text-emerald-400">≥40%</span>
          <span className="text-gray-600 mx-1">/</span>
          <span className="text-cyan-400">20~40%</span>
          <span className="text-gray-600 mx-1">/</span>
          <span className="text-amber-400">0~20%</span>
          <span className="text-gray-600 mx-1">/</span>
          <span className="text-red-400">0% 이하</span>
        </p>
      </div>
    </div>
  );
}

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
  const { user } = useAuthStore();

  // Role-based access
  const canViewMargin = ['system_admin', 'company_admin', 'order_handler'].includes(
    user?.role || '',
  );
  const canEditMargin = user?.role === 'system_admin';

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

  // ---- Margin Analysis data ----
  const [marginProducts, setMarginProducts] = useState<Product[]>([]);
  const [marginAccounts, setMarginAccounts] = useState<SuperapAccount[]>([]);
  const [marginPresets, setMarginPresets] = useState<NetworkPreset[]>([]);
  const [marginLoading, setMarginLoading] = useState(false);
  const [marginError, setMarginError] = useState<string | null>(null);
  const [marginFetched, setMarginFetched] = useState(false);

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

  // ---- Fetch margin data (lazy) ----
  useEffect(() => {
    if (activeTab !== 'margin' || marginFetched || !canViewMargin) return;

    let cancelled = false;
    setMarginLoading(true);
    setMarginError(null);

    Promise.all([
      productsApi.list({ size: 200, is_active: true }),
      campaignAccountsApi.list({ size: 200, is_active: true }),
      networkPresetsApi.list({ size: 200, is_active: true }),
    ])
      .then(([productsRes, accountsRes, presetsRes]) => {
        if (cancelled) return;
        setMarginProducts(productsRes.items);
        setMarginAccounts(accountsRes.items);
        setMarginPresets(presetsRes.items);
        setMarginLoading(false);
        setMarginFetched(true);
      })
      .catch((err) => {
        if (cancelled) return;
        setMarginError(err?.response?.data?.detail || '마진 분석 데이터를 불러오지 못했습니다.');
        setMarginLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeTab, marginFetched, canViewMargin]);

  // ---- Margin rows (memoized) ----
  const marginRows: MarginRow[] = useMemo(() => {
    return marginProducts.map((product) => ({
      product,
      accounts: marginAccounts,
      presets: marginPresets,
    }));
  }, [marginProducts, marginAccounts, marginPresets]);

  // ---- Update hidden_margin_rate ----
  const handleUpdateHiddenMarginRate = async (productId: number, rate: number) => {
    try {
      await productsApi.update(productId, { hidden_margin_rate: rate });
      setMarginProducts((prev) =>
        prev.map((p) =>
          p.id === productId ? { ...p, hidden_margin_rate: rate } : p,
        ),
      );
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
      throw err;
    }
  };

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
        {canViewMargin && (
          <button
            onClick={() => setActiveTab('margin')}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'margin'
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            세팅 감산/마진 분석
          </button>
        )}
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
      {/* Tab: 세팅 감산/마진 분석                                         */}
      {/* ================================================================= */}
      {activeTab === 'margin' && canViewMargin && (
        <>
          {marginLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="animate-pulse bg-surface-raised rounded-xl h-14" />
              ))}
            </div>
          ) : marginError ? (
            <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-red-400 text-sm">
              {marginError}
            </div>
          ) : (
            <>
              <div className="bg-purple-900/20 border border-purple-800/40 rounded-lg px-4 py-3 text-sm text-purple-300">
                판매가 대비 원가 기준 판매 마진율과 실세팅 감산 비율을 함께 표시합니다.
                {canEditMargin && (
                  <> <strong>세팅 감산 비율</strong>을 클릭하면 인라인 수정할 수 있습니다.</>
                )}
              </div>
              <MarginAnalysisTable
                rows={marginRows}
                canEdit={canEditMargin}
                onUpdateHiddenMarginRate={handleUpdateHiddenMarginRate}
              />
            </>
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
