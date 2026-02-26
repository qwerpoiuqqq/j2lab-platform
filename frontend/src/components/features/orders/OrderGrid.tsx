import { useState, useCallback, useRef } from 'react';
import type { Product, FormFieldExtended } from '@/types';
import { formatCurrency, formatNumber, downloadBlob } from '@/utils/format';
import { ordersApi } from '@/api/orders';
import Button from '@/components/common/Button';
import {
  PlusIcon,
  TrashIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  DocumentArrowDownIcon,
} from '@heroicons/react/24/outline';

export type OrderGridRow = Record<string, string | number>;

interface OrderGridProps {
  product: Product;
  schema: FormFieldExtended[];
  onSubmit: (items: OrderGridRow[], notes: string) => void;
  submitting?: boolean;
}

function evaluateFormula(formula: string, row: OrderGridRow): number {
  try {
    const parts = formula.split(/\s*([+\-*/])\s*/);
    if (parts.length < 3) return 0;
    let result = Number(row[parts[0]]) || 0;
    for (let i = 1; i < parts.length; i += 2) {
      const op = parts[i];
      const val = Number(row[parts[i + 1]]) || 0;
      switch (op) {
        case '+': result += val; break;
        case '-': result -= val; break;
        case '*': result *= val; break;
        case '/': result = val !== 0 ? result / val : 0; break;
      }
    }
    return Math.round(result);
  } catch {
    return 0;
  }
}

function evaluateDateCalc(baseField: string, daysField: string, row: OrderGridRow): string {
  try {
    const baseVal = row[baseField];
    if (!baseVal) return '';
    const baseDate = new Date(String(baseVal));
    if (isNaN(baseDate.getTime())) return '';
    const days = parseInt(String(row[daysField])) || 0;
    baseDate.setDate(baseDate.getDate() + days);
    return baseDate.toISOString().split('T')[0];
  } catch {
    return '';
  }
}

