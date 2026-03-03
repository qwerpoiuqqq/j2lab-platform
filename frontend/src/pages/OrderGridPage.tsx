import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import { productsApi } from '@/api/products';
import { ordersApi } from '@/api/orders';
import { pricesApi } from '@/api/prices';
import type { Product, OrderType } from '@/types';
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

  // Fetch products
  const { data: productsData, isLoading: productsLoading } = useQuery({
    queryKey: ['products', { size: 100, is_active: true }],
    queryFn: () => productsApi.list({ size: 100, is_active: true }),
  });
  const products = productsData?.items ?? [];

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
    setOrderSubmitting(true);
    try {
      await ordersApi.create({
        notes: notes || undefined,
        order_type: orderType,
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
        <h1 className="text-2xl font-bold text-gray-900">주문 접수</h1>
        <p className="mt-1 text-sm text-gray-500">
          상품을 선택한 후 접수 양식에 맞게 데이터를 입력하세요. AI가 캠페인 타입과 네트워크를 자동 추천합니다.
        </p>
      </div>

      {/* Step 1: 상품 선택 */}
      {!selectedProduct ? (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">상품 선택</h2>
            <p className="mt-1 text-sm text-gray-500">접수할 상품을 선택하세요.</p>
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
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {products.map((product) => (
                  <button
                    key={product.id}
                    onClick={() => setSelectedProduct(product)}
                    className="text-left p-4 border border-gray-200 rounded-lg hover:border-primary-400 hover:bg-primary-50 transition-colors"
                  >
                    <div className="font-medium text-gray-900">{product.name}</div>
                    {product.category && (
                      <div className="mt-1 text-xs text-gray-500">{product.category}</div>
                    )}
                    {product.description && (
                      <div className="mt-1 text-xs text-gray-400 line-clamp-2">{product.description}</div>
                    )}
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
              <span className="text-sm font-medium text-gray-900">{selectedProduct.name}</span>
              {selectedProduct.category && (
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                  {selectedProduct.category}
                </span>
              )}
            </div>
            {isAdmin && (
              <div className="flex items-center gap-2 ml-auto">
                <label className="text-sm text-gray-600">주문 유형:</label>
                <select
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value as OrderType)}
                  className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  {orderTypeOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                {orderType !== 'regular' && (
                  <span className="text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded">
                    매출 0원 (매입만 발생)
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Order Grid */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">접수 양식 입력</h2>
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
