import { useState, useCallback, useRef, useEffect } from 'react';
import {
  PlusIcon,
  TrashIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';
import { placesApi, type PlaceRecommendationV2 } from '@/api/places';
import { ordersApi } from '@/api/orders';
import { useAuthStore } from '@/store/auth';
import { formatNumber } from '@/utils/format';
import Button from '@/components/common/Button';

interface SimplifiedRow {
  id: string;
  place_url: string;
  start_date: string;
  daily_limit: number;
  duration_days: number;
  target_keyword: string;
  campaign_type: 'traffic' | 'save';
  // Computed
  total_quantity: number;
  end_date: string;
  // AI recommendation
  recommendation: PlaceRecommendationV2 | null;
  recommendLoading: boolean;
}

interface SimplifiedOrderGridProps {
  onSuccess: () => void;
}

function generateId(): string {
  return Math.random().toString(36).slice(2, 11);
}

function computeEndDate(startDate: string, durationDays: number): string {
  if (!startDate || durationDays <= 0) return '';
  try {
    const d = new Date(startDate);
    if (isNaN(d.getTime())) return '';
    d.setDate(d.getDate() + durationDays);
    return d.toISOString().split('T')[0];
  } catch {
    return '';
  }
}

function createEmptyRow(): SimplifiedRow {
  const today = new Date().toISOString().split('T')[0];
  return {
    id: generateId(),
    place_url: '',
    start_date: today,
    daily_limit: 100,
    duration_days: 7,
    target_keyword: '',
    campaign_type: 'traffic',
    total_quantity: 700,
    end_date: computeEndDate(today, 7),
    recommendation: null,
    recommendLoading: false,
  };
}

export default function SimplifiedOrderGrid({ onSuccess }: SimplifiedOrderGridProps) {
  const [rows, setRows] = useState<SimplifiedRow[]>([createEmptyRow()]);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const user = useAuthStore((s) => s.user);
  const timerRefs = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      timerRefs.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  const updateRow = useCallback((rowId: string, updates: Partial<SimplifiedRow>) => {
    setRows((prev) =>
      prev.map((row) => {
        if (row.id !== rowId) return row;
        const updated = { ...row, ...updates };
        updated.total_quantity = updated.daily_limit * updated.duration_days;
        updated.end_date = computeEndDate(updated.start_date, updated.duration_days);
        return updated;
      })
    );
  }, []);

  const fetchRecommendation = useCallback(
    (rowId: string, url: string) => {
      const prev = timerRefs.current.get(rowId);
      if (prev) clearTimeout(prev);

      if (!url || !user?.company_id) {
        updateRow(rowId, { recommendation: null, recommendLoading: false });
        return;
      }

      if (!/\d{5,}/.test(url)) return;

      updateRow(rowId, { recommendLoading: true });

      const timer = setTimeout(async () => {
        try {
          const result = await placesApi.recommendBoth({
            place_url: url,
            company_id: user.company_id!,
          });
          setRows((prev) =>
            prev.map((row) => {
              if (row.id !== rowId) return row;
              return {
                ...row,
                recommendation: result,
                recommendLoading: false,
                campaign_type: result.recommended_campaign_type,
              };
            })
          );
        } catch {
          setRows((prev) =>
            prev.map((row) =>
              row.id === rowId ? { ...row, recommendation: null, recommendLoading: false } : row
            )
          );
        }
      }, 500);

      timerRefs.current.set(rowId, timer);
    },
    [user?.company_id, updateRow]
  );

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, createEmptyRow()]);
  }, []);

  const deleteRow = useCallback((rowId: string) => {
    setRows((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((r) => r.id !== rowId);
    });
  }, []);

  const copyRow = useCallback((rowId: string) => {
    setRows((prev) => {
      const idx = prev.findIndex((r) => r.id === rowId);
      if (idx === -1) return prev;
      const copy: SimplifiedRow = {
        ...prev[idx],
        id: generateId(),
        recommendation: prev[idx].recommendation,
        recommendLoading: false,
      };
      const newRows = [...prev];
      newRows.splice(idx + 1, 0, copy);
      return newRows;
    });
  }, []);

  const handleSubmit = async () => {
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      if (!row.place_url) {
        alert(`${i + 1}행: 플레이스 URL을 입력해주세요.`);
        return;
      }
      if (!row.start_date) {
        alert(`${i + 1}행: 작업 시작일을 입력해주세요.`);
        return;
      }
      if (row.daily_limit < 1) {
        alert(`${i + 1}행: 일 작업량은 1 이상이어야 합니다.`);
        return;
      }
      if (row.duration_days < 1) {
        alert(`${i + 1}행: 작업 기간은 1일 이상이어야 합니다.`);
        return;
      }
    }

    setSubmitting(true);
    try {
      await ordersApi.createSimplified({
        items: rows.map((row) => ({
          place_url: row.place_url,
          start_date: row.start_date,
          daily_limit: row.daily_limit,
          duration_days: row.duration_days,
          target_keyword: row.target_keyword,
          campaign_type: row.campaign_type,
        })),
        notes: notes || undefined,
      });
      onSuccess();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '주문 제출에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const totalQuantity = rows.reduce((sum, r) => sum + r.total_quantity, 0);

  return (
    <div className="space-y-4">
      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={addRow} icon={<PlusIcon className="h-4 w-4" />}>
          행 추가
        </Button>
      </div>

      {/* Grid table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 w-10">#</th>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 min-w-[220px]">
                플레이스 URL <span className="text-red-500">*</span>
              </th>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 w-32">
                작업 시작일 <span className="text-red-500">*</span>
              </th>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 w-24">
                일 작업량(타수) <span className="text-red-500">*</span>
              </th>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 w-24">
                작업 기간(일) <span className="text-red-500">*</span>
              </th>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 w-32">
                목표 노출 키워드
              </th>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 w-24">
                캠페인 타입
              </th>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 min-w-[240px]">
                AI 추천
              </th>
              <th className="px-2 py-3 text-center text-xs font-semibold text-gray-600 w-20">총 수량</th>
              <th className="px-2 py-3 text-left text-xs font-semibold text-gray-600 w-28">마감일</th>
              <th className="px-2 py-3 w-16" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {rows.map((row, rowIdx) => (
              <tr key={row.id} className="hover:bg-gray-50/50 align-top">
                <td className="px-2 py-2 text-gray-400 font-medium">{rowIdx + 1}</td>

                {/* 플레이스 URL */}
                <td className="px-1 py-1">
                  <input
                    type="url"
                    value={row.place_url}
                    onChange={(e) => {
                      updateRow(row.id, { place_url: e.target.value });
                      fetchRecommendation(row.id, e.target.value);
                    }}
                    placeholder="https://m.place.naver.com/..."
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                  />
                </td>

                {/* 작업 시작일 */}
                <td className="px-1 py-1">
                  <input
                    type="date"
                    value={row.start_date}
                    onChange={(e) => updateRow(row.id, { start_date: e.target.value })}
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                  />
                </td>

                {/* 일 작업량(타수) */}
                <td className="px-1 py-1">
                  <input
                    type="number"
                    value={row.daily_limit}
                    min={1}
                    onChange={(e) =>
                      updateRow(row.id, { daily_limit: Math.max(1, parseInt(e.target.value) || 1) })
                    }
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded text-right focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                  />
                </td>

                {/* 작업 기간(일) */}
                <td className="px-1 py-1">
                  <input
                    type="number"
                    value={row.duration_days}
                    min={1}
                    onChange={(e) =>
                      updateRow(row.id, { duration_days: Math.max(1, parseInt(e.target.value) || 1) })
                    }
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded text-right focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                  />
                </td>

                {/* 목표 노출 키워드 */}
                <td className="px-1 py-1">
                  <input
                    type="text"
                    value={row.target_keyword}
                    onChange={(e) => updateRow(row.id, { target_keyword: e.target.value })}
                    placeholder="키워드 입력"
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
                  />
                </td>

                {/* 캠페인 타입 (AI 자동 배정, 사용자 변경 가능) */}
                <td className="px-1 py-1">
                  <CampaignTypeToggle
                    value={row.campaign_type}
                    onChange={(val) => updateRow(row.id, { campaign_type: val })}
                  />
                </td>

                {/* AI 추천 */}
                <td className="px-2 py-1">
                  <RecommendationInfo
                    recommendation={row.recommendation}
                    loading={row.recommendLoading}
                  />
                </td>

                {/* 총 수량 (readonly) */}
                <td className="px-2 py-2 text-sm text-gray-700 text-center font-medium bg-gray-50/50">
                  {formatNumber(row.total_quantity)}
                </td>

                {/* 마감일 (readonly) */}
                <td className="px-2 py-2 text-sm text-gray-600 bg-gray-50/50">{row.end_date}</td>

                {/* Actions */}
                <td className="px-1 py-1">
                  <div className="flex items-center gap-0.5">
                    <button
                      onClick={() => copyRow(row.id)}
                      className="p-1 text-gray-400 hover:text-primary-600 transition-colors"
                      title="행 복사"
                    >
                      <DocumentDuplicateIcon className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => deleteRow(row.id)}
                      className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                      title="행 삭제"
                      disabled={rows.length <= 1}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Notes + Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">비고</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="주문 관련 메모를 입력하세요..."
          />
        </div>

        <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">총 건수</span>
            <span className="font-medium text-gray-900">{formatNumber(rows.length)}건</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">총 수량</span>
            <span className="font-medium text-gray-900">{formatNumber(totalQuantity)}타</span>
          </div>
          <div className="border-t border-gray-200 pt-2" />
          <div className="text-xs text-gray-400">
            실제 금액은 서버에서 가격 정책 기반으로 계산됩니다.
          </div>
        </div>
      </div>

      {/* Submit */}
      <div className="flex justify-end">
        <Button size="lg" onClick={handleSubmit} loading={submitting} disabled={rows.length === 0}>
          주문 접수 ({formatNumber(rows.length)}건)
        </Button>
      </div>
    </div>
  );
}

