import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  Squares2X2Icon,
  CubeIcon,
  ClipboardDocumentListIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { categoriesApi } from '@/api/categories';
import { productsApi } from '@/api/products';
import { ordersApi } from '@/api/orders';
import { pricesApi } from '@/api/prices';
import { campaignAccountsApi } from '@/api/campaignAccounts';
import { pointsApi } from '@/api/points';
import type { Product, OrderType, SuperapAccount } from '@/types';
import { formatCurrency } from '@/utils/format';
import { normalizeSchema } from '@/utils/schema';
import OrderGrid, { type OrderGridRow } from '@/components/features/orders/OrderGrid';
import Button from '@/components/common/Button';
import { useAuthStore } from '@/store/auth';
import { categoryIcons, CategoryIcon } from '@/components/common/CategoryIcons';

const orderTypeOptions: { value: OrderType; label: string }[] = [
  { value: 'regular', label: '일반' },
  { value: 'monthly_guarantee', label: '월보장' },
  { value: 'managed', label: '관리형' },
];

const visualTokenMap: Array<{ match: string[]; symbol: string; ring: string; glow: string; symbolBg: string; symbolText: string }> = [
  { match: ['네이버', '플레이스'], symbol: 'N', ring: 'border-emerald-200', glow: 'from-emerald-100 via-emerald-50 to-white', symbolBg: 'bg-emerald-500', symbolText: 'text-white' },
  { match: ['인스타'], symbol: '◎', ring: 'border-rose-200', glow: 'from-rose-100 via-orange-50 to-white', symbolBg: 'bg-gradient-to-br from-rose-500 to-orange-400', symbolText: 'text-white' },
  { match: ['유튜브'], symbol: '▶', ring: 'border-red-200', glow: 'from-red-100 via-rose-50 to-white', symbolBg: 'bg-red-500', symbolText: 'text-white' },
  { match: ['틱톡'], symbol: '♪', ring: 'border-cyan-200', glow: 'from-cyan-100 via-sky-50 to-white', symbolBg: 'bg-cyan-500', symbolText: 'text-white' },
  { match: ['카카오'], symbol: 'K', ring: 'border-yellow-200', glow: 'from-yellow-100 via-amber-50 to-white', symbolBg: 'bg-yellow-400', symbolText: 'text-gray-50' },
  { match: ['페이스북'], symbol: 'f', ring: 'border-blue-200', glow: 'from-blue-100 via-indigo-50 to-white', symbolBg: 'bg-blue-500', symbolText: 'text-white' },
  { match: ['쿠팡'], symbol: 'C', ring: 'border-orange-200', glow: 'from-orange-100 via-amber-50 to-white', symbolBg: 'bg-orange-500', symbolText: 'text-white' },
  { match: ['블로그'], symbol: 'B', ring: 'border-lime-200', glow: 'from-lime-100 via-emerald-50 to-white', symbolBg: 'bg-lime-500', symbolText: 'text-white' },
  { match: ['쇼핑'], symbol: 'S', ring: 'border-pink-200', glow: 'from-pink-100 via-rose-50 to-white', symbolBg: 'bg-pink-500', symbolText: 'text-white' },
  { match: ['트래픽'], symbol: '↑', ring: 'border-sky-200', glow: 'from-sky-100 via-blue-50 to-white', symbolBg: 'bg-sky-500', symbolText: 'text-white' },
  { match: ['저장'], symbol: '□', ring: 'border-violet-200', glow: 'from-violet-100 via-fuchsia-50 to-white', symbolBg: 'bg-violet-500', symbolText: 'text-white' },
  { match: ['자동완성'], symbol: 'A', ring: 'border-purple-200', glow: 'from-purple-100 via-violet-50 to-white', symbolBg: 'bg-purple-500', symbolText: 'text-white' },
  { match: ['영수증'], symbol: 'R', ring: 'border-stone-200', glow: 'from-stone-100 via-neutral-50 to-white', symbolBg: 'bg-stone-500', symbolText: 'text-white' },
];

interface CategoryBucket {
  key: string;
  name: string;
  description?: string;
  icon?: string;
  image_url?: string;
  sort_order: number;
  products: Product[];
}

