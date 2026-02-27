import { useState, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ChevronRightIcon, ArrowUpTrayIcon } from '@heroicons/react/24/outline';
import { productsApi } from '@/api/products';
import { pricesApi } from '@/api/prices';
import { ordersApi } from '@/api/orders';
import { normalizeSchema } from '@/utils/schema';
import type { Product, ProductSchema, CreateOrderRequest, ExcelUploadPreviewResponse } from '@/types';
import CategorySelector from '@/components/features/orders/CategorySelector';
import ProductSelector from '@/components/features/orders/ProductSelector';
import OrderGrid, { type OrderGridRow } from '@/components/features/orders/OrderGrid';
import Button from '@/components/common/Button';

type Step = 1 | 2 | 3;
type InputMode = 'form' | 'excel';

export default function OrderGridPage() {
  const navigate = useNavigate();
  const [inputMode, setInputMode] = useState<InputMode>('form');
  const [step, setStep] = useState<Step>(1);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [schema, setSchema] = useState<ProductSchema | null>(null);

  // Excel upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [excelPreview, setExcelPreview] = useState<ExcelUploadPreviewResponse | null>(null);
  const [excelUploading, setExcelUploading] = useState(false);
  const [excelNotes, setExcelNotes] = useState('');

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
      // Normalize form_schema to handle both old and new formats
      const normalized = {
        ...data,
        form_schema: normalizeSchema(data.form_schema),
      };
      setSchema(normalized);
      return normalized;
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

  // Excel upload handler
  const handleExcelFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedProduct) return;
    setExcelUploading(true);
    setExcelPreview(null);
    try {
      const preview = await ordersApi.uploadExcelPreview(file, selectedProduct.id);
      setExcelPreview(preview);
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Excel 파일 처리에 실패했습니다.');
    } finally {
      setExcelUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Excel confirm handler
  const confirmExcelMutation = useMutation({
    mutationFn: async () => {
      if (!excelPreview) return;
      const validItems = excelPreview.items.filter((item) => item.is_valid);
      return ordersApi.confirmExcelUpload({
        product_id: excelPreview.product_id,
        row_indices: validItems.map((item) => item.row_number),
        rows: validItems.map((item) => item.data),
        notes: excelNotes || undefined,
      });
    },
    onSuccess: () => {
      navigate('/orders');
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Excel 주문 생성에 실패했습니다.');
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

      {/* Mode Toggle */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => { setInputMode('form'); setExcelPreview(null); }}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            inputMode === 'form'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          폼 입력
        </button>
        <button
          onClick={() => setInputMode('excel')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            inputMode === 'excel'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Excel 업로드
        </button>
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
        {inputMode === 'form' && (
          <>
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
          </>
        )}

        {inputMode === 'excel' && (
          <div className="space-y-6">
            {/* Product selection for Excel mode */}
            {!selectedProduct ? (
              <>
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
              </>
            ) : (
              <StepCard
                title={`${selectedProduct.name} - Excel 업로드`}
                onBack={() => { setSelectedProduct(null); setExcelPreview(null); setStep(1); setSelectedCategory(''); }}
              >
                <div className="space-y-4">
                  {/* Template download + file upload */}
                  <div className="flex items-center gap-4">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={async () => {
                        try {
                          const blob = await ordersApi.downloadExcelTemplate(selectedProduct.id);
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `template_${selectedProduct.code}.xlsx`;
                          a.click();
                          URL.revokeObjectURL(url);
                        } catch {
                          alert('템플릿 다운로드에 실패했습니다.');
                        }
                      }}
                    >
                      템플릿 다운로드
                    </Button>
                    <label className="flex items-center gap-2 cursor-pointer px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors">
                      <ArrowUpTrayIcon className="h-4 w-4" />
                      Excel 파일 선택
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".xlsx,.xls"
                        onChange={handleExcelFileChange}
                        className="hidden"
                      />
                    </label>
                    {excelUploading && <span className="text-sm text-gray-500">처리 중...</span>}
                  </div>

                  {/* Preview table */}
                  {excelPreview && (
                    <div className="space-y-4">
                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-gray-700">전체: <strong>{excelPreview.total}</strong>건</span>
                        <span className="text-green-600">유효: <strong>{excelPreview.valid_count}</strong>건</span>
                        {excelPreview.error_count > 0 && (
                          <span className="text-red-600">오류: <strong>{excelPreview.error_count}</strong>건</span>
                        )}
                      </div>

                      <div className="overflow-x-auto border rounded-lg max-h-96">
                        <table className="min-w-full divide-y divide-gray-200 text-sm">
                          <thead className="bg-gray-50 sticky top-0">
                            <tr>
                              <th className="px-3 py-2 text-left font-medium text-gray-500">행</th>
                              <th className="px-3 py-2 text-left font-medium text-gray-500">상태</th>
                              {excelPreview.items[0] && Object.keys(excelPreview.items[0].data).map((key) => (
                                <th key={key} className="px-3 py-2 text-left font-medium text-gray-500">{key}</th>
                              ))}
                              <th className="px-3 py-2 text-left font-medium text-gray-500">오류</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {excelPreview.items.map((item) => (
                              <tr key={item.row_number} className={item.is_valid ? '' : 'bg-red-50'}>
                                <td className="px-3 py-2 text-gray-700">{item.row_number}</td>
                                <td className="px-3 py-2">
                                  {item.is_valid ? (
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">유효</span>
                                  ) : (
                                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">오류</span>
                                  )}
                                </td>
                                {Object.values(item.data).map((val, i) => (
                                  <td key={i} className="px-3 py-2 text-gray-600 max-w-[200px] truncate">
                                    {val != null ? String(val) : ''}
                                  </td>
                                ))}
                                <td className="px-3 py-2 text-red-600 text-xs">
                                  {item.errors.join('; ')}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Notes + Confirm */}
                      {excelPreview.valid_count > 0 && (
                        <div className="space-y-3">
                          <textarea
                            placeholder="비고 (선택사항)"
                            value={excelNotes}
                            onChange={(e) => setExcelNotes(e.target.value)}
                            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                            rows={2}
                          />
                          <div className="flex justify-end">
                            <Button
                              onClick={() => confirmExcelMutation.mutate()}
                              loading={confirmExcelMutation.isPending}
                            >
                              {excelPreview.valid_count}건 주문 생성
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </StepCard>
            )}
          </div>
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
