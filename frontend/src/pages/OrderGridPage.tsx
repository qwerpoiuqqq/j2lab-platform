import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ArrowUpTrayIcon, ArrowDownTrayIcon, ArrowLeftIcon } from '@heroicons/react/24/outline';
import { productsApi } from '@/api/products';
import { ordersApi } from '@/api/orders';
import type { Product, ExcelUploadPreviewResponse } from '@/types';
import { normalizeSchema } from '@/utils/schema';
import OrderGrid, { type OrderGridRow } from '@/components/features/orders/OrderGrid';
import Button from '@/components/common/Button';

type InputMode = 'form' | 'excel';

export default function OrderGridPage() {
  const navigate = useNavigate();
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [inputMode, setInputMode] = useState<InputMode>('form');

  // Excel upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [excelPreview, setExcelPreview] = useState<ExcelUploadPreviewResponse | null>(null);
  const [excelUploading, setExcelUploading] = useState(false);
  const [excelNotes, setExcelNotes] = useState('');
  const [orderSubmitting, setOrderSubmitting] = useState(false);

  // Fetch products
  const { data: productsData, isLoading: productsLoading } = useQuery({
    queryKey: ['products', { size: 100, is_active: true }],
    queryFn: () => productsApi.list({ size: 100, is_active: true }),
  });
  const products = productsData?.items ?? [];

  // Reset when product changes
  useEffect(() => {
    setExcelPreview(null);
    setExcelNotes('');
  }, [selectedProduct]);

  // Template download
  const handleDownloadTemplate = async (product: Product) => {
    try {
      const blob = await ordersApi.downloadExcelTemplate(product.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${product.name}_템플릿.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('템플릿 다운로드에 실패했습니다.');
    }
  };

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

  // Excel confirm mutation
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
    onSuccess: () => navigate('/orders'),
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Excel 주문 생성에 실패했습니다.');
    },
  });

  // Direct input submit
  const handleDirectSubmit = async (items: OrderGridRow[], notes: string) => {
    if (!selectedProduct) return;
    setOrderSubmitting(true);
    try {
      await ordersApi.create({
        notes: notes || undefined,
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
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setSelectedProduct(null);
                setExcelPreview(null);
              }}
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
          </div>

          {/* Mode Toggle */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
            <button
              onClick={() => setInputMode('form')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                inputMode === 'form'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              직접 입력
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

          {/* Content */}
          <div className="min-h-[300px]">
            {inputMode === 'form' && (
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
                    enableAI
                  />
                </div>
              </div>
            )}

            {inputMode === 'excel' && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">Excel 업로드</h2>
                </div>
                <div className="p-6 space-y-4">
                  <div className="flex items-center gap-3">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleDownloadTemplate(selectedProduct)}
                      icon={<ArrowDownTrayIcon className="h-4 w-4" />}
                    >
                      템플릿 다운로드
                    </Button>
                    <label className="flex items-center gap-2 cursor-pointer px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors">
                      <ArrowUpTrayIcon className="h-4 w-4" />
                      Excel 파일 업로드
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
                              {excelPreview.items[0] &&
                                Object.keys(excelPreview.items[0].data).map((key) => (
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
                                <td className="px-3 py-2 text-red-600 text-xs">{item.errors.join('; ')}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

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
              </div>
            )}
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
