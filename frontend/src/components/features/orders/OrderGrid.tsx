import React, { useState, useCallback, useRef, useEffect } from 'react';
import type { Product, FormFieldExtended, CalcFormula, DateCalcFormula, CombinedProductConfig } from '@/types';
import { formatCurrency, formatNumber, getCampaignTypeLabel } from '@/utils/format';
import { getCalcFormula, getDateCalcFormula, getDateDiffFormula } from '@/utils/schema';
import { placesApi, type PlaceRecommendationV2 } from '@/api/places';
import { useAuthStore } from '@/store/auth';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import {
  PlusIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import { ExclamationTriangleIcon } from '@heroicons/react/20/solid';

export type OrderGridRow = Record<string, string | number>;

// ─── Place URL normalization ────────────────────────────────────────

/**
 * Normalize a Naver Place URL to canonical format: https://m.place.naver.com/{type}/{mid}
 * Strips query params, hash, /home suffix, etc.
 * Returns { url, warning } — warning is set for unsupported formats.
 */
function normalizePlaceUrl(raw: string): { url: string; warning: string } {
  const trimmed = raw.trim();
  if (!trimmed) return { url: '', warning: '' };

  // naver.me short URLs — cannot resolve client-side
  if (/naver\.me/i.test(trimmed)) {
    return {
      url: trimmed,
      warning: 'naver.me 단축 URL은 사용할 수 없습니다. 모바일 플레이스 URL(https://m.place.naver.com/...)을 입력해주세요.',
    };
  }

  // PC URL (place.naver.com without 'm.' prefix)
  if (/^https?:\/\/place\.naver\.com\//i.test(trimmed)) {
    return {
      url: trimmed,
      warning: 'PC 주소입니다. 모바일 주소(https://m.place.naver.com/...)로 변환해서 입력해주세요.',
    };
  }

  // Extract from m.place.naver.com URL
  const mPlaceMatch = trimmed.match(
    /https?:\/\/m\.place\.naver\.com\/([a-zA-Z]+)\/(\d+)/i
  );
  if (mPlaceMatch) {
    const normalized = `https://m.place.naver.com/${mPlaceMatch[1]}/${mPlaceMatch[2]}`;
    return { url: normalized, warning: '' };
  }

  // map.naver.com with place ID
  const mapMatch = trimmed.match(/https?:\/\/map\.naver\.com\/.*?place\/(\d+)/i);
  if (mapMatch) {
    return {
      url: trimmed,
      warning: `지도 URL입니다. 모바일 플레이스 URL(https://m.place.naver.com/.../${mapMatch[1]})로 변환해서 입력해주세요.`,
    };
  }

  // Not a recognized Naver URL — return as-is
  return { url: trimmed, warning: '' };
}

interface OrderGridProps {
  product: Product;
  schema: FormFieldExtended[];
  onSubmit: (items: OrderGridRow[], notes: string) => void;
  submitting?: boolean;
  effectivePrice?: number;
  mode?: 'single' | 'combined';
  combinedConfig?: CombinedProductConfig;
  enableAI?: boolean;
}

// ─── Row-level AI state ──────────────────────────────────────────────

interface RowAIState {
  recommendation: PlaceRecommendationV2 | null;
  loading: boolean;
  networkName: string;
}

// ─── Formula evaluation ──────────────────────────────────────────────

function evaluateCalcFormula(formula: CalcFormula, row: OrderGridRow): number {
  try {
    const a = Number(row[formula.fieldA]) || 0;
    const b = Number(row[formula.fieldB]) || 0;
    switch (formula.operator) {
      case '+': return Math.round(a + b);
      case '-': return Math.round(a - b);
      case '*': return Math.round(a * b);
      case '/': return b !== 0 ? Math.round(a / b) : 0;
    }
    return 0;
  } catch {
    return 0;
  }
}

function evaluateDateCalcFormula(formula: DateCalcFormula, row: OrderGridRow): string {
  try {
    const baseVal = row[formula.dateField];
    if (!baseVal) return '';
    const baseDate = new Date(String(baseVal));
    if (isNaN(baseDate.getTime())) return '';
    const days = parseInt(String(row[formula.daysField])) || 0;
    baseDate.setDate(baseDate.getDate() + days);
    return baseDate.toISOString().split('T')[0];
  } catch {
    return '';
  }
}

function evaluateDateDiffFormula(formula: { startField: string; endField: string }, row: OrderGridRow): number {
  try {
    const startVal = row[formula.startField];
    const endVal = row[formula.endField];
    if (!startVal || !endVal) return 0;
    const start = new Date(String(startVal));
    const end = new Date(String(endVal));
    if (isNaN(start.getTime()) || isNaN(end.getTime())) return 0;
    const diffMs = end.getTime() - start.getTime();
    const days = Math.round(diffMs / (1000 * 60 * 60 * 24)) + 1;
    return days > 0 ? days : 0;
  } catch {
    return 0;
  }
}

function createEmptyRow(schema: FormFieldExtended[]): OrderGridRow {
  const row: OrderGridRow = {};
  for (const field of schema) {
    if (field.default !== undefined) {
      row[field.name] = field.default;
    } else if (field.type === 'checkbox') {
      row[field.name] = 1;
    } else if (field.type === 'number' || field.type === 'calc' || field.type === 'date_diff') {
      row[field.name] = 0;
    } else {
      row[field.name] = '';
    }
  }
  return row;
}

function computeRow(row: OrderGridRow, schema: FormFieldExtended[]): OrderGridRow {
  const computed = { ...row };
  for (const field of schema) {
    if (field.group && !computed[field.group]) {
      if (field.type === 'calc') computed[field.name] = 0;
      else if (field.type === 'date_calc') computed[field.name] = '';
      continue;
    }
    if (field.type === 'date_diff') {
      const f = getDateDiffFormula(field);
      if (f) computed[field.name] = evaluateDateDiffFormula(f, computed);
    } else if (field.type === 'calc') {
      const f = getCalcFormula(field);
      if (f) computed[field.name] = evaluateCalcFormula(f, computed);
    } else if (field.type === 'date_calc') {
      const f = getDateCalcFormula(field);
      if (f) computed[field.name] = evaluateDateCalcFormula(f, computed);
    }
  }
  return computed;
}

export default function OrderGrid({
  product,
  schema,
  onSubmit,
  submitting,
  effectivePrice,
  mode = 'single',
  combinedConfig,
  enableAI = false,
}: OrderGridProps) {
  const [rows, setRows] = useState<OrderGridRow[]>([computeRow(createEmptyRow(schema), schema)]);
  const [notes, setNotes] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [hasTodayRows, setHasTodayRows] = useState(false);
  const user = useAuthStore((s) => s.user);

  // AI recommendation state per row
  const [aiStates, setAiStates] = useState<RowAIState[]>([{ recommendation: null, loading: false, networkName: '' }]);
  const timerRefs = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  // URL warning state per row
  const [urlWarnings, setUrlWarnings] = useState<string[]>(['']);

  // Find url field in schema for AI trigger
  const urlFieldName = schema.find((f) => f.type === 'url')?.name || '';
  const campaignTypeFieldName = enableAI ? schema.find((f) => f.name === 'campaign_type')?.name || '' : '';

  useEffect(() => {
    return () => {
      timerRefs.current.forEach((t) => clearTimeout(t));
    };
  }, []);


  const quantityField = schema.find((f) => f.is_quantity);

  const updateRow = useCallback((rowIdx: number, fieldName: string, value: string | number) => {
    setRows((prev) => {
      const updated = [...prev];
      updated[rowIdx] = computeRow({ ...updated[rowIdx], [fieldName]: value }, schema);
      return updated;
    });
  }, [schema]);

  // AI recommendation fetch
  const fetchRecommendation = useCallback((rowIdx: number, url: string) => {
    const prev = timerRefs.current.get(rowIdx);
    if (prev) clearTimeout(prev);

    if (!url || !user?.company_id || !/\d{5,}/.test(url)) {
      setAiStates((s) => {
        const ns = [...s];
        if (ns[rowIdx]) ns[rowIdx] = { recommendation: null, loading: false, networkName: '' };
        return ns;
      });
      return;
    }

    setAiStates((s) => {
      const ns = [...s];
      if (ns[rowIdx]) ns[rowIdx] = { ...ns[rowIdx], loading: true };
      return ns;
    });

    const timer = setTimeout(async () => {
      try {
        const result = await placesApi.recommendBoth({
          place_url: url,
          company_id: user!.company_id!,
        });
        const recType = result.recommended_campaign_type;
        const typeRec = recType === 'traffic' ? result.traffic : result.save;

        setAiStates((s) => {
          const ns = [...s];
          ns[rowIdx] = {
            recommendation: result,
            loading: false,
            networkName: typeRec.recommended_network || '',
          };
          return ns;
        });

        // Auto-set campaign_type field if it exists
        if (campaignTypeFieldName) {
          setRows((prev) => {
            const updated = [...prev];
            if (updated[rowIdx]) {
              updated[rowIdx] = computeRow({ ...updated[rowIdx], [campaignTypeFieldName]: recType }, schema);
            }
            return updated;
          });
        }
      } catch {
        setAiStates((s) => {
          const ns = [...s];
          if (ns[rowIdx]) ns[rowIdx] = { recommendation: null, loading: false, networkName: '' };
          return ns;
        });
      }
    }, 500);

    timerRefs.current.set(rowIdx, timer);
  }, [user?.company_id, campaignTypeFieldName, schema]);

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, computeRow(createEmptyRow(schema), schema)]);
    setAiStates((prev) => [...prev, { recommendation: null, loading: false, networkName: '' }]);
    setUrlWarnings((prev) => [...prev, '']);
  }, [schema]);

  const deleteRow = useCallback((idx: number) => {
    setRows((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((_, i) => i !== idx);
    });
    setAiStates((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((_, i) => i !== idx);
    });
    setUrlWarnings((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((_, i) => i !== idx);
    });
  }, []);

  const copyRow = useCallback((idx: number) => {
    setRows((prev) => {
      const newRow = computeRow({ ...prev[idx] }, schema);
      const newRows = [...prev];
      newRows.splice(idx + 1, 0, newRow);
      return newRows;
    });
    setAiStates((prev) => {
      const copied = prev[idx] ? { ...prev[idx] } : { recommendation: null, loading: false, networkName: '' };
      const ns = [...prev];
      ns.splice(idx + 1, 0, copied);
      return ns;
    });
    setUrlWarnings((prev) => {
      const ns = [...prev];
      ns.splice(idx + 1, 0, prev[idx] || '');
      return ns;
    });
  }, [schema]);

  // Combined mode price calculations
  const trafficTotalQty = mode === 'combined' && combinedConfig
    ? rows.reduce((sum, row) => {
        if (!row.traffic_enabled) return sum;
        return sum + ((Number(row.traffic_daily_limit) || 0) * (Number(row.traffic_duration_days) || 0));
      }, 0)
    : 0;

  const saveTotalQty = mode === 'combined' && combinedConfig
    ? rows.reduce((sum, row) => {
        if (!row.save_enabled) return sum;
        return sum + ((Number(row.save_daily_limit) || 0) * (Number(row.save_duration_days) || 0));
      }, 0)
    : 0;

  const trafficSubtotal = mode === 'combined' && combinedConfig ? trafficTotalQty * combinedConfig.trafficPrice : 0;
  const saveSubtotal = mode === 'combined' && combinedConfig ? saveTotalQty * combinedConfig.savePrice : 0;

  const subtotal = mode === 'combined'
    ? trafficSubtotal + saveSubtotal
    : rows.reduce((sum, row) => {
        if (quantityField) {
          const qty = Number(row[quantityField.name]) || 0;
          return sum + qty * (effectivePrice ?? product.base_price);
        }
        const calcField = schema.find((f) => f.type === 'calc' && f.formula);
        if (calcField) {
          return sum + (Number(row[calcField.name]) || 0);
        }
        const qty = Number(row['quantity']) || 0;
        const price = Number(row['unit_price']) || (effectivePrice ?? product.base_price);
        return sum + qty * price;
      }, 0);

  const vat = Math.round(subtotal * 0.1);
  const total = subtotal + vat;

  const handleSubmit = () => {
    // URL 경고가 있는 행 체크
    for (let i = 0; i < urlWarnings.length; i++) {
      if (urlWarnings[i]) {
        alert(`${i + 1}행: ${urlWarnings[i]}`);
        return;
      }
    }

    const minDaily = product.min_daily_limit;
    const minDays = product.min_work_days;
    const maxDays = product.max_work_days;

    for (let i = 0; i < rows.length; i++) {
      if (mode === 'combined') {
        if (!rows[i].traffic_enabled && !rows[i].save_enabled) {
          alert(`${i + 1}행: 트래픽 또는 저장하기 중 최소 1개를 선택해야 합니다.`);
          return;
        }
        if (rows[i].traffic_enabled) {
          if (!Number(rows[i].traffic_daily_limit) || !Number(rows[i].traffic_duration_days)) {
            alert(`${i + 1}행: 트래픽 타수와 기간을 입력해주세요.`);
            return;
          }
        }
        if (rows[i].save_enabled) {
          if (!Number(rows[i].save_daily_limit) || !Number(rows[i].save_duration_days)) {
            alert(`${i + 1}행: 저장 타수와 기간을 입력해주세요.`);
            return;
          }
        }
      }

      // 상품 제약조건 검증
      const dailyLimit = Number(rows[i]['daily_limit']);
      const durationDays = Number(rows[i]['duration_days']);
      if (minDaily && dailyLimit && dailyLimit < minDaily) {
        alert(`${i + 1}행: 일 작업량은 최소 ${minDaily} 이상이어야 합니다.`);
        return;
      }
      if (minDays && durationDays && durationDays < minDays) {
        alert(`${i + 1}행: 작업 기간은 최소 ${minDays}일 이상이어야 합니다.`);
        return;
      }
      if (maxDays && durationDays && durationDays > maxDays) {
        alert(`${i + 1}행: 작업 기간은 최대 ${maxDays}일 이하여야 합니다.`);
        return;
      }

      for (const field of schema) {
        if (field.group && !rows[i][field.group]) continue;
        if (field.required && !rows[i][field.name] && rows[i][field.name] !== 0) {
          alert(`${i + 1}행: ${field.label} 항목은 필수입니다.`);
          return;
        }
      }
    }

    // 당일 구동건 체크 후 확인 모달 표시
    const today = new Date().toISOString().split('T')[0];
    const todayFound = rows.some((row) => {
      return Object.values(row).some((v) => v === today);
    });
    setHasTodayRows(todayFound);
    setConfirmOpen(true);
  };

  const handleConfirmedSubmit = () => {
    setConfirmOpen(false);
    onSubmit(rows, notes);
  };

  const handleKeyDown = (e: React.KeyboardEvent, rowIdx: number, colIdx: number) => {
    if (e.key === 'Tab') return;
    if (e.key === 'Enter') {
      e.preventDefault();
      const nextRow = rowIdx + 1;
      if (nextRow < rows.length) {
        const nextInput = document.querySelector(
          `[data-row="${nextRow}"][data-col="${colIdx}"]`,
        ) as HTMLElement;
        nextInput?.focus();
      }
    }
  };

  // Get network list from current row's AI state
  const getNetworkList = (rowIdx: number) => {
    const ai = aiStates[rowIdx];
    if (!ai?.recommendation) return [];
    const row = rows[rowIdx];
    const currentType = campaignTypeFieldName ? String(row[campaignTypeFieldName] || 'traffic') : 'traffic';
    const typeRec = currentType === 'traffic' ? ai.recommendation.traffic : ai.recommendation.save;
    return typeRec.available_network_list || [];
  };

  return (
    <div className="space-y-4">
      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={addRow} icon={<PlusIcon className="h-4 w-4" />}>
          행 추가
        </Button>
      </div>

      {/* Grid table */}
      <div className="overflow-auto max-h-[60vh] border border-border rounded-lg">
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-surface-raised sticky top-0 z-10">
            <tr>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase w-12">#</th>
              {schema.map((field) => (
                <th
                  key={field.name}
                  className={`px-3 py-3 text-left text-xs font-medium uppercase whitespace-nowrap${
                    field.type === 'url' ? ' min-w-[340px]' : ''
                  }`}
                  style={field.color ? { backgroundColor: field.color, color: '#fff' } : undefined}
                >
                  {field.label}
                  {field.required && !field.group && <span className="text-red-500 ml-0.5">*</span>}
                </th>
              ))}
              {/* AI: 네트워크 선택 컬럼 */}
              {enableAI && (
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase whitespace-nowrap">
                  네트워크
                </th>
              )}
              <th className="px-3 py-3 w-12" />
            </tr>
          </thead>
          <tbody className="bg-surface">
            {rows.map((row, rowIdx) => {
              const ai = aiStates[rowIdx] || { recommendation: null, loading: false, networkName: '' };
              const networkList = enableAI ? getNetworkList(rowIdx) : [];
              const hasAI = enableAI && (ai.loading || ai.recommendation);

              return (
                <React.Fragment key={rowIdx}>
                  {/* 데이터 행 */}
                  <tr className="border-t border-border hover:bg-surface-raised align-top">
                    <td className="px-3 py-2 text-sm text-gray-400">{rowIdx + 1}</td>
                    {schema.map((field, colIdx) => (
                      <td key={field.name} className="px-1 py-1">
                        <GridCell
                          field={field}
                          value={row[field.name]}
                          onChange={(val) => {
                            // URL auto-normalization on paste/change
                            if (field.type === 'url' && field.name === urlFieldName) {
                              const { url: normalized, warning } = normalizePlaceUrl(String(val));
                              setUrlWarnings((prev) => {
                                const ns = [...prev];
                                ns[rowIdx] = warning;
                                return ns;
                              });
                              if (!warning && normalized !== String(val)) {
                                updateRow(rowIdx, field.name, normalized);
                              } else {
                                updateRow(rowIdx, field.name, val);
                              }
                              // AI: trigger recommendation on URL change
                              if (enableAI) {
                                fetchRecommendation(rowIdx, warning ? '' : normalized);
                              }
                            } else {
                              updateRow(rowIdx, field.name, val);
                            }
                          }}
                          onKeyDown={(e) => handleKeyDown(e, rowIdx, colIdx)}
                          rowIdx={rowIdx}
                          colIdx={colIdx}
                          disabled={!!field.group && !row[field.group]}
                        />
                      </td>
                    ))}
                    {/* 네트워크 드롭다운 */}
                    {enableAI && (
                      <td className="px-1 py-1">
                        {networkList.length > 0 ? (
                          <select
                            value={ai.networkName}
                            onChange={(e) => {
                              setAiStates((s) => {
                                const ns = [...s];
                                ns[rowIdx] = { ...ns[rowIdx], networkName: e.target.value };
                                return ns;
                              });
                            }}
                            className="w-full px-2 py-1.5 text-sm border border-border-strong rounded bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40"
                          >
                            {networkList.map((n) => (
                              <option key={n.id} value={n.name}>{n.name}</option>
                            ))}
                          </select>
                        ) : ai.recommendation ? (
                          <span className="text-xs text-gray-400 px-2">네트워크 없음</span>
                        ) : (
                          <span className="text-xs text-gray-600 px-2">URL 입력 후</span>
                        )}
                      </td>
                    )}
                    <td className="px-2 py-1 flex items-center gap-0.5">
                      <button onClick={() => copyRow(rowIdx)} className="p-1 text-gray-400 hover:text-primary-500 transition-colors" title="행 복사">
                        <DocumentDuplicateIcon className="h-4 w-4" />
                      </button>
                      <button onClick={() => deleteRow(rowIdx)} className="p-1 text-gray-400 hover:text-red-500 transition-colors" title="행 삭제" disabled={rows.length <= 1}>
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>

                  {/* URL 경고 메시지 */}
                  {urlWarnings[rowIdx] && (
                    <tr className="border-0">
                      <td />
                      <td colSpan={schema.length + (enableAI ? 2 : 1)} className="px-1 pb-1 pt-0">
                        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-900/20 rounded border border-amber-800/50 text-xs text-amber-400">
                          <ExclamationTriangleIcon className="h-3.5 w-3.5 shrink-0" />
                          {urlWarnings[rowIdx]}
                        </div>
                      </td>
                    </tr>
                  )}

                  {/* AI 제안 카드 — URL 입력 후 분석 결과 있을 때만 */}
                  {hasAI && (
                    <tr className="border-0">
                      <td />
                      <td colSpan={schema.length + (enableAI ? 2 : 1)} className="px-1 pb-3 pt-0">
                        <SuggestionCard
                          recommendation={ai.recommendation}
                          loading={ai.loading}
                          currentType={campaignTypeFieldName ? String(row[campaignTypeFieldName] || 'traffic') : 'traffic'}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Notes + Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">비고</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-border-strong px-3 py-2 text-sm bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400"
            placeholder="주문 관련 메모를 입력하세요..."
          />
        </div>

        {mode === 'combined' && combinedConfig ? (
          <div className="bg-surface-raised rounded-xl border border-border p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">총 건수</span>
              <span className="font-medium text-gray-100">{formatNumber(rows.length)}건</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">트래픽 ({formatNumber(trafficTotalQty)}타 x {formatCurrency(combinedConfig.trafficPrice)})</span>
              <span className="font-medium text-gray-100">{formatCurrency(trafficSubtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">저장하기 ({formatNumber(saveTotalQty)}타 x {formatCurrency(combinedConfig.savePrice)})</span>
              <span className="font-medium text-gray-100">{formatCurrency(saveSubtotal)}</span>
            </div>
            <div className="border-t border-border pt-2" />
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">공급가액</span>
              <span className="font-medium text-gray-100">{formatCurrency(subtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">부가세 (10%)</span>
              <span className="font-medium text-gray-100">{formatCurrency(vat)}</span>
            </div>
            <div className="border-t border-border pt-2 flex justify-between">
              <span className="text-base font-semibold text-gray-100">합계</span>
              <span className="text-base font-bold text-primary-600">{formatCurrency(total)}</span>
            </div>
          </div>
        ) : (
          <div className="bg-surface-raised rounded-xl border border-border p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">총 건수</span>
              <span className="font-medium text-gray-100">{formatNumber(rows.length)}건</span>
            </div>
            {quantityField && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">총 수량 ({quantityField.label})</span>
                <span className="font-medium text-gray-100">
                  {formatNumber(rows.reduce((s, r) => s + (Number(r[quantityField.name]) || 0), 0))}
                </span>
              </div>
            )}
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">공급가액</span>
              <span className="font-medium text-gray-100">{formatCurrency(subtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">부가세 (10%)</span>
              <span className="font-medium text-gray-100">{formatCurrency(vat)}</span>
            </div>
            <div className="border-t border-border pt-2 flex justify-between">
              <span className="text-base font-semibold text-gray-100">합계</span>
              <span className="text-base font-bold text-primary-600">{formatCurrency(total)}</span>
            </div>
          </div>
        )}
      </div>

      {/* Submit */}
      <div className="flex justify-end">
        <Button size="lg" onClick={handleSubmit} loading={submitting} disabled={rows.length === 0}>
          주문 제출 ({formatNumber(rows.length)}건)
        </Button>
      </div>

      {/* 발주 확인 모달 */}
      <Modal
        isOpen={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="발주 확인"
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              취소
            </Button>
            <Button onClick={handleConfirmedSubmit}>
              확인 및 제출
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-sm text-gray-300">
          <p>
            작업 발주건에 대한 잘못 기입하신 건의 책임은 귀하에게 있으며, 한번 더 체크 후 발주 부탁드립니다.
          </p>
          {hasTodayRows && (
            <div className="flex items-start gap-2 rounded-lg border border-amber-700/50 bg-amber-900/20 px-3 py-2.5 text-amber-400">
              <ExclamationTriangleIcon className="h-4 w-4 shrink-0 mt-0.5" />
              <p>
                작업 발주건에 당일 구동건이 포함되어 있습니다. 바로 캠페인 구동이 시작되며, 오기입에 대한 책임은 귀하에게 있습니다.
              </p>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}

// ─── AI 제안 카드 ────────────────────────────────────────────────

function SuggestionCard({
  recommendation,
  loading,
  currentType,
}: {
  recommendation: PlaceRecommendationV2 | null;
  loading: boolean;
  currentType: string;
}) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-primary-900/20 rounded-lg border border-primary-800/30 animate-pulse">
        <SparklesIcon className="h-4 w-4 text-primary-400 shrink-0" />
        <span className="text-xs text-primary-400">AI가 이 플레이스를 분석하고 있습니다...</span>
      </div>
    );
  }

  if (!recommendation) return null;

  const rec = recommendation;
  const recType = rec.recommended_campaign_type;
  const recTypeRec = recType === 'traffic' ? rec.traffic : rec.save;
  const placeName = rec.place_name;
  const placeLabel = placeName
    ? `${placeName} (${rec.is_existing ? '기존' : '신규'} 플레이스)`
    : (rec.is_existing ? '기존 플레이스' : '신규 플레이스');
  const actionText = recTypeRec.recommended_action === 'extend' ? '연장' : '신규 세팅';

  return (
    <div className="flex items-start gap-2 px-3 py-2.5 bg-surface-raised rounded-lg border border-border">
      <SparklesIcon className="h-4 w-4 text-primary-400 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-xs text-gray-300 leading-relaxed">
          <span className="font-medium text-primary-400">{placeLabel}</span>입니다.{' '}
          <span className={`font-semibold ${recType === 'traffic' ? 'text-primary-400' : 'text-purple-400'}`}>
            {recType === 'traffic' ? '트래픽' : '저장하기'}
          </span>
          {recTypeRec.recommended_network && (
            <> <span className="font-medium text-gray-200">{recTypeRec.recommended_network}</span></>
          )}
          으로 <span className="font-medium">{actionText}</span> 진행해보시는 건 어떨까요?
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-1.5">
          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${rec.is_existing ? 'bg-orange-900/30 text-orange-400' : 'bg-green-900/30 text-green-400'}`}>
            {rec.is_existing ? '기존' : '신규'}
          </span>
          {recTypeRec.recommended_action === 'extend' && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-yellow-900/30 text-yellow-400">연장 가능</span>
          )}
          <span className="text-[10px] text-gray-400">
            남은 네트워크: 트래픽 {rec.traffic.available_networks}개 / 저장하기 {rec.save.available_networks}개
          </span>
          {currentType !== recType && (
            <span className="text-[10px] text-amber-600 font-medium">(AI 추천: {recType === 'traffic' ? '트래픽' : '저장하기'})</span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Grid Cell Component ────────────────────────────────────────────────

interface GridCellProps {
  field: FormFieldExtended;
  value: string | number;
  onChange: (value: string | number) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  rowIdx: number;
  colIdx: number;
  disabled?: boolean;
}

function GridCell({ field, value, onChange, onKeyDown, rowIdx, colIdx, disabled }: GridCellProps) {
  const baseClass =
    `w-full px-2 py-1.5 text-sm border border-border-strong rounded bg-surface text-gray-200 focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400${
      disabled ? ' bg-surface-overlay text-gray-500 cursor-not-allowed' : ''
    }`;
  const readonlyClass =
    'w-full px-2 py-1.5 text-sm bg-surface-overlay border border-border rounded text-gray-400 cursor-default';
  const disabledReadonlyClass =
    'w-full px-2 py-1.5 text-sm bg-surface-overlay border border-border rounded text-gray-600 cursor-not-allowed';

  const dataAttrs = { 'data-row': rowIdx, 'data-col': colIdx } as Record<string, number>;

  switch (field.type) {
    case 'checkbox':
      return (
        <div className="flex items-center justify-center">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked ? 1 : 0)}
            className="h-5 w-5 rounded border-border-strong text-primary-600 focus:ring-primary-400/40 cursor-pointer"
            {...dataAttrs}
          />
        </div>
      );

    case 'text':
      return (
        <input type="text" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} className={baseClass} disabled={disabled} {...dataAttrs} />
      );

    case 'url':
      return (
        <input type="url" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} className={baseClass} placeholder="https://" disabled={disabled} {...dataAttrs} />
      );

    case 'number': {
      const minAttr = field.min !== undefined ? field.min : 0;
      const maxAttr = field.max !== undefined ? field.max : undefined;
      return (
        <input type="number" value={disabled ? '' : (value === '' ? '' : Number(value))} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} onKeyDown={onKeyDown} className={`${baseClass} text-right`} min={minAttr} max={maxAttr} disabled={disabled} {...dataAttrs} />
      );
    }

    case 'date':
      return (
        <input type="date" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} className={baseClass} min={new Date().toISOString().split('T')[0]} disabled={disabled} {...dataAttrs} />
      );

    case 'select':
      return (
        <select value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} className={baseClass} disabled={disabled} {...dataAttrs}>
          <option value="">선택...</option>
          {(field.options ?? []).map((opt) => (
            <option key={opt} value={opt}>{field.name === 'campaign_type' ? getCampaignTypeLabel(opt) : opt}</option>
          ))}
        </select>
      );

    case 'date_diff':
    case 'calc':
      return (
        <input type="text" value={disabled ? '' : (typeof value === 'number' ? formatNumber(value) : String(value ?? ''))} readOnly tabIndex={-1} className={disabled ? disabledReadonlyClass : readonlyClass} />
      );

    case 'date_calc':
      return (
        <input type="text" value={disabled ? '' : String(value ?? '')} readOnly tabIndex={-1} className={disabled ? disabledReadonlyClass : readonlyClass} />
      );

    case 'readonly':
      return (
        <div className="w-full px-2 py-1.5 text-sm bg-surface-overlay border border-border rounded text-gray-400 cursor-default" title={field.description}>
          {String(value || field.description || field.sample || '')}
        </div>
      );

    default:
      return (
        <input type="text" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} className={baseClass} disabled={disabled} {...dataAttrs} />
      );
  }
}
