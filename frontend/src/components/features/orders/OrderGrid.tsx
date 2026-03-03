import React, { useState, useCallback, useRef, useEffect } from 'react';
import type { Product, FormFieldExtended, CalcFormula, DateCalcFormula, CombinedProductConfig } from '@/types';
import { formatCurrency, formatNumber, downloadBlob } from '@/utils/format';
import { getCalcFormula, getDateCalcFormula, getDateDiffFormula } from '@/utils/schema';
import { ordersApi } from '@/api/orders';
import { placesApi, type PlaceRecommendationV2 } from '@/api/places';
import { useAuthStore } from '@/store/auth';
import Button from '@/components/common/Button';
import {
  PlusIcon,
  TrashIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  DocumentArrowDownIcon,
  DocumentDuplicateIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';

export type OrderGridRow = Record<string, string | number>;

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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const user = useAuthStore((s) => s.user);

  // AI recommendation state per row
  const [aiStates, setAiStates] = useState<RowAIState[]>([{ recommendation: null, loading: false, networkName: '' }]);
  const timerRefs = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  // Find url field in schema for AI trigger
  const urlFieldName = enableAI ? schema.find((f) => f.type === 'url')?.name || '' : '';
  const campaignTypeFieldName = enableAI ? schema.find((f) => f.name === 'campaign_type')?.name || '' : '';

  useEffect(() => {
    return () => {
      timerRefs.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  // Keep aiStates in sync with rows count
  useEffect(() => {
    setAiStates((prev) => {
      if (prev.length === rows.length) return prev;
      if (prev.length < rows.length) {
        return [...prev, ...Array(rows.length - prev.length).fill(null).map(() => ({ recommendation: null, loading: false, networkName: '' }))];
      }
      return prev.slice(0, rows.length);
    });
  }, [rows.length]);

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

  const handleTemplateDownload = async () => {
    try {
      const blob = await ordersApi.downloadExcelTemplate(product.id);
      downloadBlob(blob, `${product.name}_template.xlsx`);
    } catch {
      alert('템플릿 다운로드에 실패했습니다.');
    }
  };

  const handleExcelUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await ordersApi.uploadExcel(file);
      if (result.errors?.length) {
        alert(`일부 오류:\n${result.errors.join('\n')}`);
      }
      if (result.rows?.length) {
        setRows(result.rows.map((r) => computeRow(r, schema)));
      }
    } catch {
      alert('Excel 업로드에 실패했습니다.');
    }
    e.target.value = '';
  };

  const handleExcelExport = () => {
    const headers = schema.map((f) => f.label);
    const csvRows = rows.map((row) =>
      schema.map((f) => {
        const val = row[f.name];
        return typeof val === 'string' && val.includes(',') ? `"${val}"` : String(val ?? '');
      }),
    );
    const bom = '\uFEFF';
    const csv = bom + [headers.join(','), ...csvRows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    downloadBlob(blob, `${product.name}_주문내역.csv`);
  };

  const handleSubmit = () => {
    for (let i = 0; i < rows.length; i++) {
      if (mode === 'combined') {
        if (!rows[i].traffic_enabled && !rows[i].save_enabled) {
          alert(`${i + 1}행: 트래픽 또는 저장 중 최소 1개를 선택해야 합니다.`);
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
      for (const field of schema) {
        if (field.group && !rows[i][field.group]) continue;
        if (field.required && !rows[i][field.name] && rows[i][field.name] !== 0) {
          alert(`${i + 1}행: ${field.label} 항목은 필수입니다.`);
          return;
        }
      }
    }
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
        {mode === 'single' && (
          <>
            <Button size="sm" variant="secondary" onClick={handleTemplateDownload} icon={<ArrowDownTrayIcon className="h-4 w-4" />}>
              Excel 템플릿
            </Button>
            <Button size="sm" variant="secondary" onClick={() => fileInputRef.current?.click()} icon={<ArrowUpTrayIcon className="h-4 w-4" />}>
              Excel 업로드
            </Button>
            <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv" onChange={handleExcelUpload} className="hidden" />
          </>
        )}
        <Button size="sm" variant="secondary" onClick={handleExcelExport} icon={<DocumentArrowDownIcon className="h-4 w-4" />}>
          Excel 내보내기
        </Button>
      </div>

      {/* Grid table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-12">#</th>
              {schema.map((field) => (
                <th
                  key={field.name}
                  className="px-3 py-3 text-left text-xs font-medium uppercase whitespace-nowrap"
                  style={field.color ? { backgroundColor: field.color, color: '#fff' } : undefined}
                >
                  {field.label}
                  {field.required && !field.group && <span className="text-red-500 ml-0.5">*</span>}
                </th>
              ))}
              {/* AI: 네트워크 선택 컬럼 */}
              {enableAI && (
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap">
                  네트워크
                </th>
              )}
              <th className="px-3 py-3 w-12" />
            </tr>
          </thead>
          <tbody className="bg-white">
            {rows.map((row, rowIdx) => {
              const ai = aiStates[rowIdx] || { recommendation: null, loading: false, networkName: '' };
              const networkList = enableAI ? getNetworkList(rowIdx) : [];
              const hasAI = enableAI && (ai.loading || ai.recommendation);

              return (
                <React.Fragment key={rowIdx}>
                  {/* 데이터 행 */}
                  <tr className="border-t border-gray-200 hover:bg-gray-50 align-top">
                    <td className="px-3 py-2 text-sm text-gray-500">{rowIdx + 1}</td>
                    {schema.map((field, colIdx) => (
                      <td key={field.name} className="px-1 py-1">
                        <GridCell
                          field={field}
                          value={row[field.name]}
                          onChange={(val) => {
                            updateRow(rowIdx, field.name, val);
                            // AI: trigger recommendation on URL change
                            if (enableAI && field.name === urlFieldName) {
                              fetchRecommendation(rowIdx, String(val));
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
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                          >
                            {networkList.map((n) => (
                              <option key={n.id} value={n.name}>{n.name}</option>
                            ))}
                          </select>
                        ) : ai.recommendation ? (
                          <span className="text-xs text-gray-400 px-2">네트워크 없음</span>
                        ) : (
                          <span className="text-xs text-gray-300 px-2">URL 입력 후</span>
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
          <label className="block text-sm font-medium text-gray-700 mb-1">비고</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            placeholder="주문 관련 메모를 입력하세요..."
          />
        </div>

        {mode === 'combined' && combinedConfig ? (
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">총 건수</span>
              <span className="font-medium text-gray-900">{formatNumber(rows.length)}건</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">트래픽 ({formatNumber(trafficTotalQty)}타 x {formatCurrency(combinedConfig.trafficPrice)})</span>
              <span className="font-medium text-gray-900">{formatCurrency(trafficSubtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">저장 ({formatNumber(saveTotalQty)}타 x {formatCurrency(combinedConfig.savePrice)})</span>
              <span className="font-medium text-gray-900">{formatCurrency(saveSubtotal)}</span>
            </div>
            <div className="border-t border-gray-200 pt-2" />
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">공급가액</span>
              <span className="font-medium text-gray-900">{formatCurrency(subtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">부가세 (10%)</span>
              <span className="font-medium text-gray-900">{formatCurrency(vat)}</span>
            </div>
            <div className="border-t border-gray-200 pt-2 flex justify-between">
              <span className="text-base font-semibold text-gray-900">합계</span>
              <span className="text-base font-bold text-primary-600">{formatCurrency(total)}</span>
            </div>
          </div>
        ) : (
          <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">총 건수</span>
              <span className="font-medium text-gray-900">{formatNumber(rows.length)}건</span>
            </div>
            {quantityField && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">총 수량 ({quantityField.label})</span>
                <span className="font-medium text-gray-900">
                  {formatNumber(rows.reduce((s, r) => s + (Number(r[quantityField.name]) || 0), 0))}
                </span>
              </div>
            )}
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">공급가액</span>
              <span className="font-medium text-gray-900">{formatCurrency(subtotal)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">부가세 (10%)</span>
              <span className="font-medium text-gray-900">{formatCurrency(vat)}</span>
            </div>
            <div className="border-t border-gray-200 pt-2 flex justify-between">
              <span className="text-base font-semibold text-gray-900">합계</span>
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
      <div className="flex items-center gap-2 px-3 py-2 bg-blue-50/60 rounded-lg border border-blue-100 animate-pulse">
        <SparklesIcon className="h-4 w-4 text-blue-400 shrink-0" />
        <span className="text-xs text-blue-500">AI가 이 플레이스를 분석하고 있습니다...</span>
      </div>
    );
  }

  if (!recommendation) return null;

  const rec = recommendation;
  const recType = rec.recommended_campaign_type;
  const recTypeRec = recType === 'traffic' ? rec.traffic : rec.save;
  const placeStatus = rec.is_existing ? '기존 플레이스' : '신규 플레이스';
  const actionText = recTypeRec.recommended_action === 'extend' ? '연장' : '신규 세팅';

  return (
    <div className="flex items-start gap-2 px-3 py-2.5 bg-gradient-to-r from-blue-50/80 to-purple-50/40 rounded-lg border border-blue-100/80">
      <SparklesIcon className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-xs text-gray-700 leading-relaxed">
          <span className="font-medium text-blue-700">{placeStatus}</span>입니다.{' '}
          <span className={`font-semibold ${recType === 'traffic' ? 'text-blue-600' : 'text-purple-600'}`}>
            {recType === 'traffic' ? '트래픽' : '저장'}
          </span>
          {recTypeRec.recommended_network && (
            <> <span className="font-medium text-gray-800">{recTypeRec.recommended_network}</span></>
          )}
          으로 <span className="font-medium">{actionText}</span> 진행해보시는 건 어떨까요?
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-1.5">
          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${rec.is_existing ? 'bg-orange-100 text-orange-700' : 'bg-green-100 text-green-700'}`}>
            {rec.is_existing ? '기존' : '신규'}
          </span>
          {recTypeRec.recommended_action === 'extend' && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-yellow-100 text-yellow-700">연장 가능</span>
          )}
          <span className="text-[10px] text-gray-400">
            남은 네트워크: 트래픽 {rec.traffic.available_networks}개 / 저장 {rec.save.available_networks}개
          </span>
          {currentType !== recType && (
            <span className="text-[10px] text-amber-600 font-medium">(AI 추천: {recType === 'traffic' ? '트래픽' : '저장'})</span>
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
    `w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500${
      disabled ? ' bg-gray-100 text-gray-400 cursor-not-allowed' : ''
    }`;
  const readonlyClass =
    'w-full px-2 py-1.5 text-sm bg-gray-100 border border-gray-200 rounded text-gray-600 cursor-default';
  const disabledReadonlyClass =
    'w-full px-2 py-1.5 text-sm bg-gray-100 border border-gray-200 rounded text-gray-300 cursor-not-allowed';

  const dataAttrs = { 'data-row': rowIdx, 'data-col': colIdx } as Record<string, number>;

  switch (field.type) {
    case 'checkbox':
      return (
        <div className="flex items-center justify-center">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked ? 1 : 0)}
            className="h-5 w-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 cursor-pointer"
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

    case 'number':
      return (
        <input type="number" value={disabled ? '' : (value === '' ? '' : Number(value))} onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))} onKeyDown={onKeyDown} className={`${baseClass} text-right`} min={0} disabled={disabled} {...dataAttrs} />
      );

    case 'date':
      return (
        <input type="date" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} className={baseClass} disabled={disabled} {...dataAttrs} />
      );

    case 'select':
      return (
        <select value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} className={baseClass} disabled={disabled} {...dataAttrs}>
          <option value="">선택...</option>
          {(field.options ?? []).map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
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
        <div className="w-full px-2 py-1.5 text-sm bg-gray-100 border border-gray-200 rounded text-gray-600 cursor-default" title={field.description}>
          {String(value || field.description || field.sample || '')}
        </div>
      );

    default:
      return (
        <input type="text" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} onKeyDown={onKeyDown} className={baseClass} disabled={disabled} {...dataAttrs} />
      );
  }
}