// ─── 캠페인 타입 토글 (AI 추천 기본값, 사용자 변경 가능) ──────────

function CampaignTypeToggle({
  value,
  onChange,
}: {
  value: 'traffic' | 'save';
  onChange: (v: 'traffic' | 'save') => void;
}) {
  return (
    <div className="flex rounded-md border border-gray-300 overflow-hidden">
      <button
        type="button"
        onClick={() => onChange('traffic')}
        className={`flex-1 px-2 py-1.5 text-xs font-medium transition-colors ${
          value === 'traffic'
            ? 'bg-blue-600 text-white'
            : 'bg-white text-gray-500 hover:bg-gray-50'
        }`}
      >
        트래픽
      </button>
      <button
        type="button"
        onClick={() => onChange('save')}
        className={`flex-1 px-2 py-1.5 text-xs font-medium transition-colors ${
          value === 'save'
            ? 'bg-purple-600 text-white'
            : 'bg-white text-gray-500 hover:bg-gray-50'
        }`}
      >
        저장
      </button>
    </div>
  );
}

// ─── AI 추천 정보 표시 ───────────────────────────────────────────

function RecommendationInfo({
  recommendation,
  loading,
}: {
  recommendation: PlaceRecommendationV2 | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="flex items-center gap-1.5">
        <svg className="animate-spin h-3.5 w-3.5 text-primary-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        <span className="text-xs text-gray-400">AI 분석 중...</span>
      </div>
    );
  }
  if (!recommendation) {
    return <span className="text-xs text-gray-300">URL 입력 시 자동 추천</span>;
  }

  const rec = recommendation;
  const recType = rec.recommended_campaign_type;
  const typeRec = recType === 'traffic' ? rec.traffic : rec.save;

  return (
    <div className="space-y-1">
      {/* 배지 라인 */}
      <div className="flex flex-wrap items-center gap-1">
        {/* 신규/기존 */}
        <span
          className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${
            rec.is_existing
              ? 'bg-orange-100 text-orange-700'
              : 'bg-green-100 text-green-700'
          }`}
        >
          {rec.is_existing ? '기존' : '신규'}
        </span>

        {/* 추천 캠페인 타입 */}
        <span
          className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${
            recType === 'traffic'
              ? 'bg-blue-100 text-blue-700'
              : 'bg-purple-100 text-purple-700'
          }`}
        >
          {recType === 'traffic' ? '트래픽' : '저장'}
        </span>

        {/* 연장 배지 */}
        {typeRec.recommended_action === 'extend' && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-yellow-100 text-yellow-700">
            연장
          </span>
        )}

        {/* 네트워크 */}
        {typeRec.recommended_network && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-700">
            {typeRec.recommended_network}
          </span>
        )}
      </div>

      {/* 추천 사유 */}
      <div className="text-[11px] text-gray-500 leading-tight">
        {rec.recommendation_reason}
      </div>

      {/* 남은 네트워크 수 */}
      <div className="text-[10px] text-gray-400">
        남은 네트워크: 트래픽 {rec.traffic.available_networks}개 / 저장 {rec.save.available_networks}개
      </div>
    </div>
  );
}
