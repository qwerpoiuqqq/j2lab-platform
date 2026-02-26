import { useState, useEffect } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import Pagination from '@/components/common/Pagination';
import { PlusIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';
import { formatDateTime } from '@/utils/format';
import { noticesApi } from '@/api/notices';
import { useAuthStore } from '@/store/auth';
import type { Notice } from '@/types';

export default function NoticesPage() {
  const user = useAuthStore((s) => s.user);
  const canManage = user && ['system_admin', 'company_admin'].includes(user.role);

  const [notices, setNotices] = useState<Notice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  const [showModal, setShowModal] = useState(false);
  const [editingNotice, setEditingNotice] = useState<Notice | null>(null);
  const [formTitle, setFormTitle] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formPinned, setFormPinned] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    noticesApi
      .list({ page, size: 20 })
      .then((data) => {
        if (!cancelled) {
          const sorted = [...data.items].sort((a, b) => {
            if (a.is_pinned && !b.is_pinned) return -1;
            if (!a.is_pinned && b.is_pinned) return 1;
            return 0;
          });
          setNotices(sorted);
          setTotalPages(data.pages);
          setTotalItems(data.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '공지사항을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [page, refreshKey]);

  const openCreate = () => {
    setEditingNotice(null);
    setFormTitle('');
    setFormContent('');
    setFormPinned(false);
    setShowModal(true);
  };

  const openEdit = (notice: Notice) => {
    setEditingNotice(notice);
    setFormTitle(notice.title);
    setFormContent(notice.content);
    setFormPinned(notice.is_pinned);
    setShowModal(true);
  };

  const handleSubmit = async () => {
    if (!formTitle.trim() || !formContent.trim()) {
      alert('제목과 내용을 입력하세요.');
      return;
    }

    setSubmitting(true);
    try {
      if (editingNotice) {
        await noticesApi.update(editingNotice.id, {
          title: formTitle,
          content: formContent,
          is_pinned: formPinned,
        });
      } else {
        await noticesApi.create({
          title: formTitle,
          content: formContent,
          is_pinned: formPinned,
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
    if (!confirm('이 공지사항을 삭제하시겠습니까?')) return;
    try {
      await noticesApi.delete(id);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '삭제에 실패했습니다.');
    }
  };

  const columns: Column<Notice>[] = [
    {
      key: 'title',
      header: '제목',
      render: (n) => (
        <div className="flex items-center gap-2">
          {n.is_pinned && <Badge variant="warning">고정</Badge>}
          <span className="font-medium text-gray-900">{n.title}</span>
        </div>
      ),
    },
    {
      key: 'content',
      header: '내용',
      render: (n) => (
        <span className="text-sm text-gray-600 line-clamp-1">{n.content}</span>
      ),
    },
    {
      key: 'created_at',
      header: '작성일',
      render: (n) => (
        <span className="text-xs text-gray-500">{formatDateTime(n.created_at)}</span>
      ),
    },
    ...(canManage
      ? [
          {
            key: 'actions' as keyof Notice,
            header: '작업',
            render: (n: Notice) => (
              <div className="flex items-center gap-1">
                <button
                  onClick={(e) => { e.stopPropagation(); openEdit(n); }}
                  className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                >
                  <PencilSquareIcon className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(n.id); }}
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">공지 관리</h1>
          <p className="mt-1 text-sm text-gray-500">공지사항을 관리합니다.</p>
        </div>
        {canManage && (
          <Button onClick={openCreate} icon={<PlusIcon className="h-4 w-4" />}>
            공지 작성
          </Button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      <Table<Notice>
        columns={columns}
        data={notices}
        keyExtractor={(n) => n.id}
        loading={loading}
        emptyMessage="공지사항이 없습니다."
      />

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalItems={totalItems}
        pageSize={20}
      />

      {/* Create/Edit Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingNotice ? '공지 수정' : '공지 작성'}
        size="lg"
      >
        <div className="space-y-4 p-1">
          <Input
            label="제목"
            value={formTitle}
            onChange={(e) => setFormTitle(e.target.value)}
            placeholder="공지사항 제목"
            required
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              내용 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={formContent}
              onChange={(e) => setFormContent(e.target.value)}
              placeholder="공지사항 내용을 입력하세요."
              rows={8}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={formPinned}
              onChange={(e) => setFormPinned(e.target.checked)}
              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700">상단 고정</span>
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              취소
            </Button>
            <Button onClick={handleSubmit} loading={submitting}>
              {editingNotice ? '수정' : '작성'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
