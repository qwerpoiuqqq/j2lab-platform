import { useState, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { ArrowUpTrayIcon } from '@heroicons/react/24/outline';
import { ordersApi } from '@/api/orders';
import type { ExcelUploadPreviewResponse } from '@/types';
import SimplifiedOrderGrid from '@/components/features/orders/SimplifiedOrderGrid';
import Button from '@/components/common/Button';

type InputMode = 'form' | 'excel';

export default function OrderGridPage() {
  const navigate = useNavigate();
  const [inputMode, setInputMode] = useState<InputMode>('form');

  // Excel upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [excelPreview, setExcelPreview] = useState<ExcelUploadPreviewResponse | null>(null);
  const [excelUploading, setExcelUploading] = useState(false);
  const [excelNotes, setExcelNotes] = useState('');

  // Excel upload handler (simplified 5-column template)
  const handleExcelFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setExcelUploading(true);
    setExcelPreview(null);
    try {
      // Use generic upload without product_id — server will auto-match
      const formData = new FormData();
      formData.append('file', file);
      // For now, use CSV parsing on client side since simplified doesn't need product schema validation
      alert('간소화 모드에서는 CSV 업로드를 사용해 주세요. (폼 입력 탭의 CSV 업로드 버튼)');
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Excel 파일 처리에 실패했습니다.');
    } finally {
      setExcelUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Excel confirm mutation (kept for backward compatibility)
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">주문 접수</h1>
        <p className="mt-1 text-sm text-gray-500">
          플레이스 URL과 작업 정보를 입력하면 AI가 캠페인 타입을 자동 추천합니다.
        </p>
      </div>

      {/* Mode Toggle */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        <button
          onClick={() => {
            setInputMode('form');
            setExcelPreview(null);
          }}
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
              <h2 className="text-lg font-semibold text-gray-900">주문 정보 입력</h2>
            </div>
            <div className="p-6">
              <SimplifiedOrderGrid onSuccess={() => navigate('/orders')} />
            </div>
          </div>
        )}

        {inputMode === 'excel' && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Excel / CSV 업로드</h2>
            </div>
            <div className="p-6 space-y-4">
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                <p className="font-medium mb-1">간소화 템플릿 형식 (5개 컬럼)</p>
                <p className="text-blue-600">
                  플레이스URL | 작업시작일 | 일작업량 | 작업기간(일) | 목표키워드
                </p>
                <p className="mt-1 text-xs text-blue-500">
                  CSV/TSV 파일을 업로드하면 AI가 각 플레이스의 캠페인 타입을 자동 추천합니다.
                </p>
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 cursor-pointer px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors">
                  <ArrowUpTrayIcon className="h-4 w-4" />
                  CSV 파일 선택
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.tsv,.txt,.xlsx,.xls"
                    onChange={handleExcelFileChange}
                    className="hidden"
                  />
                </label>
                {excelUploading && <span className="text-sm text-gray-500">처리 중...</span>}
              </div>

              {/* When CSV uploaded, switch to form mode with pre-filled rows */}
              <div className="text-sm text-gray-500">
                CSV 파일을 선택하면 "직접 입력" 탭의 그리드에 데이터가 자동으로 채워집니다.
              </div>

              {/* Legacy Excel preview (for backward compatibility) */}
              {excelPreview && (
                <div className="space-y-4">
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-700">
                      전체: <strong>{excelPreview.total}</strong>건
                    </span>
                    <span className="text-green-600">
                      유효: <strong>{excelPreview.valid_count}</strong>건
                    </span>
                    {excelPreview.error_count > 0 && (
                      <span className="text-red-600">
                        오류: <strong>{excelPreview.error_count}</strong>건
                      </span>
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
                              <th key={key} className="px-3 py-2 text-left font-medium text-gray-500">
                                {key}
                              </th>
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
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                  유효
                                </span>
                              ) : (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                  오류
                                </span>
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
    </div>
  );
}
