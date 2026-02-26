import { useState, useEffect } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import { PlusIcon, PencilSquareIcon } from '@heroicons/react/24/outline';
import { formatCurrency, formatDateTime } from '@/utils/format';
import type { Product, FormField } from '@/types';
import { productsApi } from '@/api/products';
import { useAuthStore } from '@/store/auth';

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
    min_work_days: '',
    max_work_days: '',
  });
  const [schemaFields, setSchemaFields] = useState<FormField[]>([]);
  const [submitting, setSubmitting] = useState(false);

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

  const openCreate = () => {
    setEditing(null);
    setFormData({ name: '', code: '', category: '', description: '', base_price: '', min_work_days: '', max_work_days: '' });
    setSchemaFields([]);
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
      min_work_days: String(product.min_work_days || ''),
      max_work_days: String(product.max_work_days || ''),
    });
    setSchemaFields(product.form_schema || []);
    setShowModal(true);
  };

  const addSchemaField = () => {
    setSchemaFields([...schemaFields, { name: '', type: 'text', label: '', required: false }]);
  };

  const updateSchemaField = (index: number, key: keyof FormField, value: any) => {
    const updated = [...schemaFields];
    updated[index] = { ...updated[index], [key]: value };
    setSchemaFields(updated);
  };

  const removeSchemaField = (index: number) => {
    setSchemaFields(schemaFields.filter((_, i) => i !== index));
  };

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
        min_work_days: parseInt(formData.min_work_days) || undefined,
        max_work_days: parseInt(formData.max_work_days) || undefined,
        form_schema: schemaFields.length > 0 ? schemaFields : undefined,
      };

      if (editing) {
        await productsApi.update(editing.id, payload);
      } else {
        await productsApi.create(payload);
      }
      setShowModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

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
      key: 'form_schema',
      header: '스키마',
      render: (p) => (
        <span className="text-xs text-gray-500">{p.form_schema?.length || 0}개 필드</span>
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
              <button
                onClick={(e) => { e.stopPropagation(); openEdit(p); }}
                className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
              >
                <PencilSquareIcon className="h-4 w-4" />
              </button>
            ),
          },
        ]
      : []),
  ];

  const fieldTypes = ['text', 'url', 'number', 'date', 'select', 'calc', 'date_calc', 'readonly'];

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
            <Input
              label="카테고리"
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            />
            <Input
              label="기본가격"
              type="number"
              value={formData.base_price}
              onChange={(e) => setFormData({ ...formData, base_price: e.target.value })}
            />
          </div>
          <Input
            label="설명"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-4">
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

          {/* Schema Builder */}
          <div className="border-t border-gray-200 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-900">주문 폼 스키마</h3>
              <Button size="sm" variant="secondary" onClick={addSchemaField} icon={<PlusIcon className="h-3 w-3" />}>
                필드 추가
              </Button>
            </div>

            {schemaFields.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">스키마 필드가 없습니다.</p>
            ) : (
              <div className="space-y-2">
                {schemaFields.map((field, idx) => (
                  <div key={idx} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg">
                    <input
                      value={field.name}
                      onChange={(e) => updateSchemaField(idx, 'name', e.target.value)}
                      placeholder="필드명"
                      className="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <input
                      value={field.label}
                      onChange={(e) => updateSchemaField(idx, 'label', e.target.value)}
                      placeholder="라벨"
                      className="flex-1 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <select
                      value={field.type}
                      onChange={(e) => updateSchemaField(idx, 'type', e.target.value)}
                      className="px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                    >
                      {fieldTypes.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    <label className="flex items-center gap-1 text-xs text-gray-600">
                      <input
                        type="checkbox"
                        checked={field.required || false}
                        onChange={(e) => updateSchemaField(idx, 'required', e.target.checked)}
                        className="rounded border-gray-300"
                      />
                      필수
                    </label>
                    <button
                      onClick={() => removeSchemaField(idx)}
                      className="p-1 text-red-400 hover:text-red-600"
                    >
                      &times;
                    </button>
                  </div>
                ))}
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
