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
import { normalizeSchema } from '@/utils/schema';
import type { Product, FormField } from '@/types';
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
  formula?: string;
  base_field?: string;
  days_field?: string;
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
  calc: '계산',
  date_calc: '날짜계산',
  readonly: '읽기전용',
};

const colorPresets = ['#4472C4', '#00B050', '#FFC000', '#FF6B35', '#C00000', '#7030A0', '#333D4B'];

const DEFAULT_COLOR = '#333D4B';

const calcOperators = ['+', '-', '*', '/'] as const;
const calcOperatorLabels: Record<string, string> = { '+': '+', '-': '-', '*': '\u00d7', '/': '\u00f7' };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Parse a simple "fieldA * fieldB" formula into parts */
function parseFormula(formula: string | undefined): { left: string; op: string; right: string } {
  if (!formula) return { left: '', op: '*', right: '' };
  for (const op of calcOperators) {
    const idx = formula.indexOf(` ${op} `);
    if (idx !== -1) {
      return {
        left: formula.substring(0, idx).trim(),
        op,
        right: formula.substring(idx + 3).trim(),
      };
    }
  }
  return { left: formula, op: '*', right: '' };
}

function buildFormula(left: string, op: string, right: string): string {
  if (!left && !right) return '';
  return `${left} ${op} ${right}`;
}

