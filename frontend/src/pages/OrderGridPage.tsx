import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ChevronRightIcon } from '@heroicons/react/24/outline';
import { productsApi } from '@/api/products';
import { pricesApi } from '@/api/prices';
import { ordersApi } from '@/api/orders';
import type { Product, ProductSchema, CreateOrderRequest } from '@/types';
import CategorySelector from '@/components/features/orders/CategorySelector';
import ProductSelector from '@/components/features/orders/ProductSelector';
import OrderGrid, { type OrderGridRow } from '@/components/features/orders/OrderGrid';
import Button from '@/components/common/Button';

type Step = 1 | 2 | 3;

export default function OrderGridPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>(1);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [schema, setSchema] = useState<ProductSchema | null>(null);

  // Fetch all products
  const { data: productsData, isLoading: productsLoading } = useQuery({
    queryKey: ['products', { size: 100, is_active: true }],
    queryFn: () => productsApi.list({ size: 100, is_active: true }),
  });

  const products = productsData?.items ?? [];

  // Fetch schema when product selected
  const { isLoading: schemaLoading } = useQuery({
    queryKey: ['product-schema', selectedProduct?.id],
    queryFn: async () => {
      const data = await pricesApi.getProductSchema(selectedProduct!.id);
      setSchema(data);
      return data;
    },
    enabled: !!selectedProduct,
  });

  // Submit mutation
  const submitMutation = useMutation({
    mutationFn: (data: CreateOrderRequest) => ordersApi.create(data),
    onSuccess: () => {
      navigate('/orders');
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail || '주문 제출에 실패했습니다.');
    },
  });

  const handleCategorySelect = (category: string) => {
    setSelectedCategory(category);
    setSelectedProduct(null);
    setSchema(null);
    setStep(2);
  };

  const handleProductSelect = (product: Product) => {
    setSelectedProduct(product);
    setSchema(null);
    setStep(3);
  };

  const handleSubmit = (items: OrderGridRow[], notes: string) => {
    if (!selectedProduct) return;
    const request: CreateOrderRequest = {
      items: items.map((row) => ({
        product_id: selectedProduct.id,
        quantity: Number(row['quantity']) || 1,
        item_data: row,
      })),
      notes: notes || undefined,
    };
    submitMutation.mutate(request);
  };

  const goToStep = (target: Step) => {
    if (target < step) {
      if (target === 1) {
        setSelectedCategory('');
        setSelectedProduct(null);
        setSchema(null);
      } else if (target === 2) {
        setSelectedProduct(null);
        setSchema(null);
      }
      setStep(target);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">주문 접수</h1>
        <p className="mt-1 text-sm text-gray-500">
          카테고리와 상품을 선택한 후 주문 정보를 입력합니다.
        </p>
      </div>

      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm">
        <BreadcrumbItem
          label="카테고리 선택"
          active={step === 1}
          completed={step > 1}
          onClick={() => goToStep(1)}
        />
        <ChevronRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
        <BreadcrumbItem
          label={selectedCategory || '상품 선택'}
          active={step === 2}
          completed={step > 2}
          onClick={() => step > 1 ? goToStep(2) : undefined}
        />
        <ChevronRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
        <BreadcrumbItem
          label={selectedProduct?.name || '주문 입력'}
          active={step === 3}
          completed={false}
        />
      </nav>

      {/* Step content */}
      <div className="min-h-[300px]">
        {step === 1 && (
          <StepCard title="카테고리를 선택하세요" loading={productsLoading}>
            <CategorySelector products={products} onSelect={handleCategorySelect} />
          </StepCard>
        )}

        {step === 2 && (
          <StepCard
            title={`${selectedCategory} - 상품을 선택하세요`}
            loading={productsLoading}
            onBack={() => goToStep(1)}
          >
            <ProductSelector
              products={products}
              category={selectedCategory}
              onSelect={handleProductSelect}
            />
          </StepCard>
        )}

        {step === 3 && selectedProduct && (
          <StepCard
            title={`${selectedProduct.name} - 주문 정보 입력`}
            loading={schemaLoading}
            onBack={() => goToStep(2)}
          >
            {schema && schema.form_schema.length > 0 ? (
              <OrderGrid
                product={selectedProduct}
                schema={schema.form_schema}
                onSubmit={handleSubmit}
                submitting={submitMutation.isPending}
              />
            ) : !schemaLoading ? (
              <div className="text-center py-12 text-gray-500">
                이 상품에 설정된 입력 양식이 없습니다.
              </div>
            ) : null}
          </StepCard>
        )}
      </div>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────

function BreadcrumbItem({
  label,
  active,
  completed,
  onClick,
}: {
  label: string;
  active: boolean;
  completed: boolean;
  onClick?: () => void;
}) {
  const baseClass = 'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors';
  if (active) {
    return (
      <span className={`${baseClass} bg-primary-100 text-primary-700`}>
        {label}
      </span>
    );
  }
  if (completed && onClick) {
    return (
      <button
        onClick={onClick}
        className={`${baseClass} text-primary-600 hover:bg-primary-50 cursor-pointer`}
      >
        {label}
      </button>
    );
  }
  return (
    <span className={`${baseClass} text-gray-400`}>
      {label}
    </span>
  );
}

function StepCard({
  title,
  loading,
  onBack,
  children,
}: {
  title: string;
  loading?: boolean;
  onBack?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        {onBack && (
          <Button size="sm" variant="ghost" onClick={onBack}>
            이전 단계
          </Button>
        )}
      </div>
      <div className="p-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <svg
              className="animate-spin h-8 w-8 text-primary-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
