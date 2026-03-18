import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { productsApi } from '@/api/products';
import { ordersApi } from '@/api/orders';
import { pricesApi } from '@/api/prices';
import { campaignAccountsApi } from '@/api/campaignAccounts';
import type { Product, OrderType, SuperapAccount } from '@/types';
import { normalizeSchema } from '@/utils/schema';
import OrderGrid, { type OrderGridRow } from '@/components/features/orders/OrderGrid';
import Button from '@/components/common/Button';
import { useAuthStore } from '@/store/auth';

// Category icon mapping (same as CategoriesPage)
const categoryIconMap: Record<string, string> = {
  'naver-place': '\u{1F4CD}',   // 📍
  'naver': '\u{1F6D2}',         // 🛒
  'receipt': '\u{1F9FE}',       // 🧾
  'chart-bar': '\u{1F4CA}',     // 📊
  'bookmark': '\u{1F516}',      // 🔖
  'sparkles': '\u{2728}',       // ✨
  'grid': '\u{1F4CB}',          // 📋
  'shopping-cart': '\u{1F6D2}', // 🛒
  'tag': '\u{1F3F7}\uFE0F',    // 🏷️
  'star': '\u{2B50}',           // ⭐
};

// Category name → icon key fallback
function getCategoryEmoji(categoryName?: string): string {
  if (!categoryName) return '\u{1F4CB}';
  if (categoryName.includes('쇼핑')) return '\u{1F6D2}';
  if (categoryName.includes('영수증')) return '\u{1F9FE}';
  if (categoryName.includes('플레이스')) return '\u{1F4CD}';
  return '\u{1F4CB}';
}

// Category name → gradient color
function getCategoryColor(categoryName?: string): { bg: string; text: string; badge: string } {
  if (!categoryName) return { bg: 'from-gray-800/60 to-gray-900/40', text: 'text-gray-400', badge: 'bg-gray-800/40 text-gray-400' };
  if (categoryName.includes('쇼핑')) return { bg: 'from-emerald-900/60 to-teal-900/40', text: 'text-emerald-400', badge: 'bg-emerald-900/40 text-emerald-400' };
  if (categoryName.includes('영수증')) return { bg: 'from-amber-900/60 to-orange-900/40', text: 'text-amber-400', badge: 'bg-amber-900/40 text-amber-400' };
  return { bg: 'from-primary-900/60 to-cyan-900/40', text: 'text-primary-400', badge: 'bg-primary-900/40 text-primary-400' };
}

const orderTypeOptions: { value: OrderType; label: string }[] = [
  { value: 'regular', label: '일반' },
  { value: 'monthly_guarantee', label: '월보장' },
  { value: 'managed', label: '관리형' },
];

