import { useState, useEffect } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import { formatCurrency, formatDateTime } from '@/utils/format';
import { normalizeSchema, labelToName } from '@/utils/schema';
import type { Product, FormField, CalcFormula, DateCalcFormula } from '@/types';
import { productsApi } from '@/api/products';
import { categoriesApi } from '@/api/categories';
import { useAuthStore } from '@/store/auth';
import { PRODUCT_PRESETS } from '@/constants/productPresets';

// ---------------------------------------------------------------------------
// Extended schema field type used internally
// ---------------------------------------------------------------------------
interface SchemaField extends FormField {
  color?: string;
  sample?: string;
  options?: string[];
  formula?: CalcFormula | DateCalcFormula;
  is_quantity?: boolean;
  description?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const fieldTypes = ['text', 'url', 'number', 'date', 'select', 'calc', 'date_calc', 'readonly'] as const;

const fieldTypeLabels: Record<string, string> = {
  text: '텍스트',
  url: 'URL',
  number: '숫자',
  date: '날짜',
  select: '선택',
  calc: '자동계산',
  date_calc: '날짜계산',
  readonly: '설명',
};

const colorPresets = ['#4472C4', '#00B050', '#FFC000', '#FF6B35', '#C00000', '#7030A0', '#333D4B'];

const DEFAULT_COLOR = '#4472C4';

const calcOperators = ['+', '-', '*', '/'] as const;
const calcOperatorLabels: Record<string, string> = { '+': '+', '-': '−', '*': '\u00d7', '/': '\u00f7' };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Get CalcFormula parts for display */
function getCalcParts(field: SchemaField): CalcFormula {
  const f = field.formula;
  if (f && typeof f === 'object' && 'fieldA' in f) return f as CalcFormula;
  return { fieldA: '', operator: '*', fieldB: '' };
}

/** Get DateCalcFormula parts for display */
function getDateCalcParts(field: SchemaField): DateCalcFormula {
  const f = field.formula;
  if (f && typeof f === 'object' && 'dateField' in f) return f as DateCalcFormula;
  return { dateField: '', daysField: '' };
}

/** Generate sample cell text for a given field type */
function sampleText(field: SchemaField, allFields: SchemaField[]): string {
  if (field.sample) return field.sample;
  switch (field.type) {
    case 'text': return '텍스트 입력';
    case 'url': return 'https://...';
    case 'number': return '100';
    case 'date': return '2026-01-01';
    case 'select': return field.options?.[0] || '옵션 선택';
    case 'calc': {
      const p = getCalcParts(field);
      const aLabel = allFields.find(f => f.name === p.fieldA)?.label || '?';
      const bLabel = allFields.find(f => f.name === p.fieldB)?.label || '?';
      const opLabel = calcOperatorLabels[p.operator] || '\u00d7';
      return `= ${aLabel} ${opLabel} ${bLabel}`;
    }
    case 'date_calc': {
      const p = getDateCalcParts(field);
      const dateLabel = allFields.find(f => f.name === p.dateField)?.label || '?';
      const daysLabel = allFields.find(f => f.name === p.daysField)?.label || '?';
      return `= ${dateLabel} + ${daysLabel} − 1`;
    }
    case 'readonly': return field.description || '자동입력';
    default: return '';
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ProductsPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === 'system_admin';

  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Product form modal
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    category: '',
    description: '',
    base_price: '',
    cost_price: '',
    reduction_rate: '',
    min_work_days: '',
    max_work_days: '',
  });
  const [schemaFields, setSchemaFields] = useState<SchemaField[]>([]);
  const [selectedFieldIndex, setSelectedFieldIndex] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [categories, setCategories] = useState<string[]>([]);

