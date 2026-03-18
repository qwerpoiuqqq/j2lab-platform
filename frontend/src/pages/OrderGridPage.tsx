import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { productsApi } from '@/api/products';
import { ordersApi } from '@/api/orders';
import { pricesApi } from '@/api/prices';
import { campaignAccountsApi } from '@/api/campaignAccounts';
import type { Product, OrderType, SuperapAccount } from '@/types';
import { normalizeSchema } from '@/utils/schema';
import { formatCurrency } from '@/utils/format';
import OrderGrid, { type OrderGridRow } from '@/components/features/orders/OrderGrid';
import { CategoryIcon } from '@/components/common/CategoryIcons';
import Button from '@/components/common/Button';
import { useAuthStore } from '@/store/auth';

const orderTypeOptions: { value: OrderType; label: string }[] = [
  { value: 'regular', label: '일반' },
  { value: 'monthly_guarantee', label: '월보장' },
  { value: 'managed', label: '관리형' },
];

// Category name → icon key mapping
function getCategoryIconKey(categoryName: string): string {
  if (categoryName.includes('플레이스')) return 'naver-place';
  if (categoryName.includes('쇼핑')) return 'shopping';
  if (categoryName.includes('영수증')) return 'receipt';
  return 'grid';
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

  const isNoRevenue = orderType === 'monthly_guarantee' || orderType === 'managed';

  // Fetch products
  const { data: productsData, isLoading: productsLoading } = useQuery({
    queryKey: ['products', { size: 100, is_active: true }],
    queryFn: () => productsApi.list({ size: 100, is_active: true }),
  });
  const products = productsData?.items ?? [];

  // Derive categories from products
  const categories = useMemo(() => {
    const map = new Map<string, { count: number; minPrice: number }>();
    for (const p of products) {
      const cat = p.category || '기타';
      const existing = map.get(cat);
      if (existing) {
        existing.count += 1;
        existing.minPrice = Math.min(existing.minPrice, p.base_price);
      } else {
        map.set(cat, { count: 1, minPrice: p.base_price });
      }
    }
    return Array.from(map.entries()).map(([name, info]) => ({
      name,
      count: info.count,
      minPrice: info.minPrice,
      iconKey: getCategoryIconKey(name),
    }));
  }, [products]);

  // Fetch superap accounts for no-revenue order types
  const { data: accountsData } = useQuery({
    queryKey: ['superapAccounts', { is_active: true }],
    queryFn: () => campaignAccountsApi.list({ is_active: true, size: 100 }),
    enabled: isNoRevenue && isAdmin,
  });
  const accounts: SuperapAccount[] = accountsData?.items ?? [];

  // Fetch effective price for selected product
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

  const handleBack = () => {
    if (selectedProduct) {
      setSelectedProduct(null);
    } else if (selectedCategory) {
      setSelectedCategory(null);
    }
  };

  const schema = selectedProduct ? normalizeSchema(selectedProduct.form_schema) : [];
  const filteredProducts = selectedCategory
    ? products.filter((p) => (p.category || '기타') === selectedCategory)
    : products;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">주문 접수</h1>
        <p className="mt-1 text-sm text-gray-400">
          상품을 선택한 후 접수 양식에 맞게 데이터를 입력하세요. AI가 캠페인 타입과 네트워크를 자동 추천합니다.
        </p>
      </div>

      {/* Step 1: 카테고리 선택 */}
      {!selectedCategory && !selectedProduct ? (
        <div className="bg-surface rounded-xl border border-border shadow-sm">
          <div className="px-6 py-4 border-b border-border">
            <h2 className="text-lg font-semibold text-gray-100">카테고리 선택</h2>
            <p className="mt-1 text-sm text-gray-400">접수할 상품의 카테고리를 선택하세요.</p>
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
                {categories.map((cat) => (
                  <button
                    key={cat.name}
                    onClick={() => setSelectedCategory(cat.name)}
                    className="bg-surface rounded-xl border border-border shadow-sm p-6 text-left hover:border-primary-400 hover:shadow-md transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <CategoryIcon iconKey={cat.iconKey} size={48} className="rounded-xl flex-shrink-0" />
                      <div>
                        <h3 className="text-lg font-semibold text-gray-100 group-hover:text-primary-400 transition-colors">
                          {cat.name}
                        </h3>
                        <p className="mt-1 text-sm text-gray-400">
                          {cat.count}개 상품 &middot; {formatCurrency(cat.minPrice)}~
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
                {categories.length === 0 && (
                  <div className="col-span-full text-center py-12 text-gray-400">
                    등록된 상품이 없습니다.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : !selectedProduct ? (
        /* Step 2: 상품 선택 */
        <div className="bg-surface rounded-xl border border-border shadow-sm">
          <div className="px-6 py-4 border-b border-border flex items-center gap-3">
            <Button size="sm" variant="ghost" onClick={handleBack} icon={<ArrowLeftIcon className="h-4 w-4" />}>
              카테고리
            </Button>
            <div>
              <h2 className="text-lg font-semibold text-gray-100">{selectedCategory}</h2>
              <p className="text-sm text-gray-400">상품을 선택하세요.</p>
            </div>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredProducts.map((product) => (
                <button
                  key={product.id}
                  onClick={() => setSelectedProduct(product)}
                  className="bg-surface rounded-xl border border-border shadow-sm p-6 text-left hover:border-primary-400 hover:shadow-md transition-all group"
                >
                  <h3 className="text-lg font-semibold text-gray-100 group-hover:text-primary-400 transition-colors">
                    {product.name}
                  </h3>
                  <p className="mt-1 text-sm font-medium text-primary-400">
                    {formatCurrency(product.base_price)}
                  </p>
                  {product.description && (
                    <p className="mt-2 text-sm text-gray-400 line-clamp-2">
                      {product.description}
                    </p>
                  )}
                  {(product.min_work_days || product.max_work_days) && (
                    <p className="mt-2 text-xs text-gray-500">
                      작업기간: {product.min_work_days ?? '-'} ~ {product.max_work_days ?? '-'}일
                    </p>
                  )}
                </button>
              ))}
              {filteredProducts.length === 0 && (
                <div className="col-span-full text-center py-12 text-gray-400">
                  이 카테고리에 상품이 없습니다.
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Step 3: 접수 양식 */}
          <div className="flex items-center gap-3 flex-wrap">
            <Button
              size="sm"
              variant="ghost"
              onClick={handleBack}
              icon={<ArrowLeftIcon className="h-4 w-4" />}
            >
              상품 변경
            </Button>
            <div className="flex items-center gap-2">
              <CategoryIcon iconKey={getCategoryIconKey(selectedProduct.category || '')} size={28} className="rounded-md" />
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