export default function OrderGridPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'system_admin' || user?.role === 'company_admin';
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [orderSubmitting, setOrderSubmitting] = useState(false);
  const [orderType, setOrderType] = useState<OrderType>('regular');
  const [assignedAccountId, setAssignedAccountId] = useState<number | null>(null);

  const isNoRevenue = orderType === 'monthly_guarantee' || orderType === 'managed';

  // Fetch products
  const { data: productsData, isLoading: productsLoading } = useQuery({
    queryKey: ['products', { size: 100, is_active: true }],
    queryFn: () => productsApi.list({ size: 100, is_active: true }),
  });
  const products = productsData?.items ?? [];

  // Fetch superap accounts for no-revenue order types
  const { data: accountsData } = useQuery({
    queryKey: ['superapAccounts', { is_active: true }],
    queryFn: () => campaignAccountsApi.list({ is_active: true, size: 100 }),
    enabled: isNoRevenue && isAdmin,
  });
  const accounts: SuperapAccount[] = accountsData?.items ?? [];

  // Fetch effective price for selected product (총판별 단가)
  const { data: productSchemaData } = useQuery({
    queryKey: ['productSchema', selectedProduct?.id],
    queryFn: () => pricesApi.getProductSchema(selectedProduct!.id),
    enabled: !!selectedProduct,
  });
  const effectivePrice = productSchemaData?.effective_price;

  // Direct input submit
  const handleDirectSubmit = async (items: OrderGridRow[], notes: string) => {
    if (!selectedProduct) return;
    if (isNoRevenue && !assignedAccountId) {
      alert('월보장/관리형 주문은 계정을 선택해야 합니다.');
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
      alert(err?.response?.data?.detail || '주문 생성에 실패했습니다.');
    } finally {
      setOrderSubmitting(false);
    }
  };

  const schema = selectedProduct ? normalizeSchema(selectedProduct.form_schema) : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">주문 접수</h1>
        <p className="mt-1 text-sm text-gray-400">
          상품을 선택한 후 접수 양식에 맞게 데이터를 입력하세요. AI가 캠페인 타입과 네트워크를 자동 추천합니다.
        </p>
      </div>

      {/* Step 1: 상품 선택 */}
      {!selectedProduct ? (
        <div className="bg-surface rounded-xl border border-border shadow-sm">
          <div className="px-6 py-4 border-b border-border">
            <h2 className="text-lg font-semibold text-gray-100">상품 선택</h2>
            <p className="mt-1 text-sm text-gray-400">접수할 상품을 선택하세요.</p>
          </div>
          <div className="p-6">
            {productsLoading ? (
              <div className="flex items-center justify-center py-12">
                <svg className="animate-spin h-6 w-6 text-primary-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {products.map((product) => {
                  const emoji = getCategoryEmoji(product.category);
                  const colors = getCategoryColor(product.category);
                  return (
                    <button
                      key={product.id}
                      onClick={() => setSelectedProduct(product)}
                      className="group text-left rounded-xl border border-border overflow-hidden hover:border-primary-400 hover:shadow-lg hover:shadow-primary-500/10 transition-all duration-200"
                    >
                      {/* Card Header */}
                      <div className={`h-32 flex items-center justify-center bg-gradient-to-br ${colors.bg} relative`}>
                        <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_30%,rgba(255,255,255,0.06),transparent)]" />
                        <span className="text-5xl group-hover:scale-110 transition-transform duration-200 drop-shadow-lg">
                          {emoji}
                        </span>
                      </div>
                      {/* Card Body */}
                      <div className="p-4 space-y-2">
                        <h3 className="font-semibold text-gray-100 group-hover:text-primary-400 transition-colors">
                          {product.name}
                        </h3>
                        {product.category && (
                          <span className={`inline-block text-xs px-2.5 py-0.5 rounded-full font-medium ${colors.badge}`}>
                            {product.category}
                          </span>
                        )}
                        {product.description && (
                          <p className="text-xs text-gray-400 line-clamp-2">{product.description}</p>
                        )}
                      </div>
                    </button>
                  );
                })}
                {products.length === 0 && (
                  <div className="col-span-full text-center py-12 text-gray-400">
                    활성 상품이 없습니다.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        <>
          {/* 선택된 상품 + 뒤로가기 */}
          <div className="flex items-center gap-3 flex-wrap">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setSelectedProduct(null)}
              icon={<ArrowLeftIcon className="h-4 w-4" />}
            >
              상품 변경
            </Button>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-100">{selectedProduct.name}</span>
              {selectedProduct.category && (
                <span className="text-xs text-gray-400 bg-surface-raised px-2 py-0.5 rounded">
                  {selectedProduct.category}
                </span>
              )}
            </div>
            {isAdmin && (
              <div className="flex items-center gap-2 ml-auto">
                <label className="text-sm text-gray-400">주문 유형:</label>
                <select
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value as OrderType)}
                  className="rounded-lg border border-border-strong px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400 bg-surface text-gray-200"
                >
                  {orderTypeOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                {isNoRevenue && (
                  <span className="text-xs text-orange-400 bg-orange-900/20 px-2 py-1 rounded">
                    매출 0원 (매입만 발생)
                  </span>
                )}
              </div>
            )}
            {isAdmin && isNoRevenue && (
              <div className="flex items-center gap-2">
                <label className="text-sm text-gray-400">배정 계정:</label>
                <select
                  value={assignedAccountId ?? ''}
                  onChange={(e) => setAssignedAccountId(e.target.value ? Number(e.target.value) : null)}
                  className="rounded-lg border border-border-strong px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400 bg-surface text-gray-200"
                >
                  <option value="">계정 선택 (필수)</option>
                  {accounts.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      {acc.user_id_superap}{acc.company_name ? ` (${acc.company_name})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Order Grid */}
          <div className="bg-surface rounded-xl border border-border shadow-sm">
            <div className="px-6 py-4 border-b border-border">
              <h2 className="text-lg font-semibold text-gray-100">접수 양식 입력</h2>
            </div>
            <div className="p-6">
              <OrderGrid
                product={selectedProduct}
                schema={schema}
                onSubmit={handleDirectSubmit}
                submitting={orderSubmitting}
                effectivePrice={effectivePrice}
                enableAI
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/** Extract quantity from row data based on product form_schema */
function getQuantityFromRow(row: OrderGridRow, product: Product): number {
  const schema = normalizeSchema(product.form_schema);
  const qtyField = schema.find((f) => f.is_quantity);
  if (qtyField) return Number(row[qtyField.name]) || 1;
  return Number(row['quantity']) || 1;
}