  // -----------------------------------------------------------------------
  // Data fetching
  // -----------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    productsApi
      .list({ size: 100 })
      .then((data) => {
        if (!cancelled) {
          setProducts(data.items);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '상품 목록을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [refreshKey]);

  useEffect(() => {
    categoriesApi.list({ size: 100 }).then((data) => {
      setCategories(data.items.map((c: any) => c.name));
    }).catch(() => {});
  }, []);

  // -----------------------------------------------------------------------
  // Modal open/close
  // -----------------------------------------------------------------------
  const openCreate = () => {
    setEditing(null);
    setFormData({ name: '', code: '', category: '', description: '', base_price: '', cost_price: '', reduction_rate: '', min_work_days: '', max_work_days: '' });
    setSchemaFields([]);
    setSelectedFieldIndex(null);
    setSelectedPreset('');
    setShowModal(true);
  };

  const openEdit = (product: Product) => {
    setEditing(product);
    setFormData({
      name: product.name,
      code: product.code,
      category: product.category || '',
      description: product.description || '',
      base_price: String(product.base_price || ''),
      cost_price: String(product.cost_price || ''),
      reduction_rate: String(product.reduction_rate || ''),
      min_work_days: String(product.min_work_days || ''),
      max_work_days: String(product.max_work_days || ''),
    });
    // normalizeSchema handles legacy formula migration
    setSchemaFields(normalizeSchema(product.form_schema) as SchemaField[]);
    setSelectedFieldIndex(null);
    setShowModal(true);
  };

  const applyPreset = (presetId: string) => {
    setSelectedPreset(presetId);
    if (!presetId) return;
    const preset = PRODUCT_PRESETS.find(p => p.id === presetId);
    if (!preset) return;
    setFormData(prev => ({
      ...prev,
      name: preset.name,
      category: preset.category,
      description: preset.description,
    }));
    setSchemaFields(preset.fields.map(f => ({
      name: f.name,
      label: f.label,
      type: f.type,
      required: f.required || false,
      color: f.color || DEFAULT_COLOR,
      sample: f.sample || '',
      options: f.options,
      formula: f.formula,
      is_quantity: f.is_quantity,
      description: f.description,
      default: f.default,
    })));
    setSelectedFieldIndex(null);
  };

  // -----------------------------------------------------------------------
  // Schema field CRUD
  // -----------------------------------------------------------------------
  const addSchemaField = () => {
    const newField: SchemaField = {
      name: '',
      label: '',
      type: 'text',
      required: true,
      color: DEFAULT_COLOR,
      sample: '',
    };
    const newFields = [...schemaFields, newField];
    setSchemaFields(newFields);
    setSelectedFieldIndex(newFields.length - 1);
  };

  const updateSchemaField = (index: number, key: string, value: any) => {
    const updated = [...schemaFields];
    updated[index] = { ...updated[index], [key]: value };
    // Auto-generate name from label
    if (key === 'label') {
      updated[index].name = labelToName(value);
    }
    setSchemaFields(updated);
  };

  const removeSchemaField = (index: number) => {
    const updated = schemaFields.filter((_, i) => i !== index);
    setSchemaFields(updated);
    if (selectedFieldIndex === index) {
      setSelectedFieldIndex(null);
    } else if (selectedFieldIndex !== null && selectedFieldIndex > index) {
      setSelectedFieldIndex(selectedFieldIndex - 1);
    }
  };

  const moveField = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= schemaFields.length) return;
    const updated = [...schemaFields];
    [updated[index], updated[target]] = [updated[target], updated[index]];
    setSchemaFields(updated);
    setSelectedFieldIndex(target);
  };

  const setQuantityField = (index: number) => {
    const updated = schemaFields.map((f, i) => ({
      ...f,
      is_quantity: i === index,
    }));
    setSchemaFields(updated);
  };

  const clearQuantityField = () => {
    const updated = schemaFields.map(f => ({ ...f, is_quantity: undefined }));
    setSchemaFields(updated);
  };

  // Update calc formula
  const updateCalcFormula = (index: number, partial: Partial<CalcFormula>) => {
    const current = getCalcParts(schemaFields[index]);
    const updated = { ...current, ...partial } as CalcFormula;
    updateSchemaField(index, 'formula', updated);
  };

  // Update date_calc formula
  const updateDateCalcFormula = (index: number, partial: Partial<DateCalcFormula>) => {
    const current = getDateCalcParts(schemaFields[index]);
    const updated = { ...current, ...partial } as DateCalcFormula;
    updateSchemaField(index, 'formula', updated);
  };

  // -----------------------------------------------------------------------
  // Delete product
  // -----------------------------------------------------------------------
  const handleDelete = async (product: Product) => {
    if (!confirm(`'${product.name}' 상품을 비활성화하시겠습니까?`)) return;
    try {
      await productsApi.delete(product.id);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '비활성화에 실패했습니다.');
    }
  };