function getVisualToken(label: string, icon?: string) {
  // 1. 관리자가 명시적으로 선택한 아이콘이 있으면 최우선 사용 (기본값 'grid' 제외)
  if (icon && icon !== 'grid') {
    const iconEntry = categoryIcons[icon];
    if (iconEntry) {
      return {
        symbol: icon,
        ring: 'border-slate-200',
        glow: 'from-slate-100 via-slate-50 to-white',
        symbolBg: iconEntry.bg,
        symbolText: iconEntry.text,
        isIconKey: true,
      };
    }
  }

  // 2. 카테고리 이름 기반 자동 매칭 (기본 아이콘이거나 선택 아이콘이 없을 때)
  const combined = `${label} ${icon || ''}`;
  const matched = visualTokenMap.find((item) => item.match.some((keyword) => combined.includes(keyword)));
  if (matched) return { ...matched, isIconKey: false };

  // 3. 'grid' 등 나머지 아이콘 키 매칭
  const iconEntry = categoryIcons[icon || ''];
  if (iconEntry) {
    return {
      symbol: icon || '',
      ring: 'border-slate-200',
      glow: 'from-slate-100 via-slate-50 to-white',
      symbolBg: iconEntry.bg,
      symbolText: iconEntry.text,
      isIconKey: true,
    };
  }

  // 4. 최종 폴백: 카테고리 이름 첫 글자
  return {
    symbol: label.trim().charAt(0) || '•',
    ring: 'border-slate-200',
    glow: 'from-slate-100 via-slate-50 to-white',
    symbolBg: 'bg-slate-700',
    symbolText: 'text-white',
    isIconKey: false,
  };
}