function createEmptyRow(schema: FormFieldExtended[]): OrderGridRow {
  const row: OrderGridRow = {};
  for (const field of schema) {
    if (field.default !== undefined) {
      row[field.name] = field.default;
    } else if (field.type === 'number' || field.type === 'calc') {
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
    if (field.type === 'calc' && field.formula) {
      computed[field.name] = evaluateFormula(field.formula, computed);
    } else if (field.type === 'date_calc' && field.base_field && field.days_field) {
      computed[field.name] = evaluateDateCalc(field.base_field, field.days_field, computed);
    }
  }
  return computed;
}

export default function OrderGrid({ product, schema, onSubmit, submitting }: OrderGridProps) {
  const [rows, setRows] = useState<OrderGridRow[]>([computeRow(createEmptyRow(schema), schema)]);
  const [notes, setNotes] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const updateRow = useCallback((rowIdx: number, fieldName: string, value: string | number) => {
    setRows((prev) => {
      const updated = [...prev];
      updated[rowIdx] = computeRow({ ...updated[rowIdx], [fieldName]: value }, schema);
      return updated;
    });
  }, [schema]);

  const addRow = useCallback(() => {
    setRows((prev) => [...prev, computeRow(createEmptyRow(schema), schema)]);
  }, [schema]);

  const deleteRow = useCallback((idx: number) => {
    setRows((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((_, i) => i !== idx);
    });
  }, []);

  // Calc totals: find subtotal-like calc fields, or sum quantity*unit_price
  const subtotal = rows.reduce((sum, row) => {
    const calcField = schema.find((f) => f.type === 'calc' && f.formula);
    if (calcField) {
      return sum + (Number(row[calcField.name]) || 0);
    }
    const qty = Number(row['quantity']) || 0;
    const price = Number(row['unit_price']) || product.base_price;
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
    // Build CSV from current grid
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
    // Validate required fields
    for (let i = 0; i < rows.length; i++) {
      for (const field of schema) {
        if (field.required && !rows[i][field.name] && rows[i][field.name] !== 0) {
          alert(`${i + 1}행: ${field.label} 항목은 필수입니다.`);
          return;
        }
      }
    }
    onSubmit(rows, notes);
  };

  const handleKeyDown = (e: React.KeyboardEvent, rowIdx: number, colIdx: number) => {
    if (e.key === 'Tab') {
      // Let default tab behavior work
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      // Move to next row, same column
      const nextRow = rowIdx + 1;
      if (nextRow < rows.length) {
        const nextInput = document.querySelector(
          `[data-row="${nextRow}"][data-col="${colIdx}"]`,
        ) as HTMLElement;
        nextInput?.focus();
      }
    }
  };

  return (
    <div className="space-y-4">
      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={addRow} icon={<PlusIcon className="h-4 w-4" />}>
          행 추가
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={handleTemplateDownload}
          icon={<ArrowDownTrayIcon className="h-4 w-4" />}
        >
          Excel 템플릿
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => fileInputRef.current?.click()}
          icon={<ArrowUpTrayIcon className="h-4 w-4" />}
        >
          Excel 업로드
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          onChange={handleExcelUpload}
          className="hidden"
        />
        <Button
          size="sm"
          variant="secondary"
          onClick={handleExcelExport}
          icon={<DocumentArrowDownIcon className="h-4 w-4" />}
        >
          Excel 내보내기
        </Button>
      </div>

      {/* Grid table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase w-12">
                #
              </th>
              {schema.map((field) => (
                <th
                  key={field.name}
                  className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase whitespace-nowrap"
                >
                  {field.label}
                  {field.required && <span className="text-red-500 ml-0.5">*</span>}
                </th>
              ))}
              <th className="px-3 py-3 w-12" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-gray-50">
                <td className="px-3 py-2 text-sm text-gray-500">{rowIdx + 1}</td>
                {schema.map((field, colIdx) => (
                  <td key={field.name} className="px-1 py-1">
                    <GridCell
                      field={field}
                      value={row[field.name]}
                      onChange={(val) => updateRow(rowIdx, field.name, val)}
                      onKeyDown={(e) => handleKeyDown(e, rowIdx, colIdx)}
                      rowIdx={rowIdx}
                      colIdx={colIdx}
                    />
                  </td>
                ))}
                <td className="px-2 py-1">
                  <button
                    onClick={() => deleteRow(rowIdx)}
                    className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                    title="행 삭제"
                    disabled={rows.length <= 1}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
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
      </div>

      {/* Submit */}
      <div className="flex justify-end">
        <Button
          size="lg"
          onClick={handleSubmit}
          loading={submitting}
          disabled={rows.length === 0}
        >
          주문 제출 ({formatNumber(rows.length)}건)
        </Button>
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
}

function GridCell({ field, value, onChange, onKeyDown, rowIdx, colIdx }: GridCellProps) {
  const baseClass =
    'w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500';
  const readonlyClass =
    'w-full px-2 py-1.5 text-sm bg-gray-100 border border-gray-200 rounded text-gray-600 cursor-default';

  const dataAttrs = { 'data-row': rowIdx, 'data-col': colIdx } as Record<string, number>;

  switch (field.type) {
    case 'text':
      return (
        <input
          type="text"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          className={baseClass}
          {...dataAttrs}
        />
      );

    case 'url':
      return (
        <input
          type="url"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          className={baseClass}
          placeholder="https://"
          {...dataAttrs}
        />
      );

    case 'number':
      return (
        <input
          type="number"
          value={value === '' ? '' : Number(value)}
          onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          onKeyDown={onKeyDown}
          className={`${baseClass} text-right`}
          min={0}
          {...dataAttrs}
        />
      );

    case 'date':
      return (
        <input
          type="date"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          className={baseClass}
          {...dataAttrs}
        />
      );

    case 'select':
      return (
        <select
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          className={baseClass}
          {...dataAttrs}
        >
          <option value="">선택...</option>
          {(field.options ?? []).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );

    case 'calc':
      return (
        <input
          type="text"
          value={typeof value === 'number' ? formatNumber(value) : String(value ?? '')}
          readOnly
          tabIndex={-1}
          className={readonlyClass}
        />
      );

    case 'date_calc':
      return (
        <input
          type="text"
          value={String(value ?? '')}
          readOnly
          tabIndex={-1}
          className={readonlyClass}
        />
      );

    case 'readonly':
      return (
        <input
          type="text"
          value={String(value ?? '')}
          readOnly
          tabIndex={-1}
          className={readonlyClass}
        />
      );

    default:
      return (
        <input
          type="text"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          className={baseClass}
          {...dataAttrs}
        />
      );
  }
}