  // -----------------------------------------------------------------------
  // Submit
  // -----------------------------------------------------------------------
  const handleSubmit = async () => {
    if (!formData.name || !formData.code) {
      alert('상품명과 코드를 입력하세요.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        name: formData.name,
        code: formData.code,
        category: formData.category || undefined,
        description: formData.description || undefined,
        base_price: parseInt(formData.base_price) || 0,
        cost_price: parseInt(formData.cost_price) || undefined,
        reduction_rate: parseInt(formData.reduction_rate) || undefined,
        min_work_days: parseInt(formData.min_work_days) || undefined,
        max_work_days: parseInt(formData.max_work_days) || undefined,
        form_schema: schemaFields.length > 0 ? schemaFields : undefined,
      };

      let response: any;
      if (editing) {
        response = await productsApi.update(editing.id, payload);
      } else {
        response = await productsApi.create(payload);
      }
      if (response?.pipeline_warnings?.length > 0) {
        alert('파이프라인 경고:\n' + response.pipeline_warnings.join('\n'));
      }
      setShowModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  // -----------------------------------------------------------------------
  // Table columns
  // -----------------------------------------------------------------------
  const columns: Column<Product>[] = [
    {
      key: 'name',
      header: '상품명',
      render: (p) => (
        <div>
          <p className="font-medium text-gray-900">{p.name}</p>
          <p className="text-xs text-gray-500">{p.code}</p>
        </div>
      ),
    },
    {
      key: 'category',
      header: '카테고리',
      render: (p) => <Badge variant="info">{p.category || '-'}</Badge>,
    },
    {
      key: 'base_price',
      header: '기본단가',
      render: (p) => <span className="font-medium text-gray-900">{formatCurrency(p.base_price)}</span>,
    },
    {
      key: 'cost_price',
      header: '원가',
      render: (p) => <span className="text-gray-600">{p.cost_price ? formatCurrency(p.cost_price) : '-'}</span>,
    },
    {
      key: 'form_schema',
      header: '스키마',
      render: (p) => (
        <span className="text-xs text-gray-500">{normalizeSchema(p.form_schema).length}개 필드</span>
      ),
    },
    {
      key: 'is_active',
      header: '상태',
      render: (p) => (
        <Badge variant={p.is_active ? 'success' : 'default'}>
          {p.is_active ? '활성' : '비활성'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: '생성일',
      render: (p) => <span className="text-gray-500 text-xs">{formatDateTime(p.created_at)}</span>,
    },
    ...(isAdmin
      ? [
          {
            key: 'actions' as keyof Product,
            header: '작업',
            render: (p: Product) => (
              <div className="flex items-center gap-1">
                <button
                  onClick={(e) => { e.stopPropagation(); openEdit(p); }}
                  className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                >
                  <PencilSquareIcon className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(p); }}
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                  title="비활성화"
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]
      : []),
  ];

  // -----------------------------------------------------------------------
  // Derived values for the selected field
  // -----------------------------------------------------------------------
  const selectedField: SchemaField | null =
    selectedFieldIndex !== null && selectedFieldIndex < schemaFields.length
      ? schemaFields[selectedFieldIndex]
      : null;

  const numberFields = schemaFields.filter(
    (f, i) => i !== selectedFieldIndex && f.type === 'number',
  );

  const dateFields = schemaFields.filter(
    (f, i) => i !== selectedFieldIndex && f.type === 'date',
  );

  const numberOrCalcFields = schemaFields.filter(
    (f) => f.type === 'number' || f.type === 'calc',
  );

  const quantityFieldIndex = schemaFields.findIndex((f) => f.is_quantity);
  const unitPrice = parseInt(formData.base_price) || 0;

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">상품 관리</h1>
          <p className="mt-1 text-sm text-gray-500">상품 목록을 조회하고 관리합니다.</p>
        </div>
        {isAdmin && (
          <Button onClick={openCreate} icon={<PlusIcon className="h-4 w-4" />}>
            상품 추가
          </Button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      <Table<Product>
        columns={columns}
        data={products}
        keyExtractor={(p) => p.id}
        loading={loading}
        emptyMessage="상품이 없습니다."
      />

      {/* Product Modal - 2-column layout */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editing ? '상품 수정' : '상품 추가'}
        size="full"
      >
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 p-1" style={{ maxHeight: '78vh', overflow: 'auto' }}>
          {/* ==================== LEFT: Basic Info ==================== */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
              <h3 className="text-sm font-bold text-gray-800 border-b border-gray-100 pb-2">기본 정보</h3>

              {/* Preset selector (only for create mode) */}
              {!editing && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">프리셋</label>
                  <select
                    value={selectedPreset}
                    onChange={(e) => applyPreset(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="">직접 구성</option>
                    {PRODUCT_PRESETS.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {preset.name} - {preset.description}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <Input
                label="상품명"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
              <Input
                label="코드"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                required
                disabled={!!editing}
              />
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">카테고리</label>
                <select
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="">선택하세요</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">설명</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                  placeholder="상품 설명을 입력하세요..."
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="기본 단가"
                  type="number"
                  value={formData.base_price}
                  onChange={(e) => setFormData({ ...formData, base_price: e.target.value })}
                />
                <Input
                  label="원가"
                  type="number"
                  value={formData.cost_price}
                  onChange={(e) => setFormData({ ...formData, cost_price: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <Input
                  label="감은 비율(%)"
                  type="number"
                  value={formData.reduction_rate}
                  onChange={(e) => setFormData({ ...formData, reduction_rate: e.target.value })}
                  placeholder="0-100"
                />
                <Input
                  label="최소 작업일"
                  type="number"
                  value={formData.min_work_days}
                  onChange={(e) => setFormData({ ...formData, min_work_days: e.target.value })}
                />
                <Input
                  label="최대 작업일"
                  type="number"
                  value={formData.max_work_days}
                  onChange={(e) => setFormData({ ...formData, max_work_days: e.target.value })}
                />
              </div>
            </div>

            {/* Price Settings Card */}
            <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
              <h3 className="text-sm font-bold text-gray-800 border-b border-gray-100 pb-2">가격 설정</h3>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">수량 기준 필드</label>
                <select
                  value={quantityFieldIndex !== -1 ? String(quantityFieldIndex) : ''}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '') { clearQuantityField(); }
                    else { setQuantityField(Number(val)); }
                  }}
                  className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">선택 안 함 (슬롯 수 = 수량)</option>
                  {numberOrCalcFields.map((field) => {
                    const realIdx = schemaFields.indexOf(field);
                    return (
                      <option key={realIdx} value={String(realIdx)}>
                        {field.label || field.name} ({fieldTypeLabels[field.type]})
                      </option>
                    );
                  })}
                </select>
                <p className="text-[11px] text-gray-400 mt-1">이 필드의 값이 가격 계산의 수량이 됩니다</p>
              </div>

              {/* Pricing formula preview */}
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs font-semibold text-gray-500 mb-2">가격 공식</p>
                {quantityFieldIndex === -1 ? (
                  <div className="text-sm text-gray-500">
                    <p>슬롯 1건 &times; {unitPrice.toLocaleString()}원 = 공급가</p>
                    <p>공급가 + 부가세(10%) = 총 견적금액</p>
                  </div>
                ) : (
                  <div className="text-sm text-gray-700">
                    <p className="mb-1">
                      <strong className="text-primary-600">
                        {schemaFields[quantityFieldIndex].label || schemaFields[quantityFieldIndex].name}
                      </strong>
                      {' '}&times; {unitPrice.toLocaleString()}원 = <strong>공급가</strong>
                    </p>
                    <p>공급가 + <strong>부가세(10%)</strong> = <strong className="text-primary-600">총 견적금액</strong></p>
                    <div className="mt-2 pt-2 border-t border-gray-200 text-xs text-gray-400">
                      예) {schemaFields[quantityFieldIndex].label} 7,000 &times; {unitPrice.toLocaleString()}원
                      = {(7000 * unitPrice).toLocaleString()}원
                      + {(7000 * unitPrice * 0.1).toLocaleString()}원
                      = <strong>{(7000 * unitPrice * 1.1).toLocaleString()}원</strong>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Submit buttons */}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setShowModal(false)}>취소</Button>
              <Button onClick={handleSubmit} loading={submitting}>
                {editing ? '수정' : '추가'}
              </Button>
            </div>
          </div>

          {/* ==================== RIGHT: Schema Preview ==================== */}
          <div className="lg:col-span-3 space-y-4">
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-gray-800">접수 양식 미리보기</h3>
                <span className="text-xs text-gray-400">열 클릭으로 편집</span>
              </div>

              {/* Spreadsheet Preview Table */}
              <div className="border border-gray-200 rounded-lg overflow-x-auto mb-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className="px-2 py-1.5 text-left text-xs font-medium text-gray-500 bg-gray-50 border-r border-gray-200 w-10">
                        #
                      </th>
                      {schemaFields.map((field, idx) => (
                        <th
                          key={idx}
                          onClick={() => setSelectedFieldIndex(idx)}
                          className={`
                            px-3 py-2 text-center min-w-[120px] cursor-pointer border-r select-none transition-all
                            ${selectedFieldIndex === idx ? 'ring-2 ring-primary-500 ring-inset' : ''}
                          `}
                          style={{
                            backgroundColor: field.color || DEFAULT_COLOR,
                            borderColor: darkenColor(field.color || DEFAULT_COLOR, 0.15),
                          }}
                        >
                          <div className="flex items-center justify-center gap-1">
                            <span className="text-white text-xs font-semibold truncate">
                              {field.label || field.name || '(이름없음)'}
                            </span>
                            {field.required && (
                              <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-yellow-400" />
                            )}
                          </div>
                          <span
                            className="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium"
                            style={{ backgroundColor: 'rgba(255,255,255,0.25)', color: '#fff' }}
                          >
                            {fieldTypeLabels[field.type] || field.type}
                          </span>
                        </th>
                      ))}
                      <th
                        onClick={addSchemaField}
                        className="px-2 py-2 bg-gray-50 border border-dashed border-gray-300 cursor-pointer text-gray-400 hover:bg-blue-50 hover:text-primary-500 hover:border-primary-400 transition-colors min-w-[60px] text-xl font-light"
                      >
                        +
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {schemaFields.length === 0 ? (
                      <tr>
                        <td colSpan={2} className="px-4 py-8 text-center text-gray-400 text-sm">
                          스키마 필드가 없습니다. + 버튼으로 추가하세요.
                        </td>
                      </tr>
                    ) : (
                      [1, 2].map((rowNum) => (
                        <tr key={rowNum} className="border-t border-gray-100">
                          <td className="px-2 py-1.5 text-xs text-gray-400 bg-gray-50 border-r border-gray-200 text-center">
                            {rowNum}
                          </td>
                          {schemaFields.map((field, idx) => {
                            const isAutoCalc = field.type === 'calc' || field.type === 'date_calc';
                            const isReadonly = field.type === 'readonly';
                            return (
                              <td
                                key={idx}
                                onClick={() => setSelectedFieldIndex(idx)}
                                className={`
                                  px-3 py-1.5 text-xs border-r border-gray-200 cursor-pointer text-center
                                  ${selectedFieldIndex === idx ? 'ring-2 ring-primary-500 ring-inset' : ''}
                                `}
                                style={{
                                  backgroundColor: isAutoCalc
                                    ? '#eff6ff'
                                    : isReadonly
                                      ? '#f9fafb'
                                      : undefined,
                                }}
                              >
                                <span className={
                                  isAutoCalc ? 'text-blue-600 font-semibold' :
                                  isReadonly ? 'text-gray-500 italic text-[12px]' :
                                  'text-gray-600'
                                }>
                                  {sampleText(field, schemaFields)}
                                </span>
                              </td>
                            );
                          })}
                          <td
                            onClick={addSchemaField}
                            className="bg-gray-50 border border-dashed border-gray-300 cursor-pointer text-center text-xs text-gray-400 hover:bg-blue-50 hover:text-primary-500 transition-colors"
                          >
                            {rowNum === 1 ? '열 추가' : ''}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Field Edit Panel */}
              {selectedField && selectedFieldIndex !== null && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-bold text-gray-800">
                      &ldquo;{selectedField.label || selectedField.name || '새 필드'}&rdquo; 편집
                    </h4>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => moveField(selectedFieldIndex, -1)}
                        disabled={selectedFieldIndex === 0}
                        className="p-1.5 rounded border border-gray-200 bg-white text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
                        title="왼쪽으로"
                      >
                        <ChevronLeftIcon className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => moveField(selectedFieldIndex, 1)}
                        disabled={selectedFieldIndex === schemaFields.length - 1}
                        className="p-1.5 rounded border border-gray-200 bg-white text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
                        title="오른쪽으로"
                      >
                        <ChevronRightIcon className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeSchemaField(selectedFieldIndex)}
                        className="ml-2 p-1.5 rounded border border-red-200 bg-white text-red-500 hover:bg-red-50"
                        title="삭제"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-12 gap-3">
                    {/* Label (main input) */}
                    <div className="col-span-12">
                      <label className="block text-xs font-medium text-gray-600 mb-1">열 이름</label>
                      <input
                        value={selectedField.label}
                        onChange={(e) => updateSchemaField(selectedFieldIndex, 'label', e.target.value)}
                        placeholder="예: 플레이스 URL"
                        className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                      />
                      {selectedField.name && (
                        <p className="text-[11px] text-gray-400 mt-0.5">
                          필드명: <code className="bg-gray-100 px-1 rounded">{selectedField.name}</code>
                        </p>
                      )}
                    </div>

                    {/* Type */}
                    <div className="col-span-3">
                      <label className="block text-xs font-medium text-gray-600 mb-1">타입</label>
                      <select
                        value={selectedField.type}
                        onChange={(e) => updateSchemaField(selectedFieldIndex, 'type', e.target.value)}
                        className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                      >
                        {fieldTypes.map((t) => (
                          <option key={t} value={t}>{fieldTypeLabels[t]}</option>
                        ))}
                      </select>
                    </div>

                    {/* Required */}
                    {selectedField.type !== 'readonly' &&
                      selectedField.type !== 'calc' &&
                      selectedField.type !== 'date_calc' && (
                      <div className="col-span-3">
                        <label className="block text-xs font-medium text-gray-600 mb-1">필수 여부</label>
                        <select
                          value={selectedField.required ? 'true' : 'false'}
                          onChange={(e) => updateSchemaField(selectedFieldIndex, 'required', e.target.value === 'true')}
                          className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                        >
                          <option value="true">필수</option>
                          <option value="false">선택사항</option>
                        </select>
                      </div>
                    )}

                    {/* Header color */}
                    <div className="col-span-3">
                      <label className="block text-xs font-medium text-gray-600 mb-1">헤더 색상</label>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {colorPresets.map((color) => (
                          <button
                            key={color}
                            type="button"
                            onClick={() => updateSchemaField(selectedFieldIndex, 'color', color)}
                            className={`
                              w-5 h-5 rounded border-2 transition-all
                              ${(selectedField.color || DEFAULT_COLOR).toUpperCase() === color.toUpperCase()
                                ? 'border-gray-900 scale-125'
                                : 'border-transparent hover:scale-110'}
                            `}
                            style={{ backgroundColor: color }}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Sample text - hidden for auto fields */}
                    {selectedField.type !== 'readonly' &&
                      selectedField.type !== 'calc' &&
                      selectedField.type !== 'date_calc' && (
                      <div className="col-span-6">
                        <label className="block text-xs font-medium text-gray-600 mb-1">샘플 텍스트</label>
                        <input
                          value={selectedField.sample || ''}
                          onChange={(e) => updateSchemaField(selectedFieldIndex, 'sample', e.target.value)}
                          placeholder="미리보기에 표시될 예시 값"
                          className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                        />
                      </div>
                    )}

                    {/* select -> options */}
                    {selectedField.type === 'select' && (
                      <div className="col-span-12">
                        <label className="block text-xs font-medium text-gray-600 mb-1">선택 옵션 (쉼표 구분)</label>
                        <input
                          value={selectedField.options?.join(', ') || ''}
                          onChange={(e) =>
                            updateSchemaField(
                              selectedFieldIndex,
                              'options',
                              e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                            )
                          }
                          placeholder="옵션1, 옵션2, 옵션3"
                          className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                        />
                      </div>
                    )}

                    {/* readonly -> description */}
                    {selectedField.type === 'readonly' && (
                      <div className="col-span-12">
                        <label className="block text-xs font-medium text-gray-600 mb-1">설명 내용 (주문자에게 표시)</label>
                        <textarea
                          value={selectedField.description || ''}
                          onChange={(e) => updateSchemaField(selectedFieldIndex, 'description', e.target.value)}
                          placeholder="예: 5위 이내 키워드 최대 5개까지 작성 부탁드립니다"
                          rows={2}
                          className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500 resize-none"
                        />
                      </div>
                    )}

                    {/* calc -> formula builder (object format) */}
                    {selectedField.type === 'calc' && (() => {
                      const parts = getCalcParts(selectedField);
                      return (
                        <div className="col-span-12">
                          <label className="block text-xs font-medium text-gray-600 mb-1">수식 설정</label>
                          <div className="flex items-center gap-2">
                            <select
                              value={parts.fieldA}
                              onChange={(e) => updateCalcFormula(selectedFieldIndex, { fieldA: e.target.value })}
                              className="flex-1 px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                            >
                              <option value="">필드 선택</option>
                              {numberFields.map((f) => (
                                <option key={f.name} value={f.name}>{f.label || f.name}</option>
                              ))}
                            </select>
                            <select
                              value={parts.operator}
                              onChange={(e) => updateCalcFormula(selectedFieldIndex, { operator: e.target.value as CalcFormula['operator'] })}
                              className="w-16 px-2 py-1.5 text-sm text-center border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                            >
                              {calcOperators.map((op) => (
                                <option key={op} value={op}>{calcOperatorLabels[op]}</option>
                              ))}
                            </select>
                            <select
                              value={parts.fieldB}
                              onChange={(e) => updateCalcFormula(selectedFieldIndex, { fieldB: e.target.value })}
                              className="flex-1 px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                            >
                              <option value="">필드 선택</option>
                              {numberFields.map((f) => (
                                <option key={f.name} value={f.name}>{f.label || f.name}</option>
                              ))}
                            </select>
                          </div>
                          <p className="text-[11px] text-gray-400 mt-1">
                            숫자 타입 필드끼리 연산합니다. 주문자가 값을 입력하면 자동 계산됩니다.
                          </p>
                        </div>
                      );
                    })()}

                    {/* date_calc -> formula builder (object format) */}
                    {selectedField.type === 'date_calc' && (() => {
                      const parts = getDateCalcParts(selectedField);
                      return (
                        <div className="col-span-12">
                          <label className="block text-xs font-medium text-gray-600 mb-1">날짜 계산 설정</label>
                          <div className="flex items-center gap-2 text-sm">
                            <select
                              value={parts.dateField}
                              onChange={(e) => updateDateCalcFormula(selectedFieldIndex, { dateField: e.target.value })}
                              className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                            >
                              <option value="">시작일 필드</option>
                              {dateFields.map((f) => (
                                <option key={f.name} value={f.name}>{f.label || f.name}</option>
                              ))}
                            </select>
                            <span className="text-gray-500 font-medium whitespace-nowrap">+</span>
                            <select
                              value={parts.daysField}
                              onChange={(e) => updateDateCalcFormula(selectedFieldIndex, { daysField: e.target.value })}
                              className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                            >
                              <option value="">작업일 수 필드</option>
                              {numberFields.map((f) => (
                                <option key={f.name} value={f.name}>{f.label || f.name}</option>
                              ))}
                            </select>
                            <span className="text-gray-500 text-xs whitespace-nowrap">− 1일</span>
                          </div>
                          <p className="text-[11px] text-gray-400 mt-1">
                            시작일 + 작업일 수 − 1 = 마감일 (시작일 포함)
                          </p>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------
function darkenColor(hex: string, amount: number): string {
  hex = hex.replace('#', '');
  let r = parseInt(hex.substring(0, 2), 16);
  let g = parseInt(hex.substring(2, 4), 16);
  let b = parseInt(hex.substring(4, 6), 16);
  r = Math.max(0, Math.round(r * (1 - amount)));
  g = Math.max(0, Math.round(g * (1 - amount)));
  b = Math.max(0, Math.round(b * (1 - amount)));
  return '#' + [r, g, b].map(c => c.toString(16).padStart(2, '0')).join('');
}