/** Generate sample cell text for a given field type */
function sampleText(field: SchemaField): string {
  if (field.sample) return field.sample;
  switch (field.type) {
    case 'text': return '텍스트 입력';
    case 'url': return 'https://...';
    case 'number': return '100';
    case 'date': return '2026-01-01';
    case 'select': return field.options?.[0] || '옵션 선택';
    case 'calc': return '= 자동계산';
    case 'date_calc': return '= 자동계산';
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
    setSchemaFields(normalizeSchema(product.form_schema) as SchemaField[]);
    setSelectedFieldIndex(null);
    setShowModal(true);
  };

  const applyPreset = (presetId: string) => {
    setSelectedPreset(presetId);
    if (!presetId) return; // "직접 구성" selected
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
      color: f.color || '#333D4B',
      sample: f.sample || '',
      options: f.options,
      formula: f.formula,
      base_field: f.base_field,
      days_field: f.days_field,
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
      name: `field_${schemaFields.length + 1}`,
      label: `필드 ${schemaFields.length + 1}`,
      type: 'text',
      required: false,
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
      // Show pipeline warnings if any
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
          <p className="text-xs text-gray-500">{p.description}</p>
        </div>
      ),
    },
    {
      key: 'code',
      header: '코드',
      render: (p) => <span className="font-mono text-sm text-gray-600">{p.code}</span>,
    },
    {
      key: 'category',
      header: '카테고리',
      render: (p) => <Badge variant="info">{p.category || '-'}</Badge>,
    },
    {
      key: 'base_price',
      header: '기본가격',
      render: (p) => <span className="font-medium text-gray-900">{formatCurrency(p.base_price)}</span>,
    },
    {
      key: 'cost_price',
      header: '원가',
      render: (p) => <span className="text-gray-600">{p.cost_price ? formatCurrency(p.cost_price) : '-'}</span>,
    },
    {
      key: 'reduction_rate',
      header: '할인율',
      render: (p) => <span className="text-gray-600">{p.reduction_rate ? `${p.reduction_rate}%` : '-'}</span>,
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

  /** Other field names for formula dropdowns, excluding the current field */
  const otherFieldNames = schemaFields
    .filter((_, i) => i !== selectedFieldIndex)
    .map((f) => f.name);

  const numberOrCalcFields = schemaFields.filter(
    (f) => f.type === 'number' || f.type === 'calc',
  );

  const quantityFieldIndex = schemaFields.findIndex((f) => f.is_quantity);

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

      {/* Product Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editing ? '상품 수정' : '상품 추가'}
        size="xl"
      >
        <div className="space-y-4 p-1 max-h-[70vh] overflow-y-auto">
          <div className="grid grid-cols-2 gap-4">
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
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">카테고리</label>
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
            <Input
              label="기본가격"
              type="number"
              value={formData.base_price}
              onChange={(e) => setFormData({ ...formData, base_price: e.target.value })}
            />
          </div>
          <Input
            label="원가"
            type="number"
            value={formData.cost_price}
            onChange={(e) => setFormData({ ...formData, cost_price: e.target.value })}
            placeholder="관리자 원가"
          />
          <Input
            label="설명"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="할인율 (%)"
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

          {/* Preset selector (only for create mode) */}
          {!editing && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">상품 프리셋</label>
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

          {/* ============================================================ */}
          {/* Schema Builder (new spreadsheet-style) */}
          {/* ============================================================ */}
          <div className="border-t border-gray-200 pt-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">주문 폼 스키마</h3>

            {/* --- 1. Spreadsheet Preview Table --- */}
            <div className="border border-gray-200 rounded-lg overflow-x-auto mb-4">
              <table className="w-full text-sm">
                {/* Column headers */}
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
                          px-3 py-2 text-left min-w-[120px] cursor-pointer border-r border-gray-200 select-none
                          ${selectedFieldIndex === idx ? 'ring-2 ring-primary-500 ring-inset' : ''}
                        `}
                        style={{ backgroundColor: field.color || DEFAULT_COLOR }}
                      >
                        <div className="flex items-center gap-1">
                          <span className="text-white text-xs font-semibold truncate">
                            {field.label || field.name}
                          </span>
                          {field.required && (
                            <span className="flex-shrink-0 w-2 h-2 rounded-full bg-red-500" />
                          )}
                        </div>
                        <span
                          className="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium"
                          style={{
                            backgroundColor: 'rgba(255,255,255,0.25)',
                            color: '#fff',
                          }}
                        >
                          {fieldTypeLabels[field.type] || field.type}
                        </span>
                      </th>
                    ))}
                    {/* Add column button */}
                    <th className="px-2 py-2 bg-gray-50 w-10">
                      <button
                        type="button"
                        onClick={addSchemaField}
                        className="flex items-center justify-center w-7 h-7 rounded-md border-2 border-dashed border-gray-300 text-gray-400 hover:border-primary-400 hover:text-primary-500 transition-colors"
                      >
                        <PlusIcon className="h-4 w-4" />
                      </button>
                    </th>
                  </tr>
                </thead>
                {/* Sample rows */}
                <tbody>
                  {schemaFields.length === 0 ? (
                    <tr>
                      <td colSpan={2} className="px-4 py-6 text-center text-gray-400 text-sm">
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
                                px-3 py-1.5 text-xs border-r border-gray-200 cursor-pointer
                                ${selectedFieldIndex === idx ? 'ring-2 ring-primary-500 ring-inset' : ''}
                              `}
                              style={{
                                backgroundColor: isAutoCalc
                                  ? '#E8F0FE'
                                  : isReadonly
                                    ? '#F3F4F6'
                                    : undefined,
                              }}
                            >
                              <span className={isAutoCalc ? 'text-blue-600' : isReadonly ? 'text-gray-500' : 'text-gray-600'}>
                                {sampleText(field)}
                              </span>
                            </td>
                          );
                        })}
                        <td className="bg-gray-50" />
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* --- 2. Field Edit Panel --- */}
            {selectedField && selectedFieldIndex !== null && (
              <div className="border border-gray-200 rounded-lg p-4 mb-4 bg-white">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-gray-800">
                    필드 편집: {selectedField.label || selectedField.name}
                  </h4>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => moveField(selectedFieldIndex, -1)}
                      disabled={selectedFieldIndex === 0}
                      className="p-1.5 rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
                      title="왼쪽으로 이동"
                    >
                      <ChevronLeftIcon className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => moveField(selectedFieldIndex, 1)}
                      disabled={selectedFieldIndex === schemaFields.length - 1}
                      className="p-1.5 rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
                      title="오른쪽으로 이동"
                    >
                      <ChevronRightIcon className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => removeSchemaField(selectedFieldIndex)}
                      className="ml-2 p-1.5 rounded text-red-500 hover:bg-red-50"
                      title="필드 삭제"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {/* Name */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">필드명 (name)</label>
                    <input
                      value={selectedField.name}
                      onChange={(e) => updateSchemaField(selectedFieldIndex, 'name', e.target.value)}
                      className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  </div>
                  {/* Label */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">라벨 (label)</label>
                    <input
                      value={selectedField.label}
                      onChange={(e) => updateSchemaField(selectedFieldIndex, 'label', e.target.value)}
                      className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  </div>
                  {/* Type */}
                  <div>
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
                  {/* Sample */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">샘플 텍스트</label>
                    <input
                      value={selectedField.sample || ''}
                      onChange={(e) => updateSchemaField(selectedFieldIndex, 'sample', e.target.value)}
                      placeholder="미리보기에 표시될 텍스트"
                      className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  </div>
                </div>

                {/* Required checkbox - hidden for readonly/calc/date_calc */}
                {selectedField.type !== 'readonly' &&
                  selectedField.type !== 'calc' &&
                  selectedField.type !== 'date_calc' && (
                  <label className="flex items-center gap-2 mt-3 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={selectedField.required || false}
                      onChange={(e) => updateSchemaField(selectedFieldIndex, 'required', e.target.checked)}
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                    필수 여부
                  </label>
                )}

                {/* Header color presets */}
                <div className="mt-3">
                  <label className="block text-xs font-medium text-gray-600 mb-1.5">헤더 색상</label>
                  <div className="flex items-center gap-2">
                    {colorPresets.map((color) => (
                      <button
                        key={color}
                        type="button"
                        onClick={() => updateSchemaField(selectedFieldIndex, 'color', color)}
                        className={`
                          w-7 h-7 rounded-full border-2 transition-all
                          ${(selectedField.color || DEFAULT_COLOR) === color
                            ? 'border-gray-900 scale-110 ring-2 ring-offset-1 ring-gray-400'
                            : 'border-transparent hover:border-gray-300'}
                        `}
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                </div>

                {/* --- Type-specific options --- */}

                {/* select -> comma-separated options */}
                {selectedField.type === 'select' && (
                  <div className="mt-3">
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
                  <div className="mt-3">
                    <label className="block text-xs font-medium text-gray-600 mb-1">설명</label>
                    <textarea
                      value={selectedField.description || ''}
                      onChange={(e) => updateSchemaField(selectedFieldIndex, 'description', e.target.value)}
                      placeholder="읽기전용 필드 설명"
                      rows={2}
                      className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500 resize-none"
                    />
                  </div>
                )}

                {/* calc -> formula builder */}
                {selectedField.type === 'calc' && (() => {
                  const parsed = parseFormula(selectedField.formula);
                  return (
                    <div className="mt-3">
                      <label className="block text-xs font-medium text-gray-600 mb-1">계산 수식</label>
                      <div className="flex items-center gap-2">
                        <select
                          value={parsed.left}
                          onChange={(e) =>
                            updateSchemaField(
                              selectedFieldIndex,
                              'formula',
                              buildFormula(e.target.value, parsed.op, parsed.right),
                            )
                          }
                          className="flex-1 px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                        >
                          <option value="">필드 선택</option>
                          {otherFieldNames.map((n) => (
                            <option key={n} value={n}>{n}</option>
                          ))}
                        </select>
                        <select
                          value={parsed.op}
                          onChange={(e) =>
                            updateSchemaField(
                              selectedFieldIndex,
                              'formula',
                              buildFormula(parsed.left, e.target.value, parsed.right),
                            )
                          }
                          className="w-16 px-2 py-1.5 text-sm text-center border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                        >
                          {calcOperators.map((op) => (
                            <option key={op} value={op}>{calcOperatorLabels[op]}</option>
                          ))}
                        </select>
                        <select
                          value={parsed.right}
                          onChange={(e) =>
                            updateSchemaField(
                              selectedFieldIndex,
                              'formula',
                              buildFormula(parsed.left, parsed.op, e.target.value),
                            )
                          }
                          className="flex-1 px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                        >
                          <option value="">필드 선택</option>
                          {otherFieldNames.map((n) => (
                            <option key={n} value={n}>{n}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  );
                })()}

                {/* date_calc -> base_field + days_field */}
                {selectedField.type === 'date_calc' && (
                  <div className="mt-3">
                    <label className="block text-xs font-medium text-gray-600 mb-1">날짜 계산</label>
                    <div className="flex items-center gap-2 text-sm">
                      <select
                        value={selectedField.base_field || ''}
                        onChange={(e) => updateSchemaField(selectedFieldIndex, 'base_field', e.target.value)}
                        className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                      >
                        <option value="">시작일 필드</option>
                        {otherFieldNames.map((n) => (
                          <option key={n} value={n}>{n}</option>
                        ))}
                      </select>
                      <span className="text-gray-500 font-medium">+</span>
                      <select
                        value={selectedField.days_field || ''}
                        onChange={(e) => updateSchemaField(selectedFieldIndex, 'days_field', e.target.value)}
                        className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500"
                      >
                        <option value="">일수 필드</option>
                        {otherFieldNames.map((n) => (
                          <option key={n} value={n}>{n}</option>
                        ))}
                      </select>
                      <span className="text-gray-500 text-xs whitespace-nowrap">- 1</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* --- 3. Quantity / Price Field Selector --- */}
            {numberOrCalcFields.length > 0 && (
              <div className="border border-gray-200 rounded-lg p-4 bg-white">
                <h4 className="text-sm font-semibold text-gray-800 mb-2">가격 설정</h4>
                <div className="space-y-1.5">
                  {numberOrCalcFields.map((field) => {
                    const realIdx = schemaFields.indexOf(field);
                    return (
                      <label key={realIdx} className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="radio"
                          name="quantity_field"
                          checked={field.is_quantity === true}
                          onChange={() => setQuantityField(realIdx)}
                          className="text-primary-600 focus:ring-primary-500"
                        />
                        {field.label || field.name}
                      </label>
                    );
                  })}
                </div>
                {quantityFieldIndex !== -1 && (
                  <p className="mt-2 text-xs text-gray-500 bg-gray-50 rounded px-2 py-1.5">
                    수량({schemaFields[quantityFieldIndex].label || schemaFields[quantityFieldIndex].name})
                    {' '}&times; 단가 = 공급가 + VAT
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-gray-200">
            <Button variant="secondary" onClick={() => setShowModal(false)}>취소</Button>
            <Button onClick={handleSubmit} loading={submitting}>
              {editing ? '수정' : '추가'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
