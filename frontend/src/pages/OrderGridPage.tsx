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
                {products.map((product) => (
                  <button
                    key={product.id}
                    onClick={() => setSelectedProduct(product)}
                    className="group text-left rounded-xl border border-border overflow-hidden hover:border-primary-400 hover:shadow-lg hover:shadow-primary-500/10 transition-all duration-200"
                  >
                    {/* Card Header with gradient */}
                    <div className={`h-28 flex items-center justify-center relative overflow-hidden ${
                      product.category?.includes('쇼핑')
                        ? 'bg-gradient-to-br from-emerald-900/60 to-teal-900/40'
                        : product.category?.includes('영수증')
                        ? 'bg-gradient-to-br from-amber-900/60 to-orange-900/40'
                        : 'bg-gradient-to-br from-primary-900/60 to-cyan-900/40'
                    }`}>
                      <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_30%,rgba(255,255,255,0.05),transparent)]" />
                      <div className={`text-4xl ${
                        product.category?.includes('쇼핑')
                          ? 'text-emerald-400/80'
                          : product.category?.includes('영수증')
                          ? 'text-amber-400/80'
                          : 'text-primary-400/80'
                      } group-hover:scale-110 transition-transform duration-200`}>
                        {product.category?.includes('쇼핑') ? (
                          <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 00-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.924-7.138a60.114 60.114 0 00-16.536-1.84M7.5 14.25L5.106 5.272M6 20.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm12.75 0a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" /></svg>
                        ) : product.category?.includes('영수증') ? (
                          <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 14.25l6-6m4.5-3.493V21.75l-3.75-1.5-3.75 1.5-3.75-1.5-3.75 1.5V4.757c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0c1.1.128 1.907 1.077 1.907 2.185zM9.75 9h.008v.008H9.75V9zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 4.5h.008v.008h-.008V13.5zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" /></svg>
                        ) : (
                          <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" /></svg>
                        )}
                      </div>
                    </div>
                    {/* Card Body */}
                    <div className="p-4">
                      <h3 className="font-semibold text-gray-100 group-hover:text-primary-400 transition-colors">
                        {product.name}
                      </h3>
                      {product.category && (
                        <span className={`inline-block mt-2 text-xs px-2 py-0.5 rounded-full ${
                          product.category?.includes('쇼핑')
                            ? 'bg-emerald-900/40 text-emerald-400'
                            : product.category?.includes('영수증')
                            ? 'bg-amber-900/40 text-amber-400'
                            : 'bg-primary-900/40 text-primary-400'
                        }`}>
                          {product.category}
                        </span>
                      )}
                      {product.description && (
                        <p className="mt-2 text-xs text-gray-400 line-clamp-2">{product.description}</p>
                      )}
                    </div>
                  </button>
                ))}
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