export default function OrderGridPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'system_admin' || user?.role === 'company_admin';
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [orderSubmitting, setOrderSubmitting] = useState(false);
  const [orderType, setOrderType] = useState<OrderType>('regular');
  const [assignedAccountId, setAssignedAccountId] = useState<number | null>(null);
  const [pointsBalance, setPointsBalance] = useState<number | null>(null);
  const [pointsOwnerName, setPointsOwnerName] = useState<string | null>(null);
  const [pointsOwnerRole, setPointsOwnerRole] = useState<string | null>(null);

  useEffect(() => {
    if (user?.id && user.role === 'distributor') {
      pointsApi.getEffectiveMyBalance()
        .then((res) => {
          setPointsBalance(res.balance);
          setPointsOwnerName(res.effective_user_name);
          setPointsOwnerRole(res.effective_user_role);
        })
        .catch(console.error);
    }
  }, [user?.id, user?.role]);

  const isSubAccount = user?.role === 'sub_account';
  const isNoRevenue = orderType === 'monthly_guarantee' || orderType === 'managed';

  const { data: productsData, isLoading: productsLoading } = useQuery({
    queryKey: ['products', { size: 100, is_active: true }],
    queryFn: () => productsApi.list({ size: 100, is_active: true }),
  });

  const { data: categoriesData, isLoading: categoriesLoading } = useQuery({
    queryKey: ['categories', { size: 100, is_active: true }],
    queryFn: () => categoriesApi.list({ size: 100, is_active: true }),
  });

  const products = productsData?.items ?? [];
  const categories = categoriesData?.items ?? [];

  const { data: accountsData } = useQuery({
    queryKey: ['superapAccounts', { is_active: true }],
    queryFn: () => campaignAccountsApi.list({ is_active: true, size: 100 }),
    enabled: isNoRevenue && isAdmin,
  });
  const accounts: SuperapAccount[] = accountsData?.items ?? [];

  const { data: productSchemaData } = useQuery({
    queryKey: ['productSchema', selectedProduct?.id],
    queryFn: () => pricesApi.getProductSchema(selectedProduct!.id),
    enabled: !!selectedProduct && !isSubAccount,
  });
  const effectivePrice = productSchemaData?.effective_price;

  const categoryBuckets = useMemo<CategoryBucket[]>(() => {
    const activeCategories = [...categories]
      .filter((category) => category.is_active)
      .sort((a, b) => a.sort_order - b.sort_order);

    const categoryMap = new Map(activeCategories.map((category) => [category.name, category]));
    const grouped = new Map<string, Product[]>();
    const uncategorized: Product[] = [];

    for (const product of products) {
      const rawCategory = product.category?.trim();
      if (!rawCategory || !categoryMap.has(rawCategory)) {
        uncategorized.push(product);
        continue;
      }
      const existing = grouped.get(rawCategory) ?? [];
      existing.push(product);
      grouped.set(rawCategory, existing);
    }

    const buckets: CategoryBucket[] = activeCategories
      .map((category) => ({
        key: category.name,
        name: category.name,
        description: category.description,
        icon: category.icon,
        image_url: category.image_url,
        sort_order: category.sort_order,
        products: [...(grouped.get(category.name) ?? [])].sort((a, b) => a.name.localeCompare(b.name, 'ko')),
      }))
      .filter((bucket) => bucket.products.length > 0);

    if (uncategorized.length > 0) {
      buckets.push({
        key: '__etc__',
        name: '기타',
        description: '카테고리가 지정되지 않았거나 미분류된 상품이에요.',
        icon: 'grid',
        image_url: undefined,
        sort_order: Number.MAX_SAFE_INTEGER,
        products: [...uncategorized].sort((a, b) => a.name.localeCompare(b.name, 'ko')),
      });
    }

    return buckets;
  }, [categories, products]);

  const selectedBucket = useMemo(
    () => categoryBuckets.find((bucket) => bucket.key === selectedCategory || bucket.name === selectedCategory) ?? null,
    [categoryBuckets, selectedCategory],
  );

  useEffect(() => {
    if (selectedCategory && !selectedBucket) {
      setSelectedCategory(null);
      setSelectedProduct(null);
    }
  }, [selectedBucket, selectedCategory]);

  useEffect(() => {
    if (!selectedProduct) return;
    const nextProduct = products.find((product) => product.id === selectedProduct.id) ?? null;
    if (!nextProduct) {
      setSelectedProduct(null);
      return;
    }
    if (selectedBucket && !selectedBucket.products.some((product) => product.id === nextProduct.id)) {
      setSelectedProduct(null);
      return;
    }
    if (nextProduct !== selectedProduct) {
      setSelectedProduct(nextProduct);
    }
  }, [products, selectedBucket, selectedProduct]);

  useEffect(() => {
    if (!isNoRevenue) {
      setAssignedAccountId(null);
    }
  }, [isNoRevenue]);

  const handleSelectCategory = (bucket: CategoryBucket) => {
    setSelectedCategory(bucket.key);
    // Auto-skip step 2 if category has only 1 product
    if (bucket.products.length === 1) {
      setSelectedProduct(bucket.products[0]);
    } else {
      setSelectedProduct(null);
    }
  };

  const handleBackToCategories = () => {
    setSelectedCategory(null);
    setSelectedProduct(null);
  };

  const handleBackToProducts = () => {
    setSelectedProduct(null);
  };

  const handleDirectSubmit = async (items: OrderGridRow[], notes: string) => {
    if (!selectedProduct) return;
    if (isNoRevenue && !assignedAccountId) {
      alert('월보장/관리형 주문은 계정을 선택해야 해요.');
      return;
    }
    setOrderSubmitting(true);
    try {
      await ordersApi.create({
        notes: notes || undefined,
        order_type: orderType,
        assigned_account_id: isNoRevenue && assignedAccountId ? assignedAccountId : undefined,
        items: items.map((row) => ({
          product_id: selectedProduct.id,
          quantity: getQuantityFromRow(row, selectedProduct),
          item_data: row,
        })),
      });
      navigate('/orders');
    } catch (err: any) {
      alert(err?.response?.data?.detail || '주문 생성에 실패했어요.');
    } finally {
      setOrderSubmitting(false);
    }
  };

  const schema = selectedProduct ? normalizeSchema(selectedProduct.form_schema) : [];
  const loading = productsLoading || categoriesLoading;
  const step = selectedProduct ? 3 : selectedBucket ? 2 : 1;

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between pt-2">
        <div>
          <button
            onClick={() => navigate('/orders')}
            className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-200 transition-colors mb-2"
          >
            <ArrowLeftIcon className="h-3.5 w-3.5" />
            주문 내역
          </button>
          <h1 className="text-2xl font-bold text-gray-100 tracking-tight">주문 접수</h1>
          <p className="mt-1.5 text-sm text-gray-500 font-medium">
            카테고리를 선택하고, 상품을 골라 접수 양식을 작성해 주세요
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2 text-xs">
          <StepBadge active={step >= 1} done={step > 1} icon={<Squares2X2Icon className="h-3.5 w-3.5" />} label="카테고리" num={1} />
          <ArrowRightIcon className="h-3 w-3 text-gray-600" />
          <StepBadge active={step >= 2} done={step > 2} icon={<CubeIcon className="h-3.5 w-3.5" />} label="세부 상품" num={2} />
          <ArrowRightIcon className="h-3 w-3 text-gray-600" />
          <StepBadge active={step >= 3} done={false} icon={<ClipboardDocumentListIcon className="h-3.5 w-3.5" />} label="접수 양식" num={3} />
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="bg-surface rounded-2xl shadow-sm border border-border-subtle p-8">
          <div className="animate-pulse space-y-4">
            <div className="h-5 w-40 rounded-lg bg-surface-raised" />
            <div className="h-3.5 w-72 rounded-lg bg-surface-raised" />
            <div className="grid grid-cols-2 gap-3 pt-3 sm:grid-cols-3 lg:grid-cols-4">
              {[0, 1, 2, 3].map((idx) => (
                <div key={idx} className="h-32 rounded-2xl bg-surface-raised" />
              ))}
            </div>
          </div>
        </div>
      ) : !selectedBucket ? (
        /* ── Step 1: Category ── */
        <div className="bg-surface rounded-2xl shadow-sm border border-border-subtle overflow-hidden transition-shadow hover:shadow-md duration-200">
          <div className="px-6 py-5 border-b border-border-subtle">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-primary-500" />
              <h2 className="text-[15px] font-bold text-gray-100">카테고리 선택</h2>
            </div>
            <p className="mt-1 text-[13px] text-gray-500 ml-3.5">이용하실 서비스 카테고리를 선택해 주세요</p>
          </div>
          <div className="p-6">
            {categoryBuckets.length === 0 ? (
              <div className="py-16 text-center">
                <p className="text-[15px] font-medium text-gray-400">활성 카테고리가 없어요</p>
                <p className="mt-1 text-sm text-gray-500">관리자에게 상품 등록을 요청해 주세요</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                {categoryBuckets.map((bucket) => {
                  const vt = getVisualToken(bucket.name, bucket.icon);
                  return (
                    <CategoryTile
                      key={bucket.key}
                      title={bucket.name}
                      count={bucket.products.length}
                      description={bucket.description}
                      symbol={vt.symbol}
                      symbolBg={vt.symbolBg}
                      symbolText={vt.symbolText}
                      isIconKey={vt.isIconKey}
                      imageUrl={bucket.image_url}
                      onClick={() => handleSelectCategory(bucket)}
                    />
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : !selectedProduct ? (
        /* ── Step 2: Product ── */
        <div className="space-y-4">
          {/* Breadcrumb bar */}
          <div className="flex flex-wrap items-center gap-3 bg-surface rounded-2xl shadow-sm border border-border-subtle px-5 py-3.5">
            <Button
              size="sm"
              variant="ghost"
              className="!rounded-xl !text-gray-400 hover:!text-gray-200 !text-sm"
              onClick={handleBackToCategories}
              icon={<ArrowLeftIcon className="h-4 w-4" />}
            >
              카테고리
            </Button>
            <div className="h-5 w-px bg-border-subtle" />
            <div className="flex items-center gap-2">
              {getVisualToken(selectedBucket.name, selectedBucket.icon).isIconKey ? (
                <CategoryIcon 
                  iconKey={getVisualToken(selectedBucket.name, selectedBucket.icon).symbol} 
                  size={28} 
                  className="rounded-lg" 
                />
              ) : (
                <span className={`inline-flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold ${getVisualToken(selectedBucket.name, selectedBucket.icon).symbolBg} ${getVisualToken(selectedBucket.name, selectedBucket.icon).symbolText}`}>
                  {getVisualToken(selectedBucket.name, selectedBucket.icon).symbol}
                </span>
              )}
              <span className="text-sm font-semibold text-gray-100">{selectedBucket.name}</span>
            </div>
            {selectedBucket.description && (
              <p className="hidden lg:block ml-auto text-[13px] text-gray-500">{selectedBucket.description}</p>
            )}
          </div>

          {/* Product cards */}
          <div className="bg-surface rounded-2xl shadow-sm border border-border-subtle overflow-hidden transition-shadow hover:shadow-md duration-200">
            <div className="px-6 py-5 border-b border-border-subtle">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-primary-500" />
                <h2 className="text-[15px] font-bold text-gray-100">세부 상품 선택</h2>
              </div>
              <p className="mt-1 text-[13px] text-gray-500 ml-3.5">{selectedBucket.name} 안에서 접수할 상품을 선택해 주세요</p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
                {selectedBucket.products.map((product) => {
                  const vt = getVisualToken(`${selectedBucket.name} ${product.name}`, selectedBucket.icon);
                  return (
                    <ProductTile
                      key={product.id}
                      title={product.name}
                      price={isSubAccount ? undefined : formatCurrency(product.base_price)}
                      period={(product.min_work_days || product.max_work_days) ? `${product.min_work_days ?? '-'}~${product.max_work_days ?? '-'}일` : undefined}
                      symbol={vt.symbol}
                      symbolBg={vt.symbolBg}
                      symbolText={vt.symbolText}
                      isIconKey={vt.isIconKey}
                      onClick={() => setSelectedProduct(product)}
                    />
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* ── Step 3: Form ── */
        <>
          {/* Breadcrumb bar */}
          <div className="flex flex-wrap items-center gap-3 bg-surface rounded-2xl shadow-sm border border-border-subtle px-5 py-3.5">
            <Button
              size="sm"
              variant="ghost"
              className="!rounded-xl !text-gray-400 hover:!text-gray-200 !text-sm"
              onClick={handleBackToProducts}
              icon={<ArrowLeftIcon className="h-4 w-4" />}
            >
              상품 변경
            </Button>
            <div className="h-5 w-px bg-border-subtle" />
            <div className="flex items-center gap-1.5">
              <span className="text-[12px] text-gray-500">{selectedBucket.name}</span>
              <ArrowRightIcon className="h-3 w-3 text-gray-600" />
              <span className="text-sm font-semibold text-gray-100">{selectedProduct.name}</span>
            </div>
            {selectedProduct.category && (
              <span className="text-[11px] text-gray-500 bg-surface-raised px-2 py-0.5 rounded-full border border-border-subtle">
                {selectedProduct.category}
              </span>
            )}

            {/* Admin controls */}
            {isAdmin && (
              <div className="flex items-center gap-3 ml-auto">
                <div className="flex items-center gap-2">
                  <label className="text-[12px] font-medium text-gray-500">유형</label>
                  <select
                    value={orderType}
                    onChange={(e) => setOrderType(e.target.value as OrderType)}
                    className="rounded-xl border border-border bg-surface px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/30 focus:border-primary-400 hover:border-border-strong transition-colors"
                  >
                    {orderTypeOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  {isNoRevenue && (
                    <span className="text-[11px] text-warning-500 bg-warning-50 px-2.5 py-1 rounded-full font-semibold border border-warning-500/20">
                      매출 0원
                    </span>
                  )}
                </div>
                {isNoRevenue && (
                  <div className="flex items-center gap-2">
                    <label className="text-[12px] font-medium text-gray-500">계정</label>
                    <select
                      value={assignedAccountId ?? ''}
                      onChange={(e) => setAssignedAccountId(e.target.value ? Number(e.target.value) : null)}
                      className="rounded-xl border border-border bg-surface px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/30 focus:border-primary-400 hover:border-border-strong transition-colors"
                    >
                      <option value="">계정을 선택해 주세요</option>
                      {accounts.map((acc) => (
                        <option key={acc.id} value={acc.id}>
                          {acc.user_id_superap}{acc.company_name ? ` (${acc.company_name})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}

            {/* Points badge for distributor only */}
            {user?.role === 'distributor' && pointsBalance !== null && (
              <div className="flex items-center gap-2 ml-auto bg-surface-raised border border-border-subtle rounded-xl px-3 py-2">
                <span className="text-[12px] text-gray-500">차감 기준</span>
                <span className="text-[12px] text-gray-500">
                  {pointsOwnerName ? `차감 기준: ${pointsOwnerName}${pointsOwnerRole ? ` (${pointsOwnerRole})` : ''}` : '차감 기준 포인트'}
                </span>
                <span className="text-sm font-bold text-primary-600">{formatCurrency(pointsBalance)}P</span>
              </div>
            )}
          </div>

          {/* Form card */}
          <div className="bg-surface rounded-2xl shadow-sm border border-border-subtle overflow-hidden transition-shadow hover:shadow-md duration-200">
            <div className="px-6 py-5 border-b border-border-subtle">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-primary-500" />
                <h2 className="text-[15px] font-bold text-gray-100">접수 양식</h2>
              </div>
              <p className="mt-1 text-[13px] text-gray-500 ml-3.5">선택한 상품에 맞는 항목만 자동으로 보여줘요</p>
            </div>
            <div className="p-6 space-y-4">
              {user?.role === 'distributor' && pointsBalance !== null && effectivePrice !== undefined && pointsBalance < effectivePrice && (
                <div className="rounded-xl bg-warning-50 border border-warning-500/20 text-warning-500 text-sm p-3.5 flex items-center gap-2.5 font-medium">
                  <ExclamationTriangleIcon className="h-5 w-5 shrink-0" />
                  <p>차감 기준 포인트가 부족합니다. 충전 후 진행해 주세요.</p>
                </div>
              )}
              <OrderGrid
                key={selectedProduct.id}
                product={selectedProduct}
                schema={schema}
                onSubmit={handleDirectSubmit}
                submitting={orderSubmitting}
                effectivePrice={user?.role !== 'sub_account' ? effectivePrice : undefined}
                enableAI={selectedProduct.is_ilryu_reward ?? false}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Step Badge ── */
function StepBadge({
  active,
  done,
  icon,
  label,
  num,
}: {
  active: boolean;
  done: boolean;
  icon: ReactNode;
  label: string;
  num: number;
}) {
  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-all duration-200',
        active
          ? 'bg-primary-600 text-white shadow-sm'
          : 'bg-surface-raised text-gray-500 border border-border-subtle',
      ].join(' ')}
    >
      {done ? (
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      ) : (
        <span className="text-[11px] font-bold">{num}</span>
      )}
      {icon}
      <span className="font-semibold">{label}</span>
    </span>
  );
}

/* ── Category Tile ── */
function CategoryTile({
  title,
  count,
  description,
  symbol,
  symbolBg,
  symbolText,
  isIconKey,
  imageUrl,
  onClick,
}: {
  title: string;
  count: number;
  description?: string;
  symbol: string;
  symbolBg: string;
  symbolText: string;
  isIconKey?: boolean;
  imageUrl?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex flex-col items-center gap-3 rounded-2xl border border-border-subtle bg-surface p-5 text-center transition-all duration-200 hover:border-primary-400/40 hover:shadow-md hover:-translate-y-0.5"
    >
      {imageUrl ? (
        <div className="h-11 w-11 overflow-hidden rounded-xl border border-border-subtle shadow-sm transition-transform duration-200 group-hover:scale-110">
          <img src={imageUrl} alt={`${title} 이미지`} className="h-full w-full object-cover" />
        </div>
      ) : isIconKey && categoryIcons[symbol] ? (
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${symbolBg} ${symbolText} transition-transform duration-200 group-hover:scale-110`}>
          <div className="w-5 h-5">{categoryIcons[symbol].icon}</div>
        </div>
      ) : (
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl text-lg font-bold ${symbolBg} ${symbolText} transition-transform duration-200 group-hover:scale-110`}>
          {symbol}
        </div>
      )}
      <div className="space-y-1">
        <div className="text-[14px] font-semibold text-gray-100">{title}</div>
        <div className="text-[12px] font-medium text-primary-600">{count}개 상품</div>
      </div>
      {description && (
        <p className="text-[11px] text-gray-500 leading-relaxed line-clamp-2">{description}</p>
      )}
    </button>
  );
}

/* ── Product Tile ── */
function ProductTile({
  title,
  price,
  period,
  symbol,
  symbolBg,
  symbolText,
  isIconKey,
  onClick,
}: {
  title: string;
  price?: string;
  period?: string;
  symbol: string;
  symbolBg: string;
  symbolText: string;
  isIconKey?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex flex-col items-center gap-3 rounded-2xl border border-border-subtle bg-surface p-5 text-center transition-all duration-200 hover:border-primary-400/40 hover:shadow-md hover:-translate-y-0.5"
    >
      {isIconKey && categoryIcons[symbol] ? (
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${symbolBg} ${symbolText} transition-transform duration-200 group-hover:scale-110`}>
          <div className="w-5 h-5">{categoryIcons[symbol].icon}</div>
        </div>
      ) : (
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl text-base font-bold ${symbolBg} ${symbolText} transition-transform duration-200 group-hover:scale-110`}>
          {symbol}
        </div>
      )}
      <div className="space-y-1">
        <div className="text-[14px] font-semibold text-gray-100">{title}</div>
        {price && <div className="text-[13px] font-bold text-primary-600">{price}</div>}
      </div>
      {period && (
        <span className="rounded-full bg-surface-raised border border-border-subtle px-2.5 py-0.5 text-[11px] font-medium text-gray-400">
          {period}
        </span>
      )}
    </button>
  );
}

function getQuantityFromRow(row: OrderGridRow, product: Product): number {
  const schema = normalizeSchema(product.form_schema);
  const qtyField = schema.find((f) => f.is_quantity);
  if (qtyField) return Number(row[qtyField.name]) || 1;
  return Number(row.quantity) || 1;
}
