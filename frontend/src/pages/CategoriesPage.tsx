import { useState, useEffect } from 'react';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import Badge from '@/components/common/Badge';
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ArrowUpIcon,
  ArrowDownIcon,
} from '@heroicons/react/24/outline';
import { categoriesApi } from '@/api/categories';
import type { Category } from '@/types';

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [reordering, setReordering] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    categoriesApi
      .list({ size: 100 })
      .then((data) => {
        if (!cancelled) {
          const sorted = [...data.items].sort((a, b) => a.sort_order - b.sort_order);
          setCategories(sorted);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '카테고리를 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [refreshKey]);

  const openCreate = () => {
    setEditing(null);
    setFormName('');
    setFormDescription('');
    setShowModal(true);
  };

  const openEdit = (cat: Category) => {
    setEditing(cat);
    setFormName(cat.name);
    setFormDescription(cat.description || '');
    setShowModal(true);
  };

  const handleSubmit = async () => {
    if (!formName.trim()) {
      alert('카테고리 이름을 입력하세요.');
      return;
    }

    setSubmitting(true);
    try {
      if (editing) {
        await categoriesApi.update(editing.id, {
          name: formName,
          description: formDescription || undefined,
        });
      } else {
        await categoriesApi.create({
          name: formName,
          description: formDescription || undefined,
        });
      }
      setShowModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('이 카테고리를 삭제하시겠습니까?')) return;
    try {
      await categoriesApi.delete(id);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '삭제에 실패했습니다.');
    }
  };

  const handleMove = async (index: number, direction: 'up' | 'down') => {
    const newCategories = [...categories];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= newCategories.length) return;

    [newCategories[index], newCategories[targetIndex]] = [newCategories[targetIndex], newCategories[index]];

    setCategories(newCategories);
    setReordering(true);

    try {
      await categoriesApi.reorder({
        items: newCategories.map((cat, idx) => ({ id: cat.id, sort_order: idx })),
      });
    } catch (err: any) {
      alert('순서 변경에 실패했습니다.');
      setRefreshKey((k) => k + 1);
    } finally {
      setReordering(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">카테고리 관리</h1>
          <p className="mt-1 text-sm text-gray-500">상품 카테고리를 관리하고 순서를 변경합니다.</p>
        </div>
        <Button onClick={openCreate} icon={<PlusIcon className="h-4 w-4" />}>
          카테고리 추가
        </Button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      {/* Category List */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm divide-y divide-gray-200">
        {loading ? (
          <div className="animate-pulse space-y-3 p-4">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 bg-gray-200 rounded" />)}
          </div>
        ) : categories.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">카테고리가 없습니다.</div>
        ) : (
          categories.map((cat, index) => (
            <div key={cat.id} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors">
              <div className="flex items-center gap-3">
                <div className="flex flex-col gap-0.5">
                  <button
                    onClick={() => handleMove(index, 'up')}
                    disabled={index === 0 || reordering}
                    className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  >
                    <ArrowUpIcon className="h-3 w-3" />
                  </button>
                  <button
                    onClick={() => handleMove(index, 'down')}
                    disabled={index === categories.length - 1 || reordering}
                    className="p-0.5 text-gray-400 hover:text-gray-600 disabled:opacity-30"
                  >
                    <ArrowDownIcon className="h-3 w-3" />
                  </button>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{cat.name}</span>
                    <Badge variant={cat.is_active ? 'success' : 'default'}>
                      {cat.is_active ? '활성' : '비활성'}
                    </Badge>
                  </div>
                  {cat.description && (
                    <p className="text-xs text-gray-500 mt-0.5">{cat.description}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => openEdit(cat)}
                  className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                >
                  <PencilSquareIcon className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleDelete(cat.id)}
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editing ? '카테고리 수정' : '카테고리 추가'}
        size="sm"
      >
        <div className="space-y-4 p-1">
          <Input
            label="카테고리 이름"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            placeholder="예: 트래픽, 저장, 자동완성"
            required
          />
          <Input
            label="설명"
            value={formDescription}
            onChange={(e) => setFormDescription(e.target.value)}
            placeholder="선택사항"
          />
          <div className="flex justify-end gap-2 pt-2">
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
