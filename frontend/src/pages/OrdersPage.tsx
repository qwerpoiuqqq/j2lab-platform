import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import OrderList from '@/components/features/orders/OrderList';
import Pagination from '@/components/common/Pagination';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import {
  MagnifyingGlassIcon,
  PlusIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import type { Order, OrderStatus } from '@/types';
import { useAuthStore } from '@/store/auth';
import { ordersApi } from '@/api/orders';
import { downloadBlob } from '@/utils/format';
import AssignmentQueuePage from '@/pages/AssignmentQueuePage';

const statusOptions: { value: string; label: string }[] = [
  { value: '', label: '전체 상태' },
  { value: 'draft', label: '임시저장' },
  { value: 'submitted', label: '접수완료' },
  { value: 'payment_confirmed', label: '입금확인' },
  { value: 'processing', label: '처리중' },
  { value: 'completed', label: '완료' },
  { value: 'cancelled', label: '취소' },
  { value: 'rejected', label: '반려' },
];

const bulkStatusOptions: { value: string; label: string }[] = [
  { value: 'submitted', label: '접수완료' },
  { value: 'payment_confirmed', label: '입금확인' },
  { value: 'processing', label: '처리중' },
  { value: 'completed', label: '완료' },
  { value: 'cancelled', label: '취소' },
];

export default function OrdersPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const user = useAuthStore((s) => s.user);

  const canViewQueue = user && ['system_admin', 'company_admin', 'order_handler'].includes(user.role);
  const activeTab = searchParams.get('tab') === 'queue' && canViewQueue ? 'queue' : 'orders';
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState<OrderStatus | ''>('');
  const [search, setSearch] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkStatus, setBulkStatus] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const canCreate = user && ['distributor', 'sub_account'].includes(user.role);
  const canBulk = user && ['system_admin', 'company_admin'].includes(user.role);

  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    ordersApi
      .list({
        page,
        size: 20,
        status: statusFilter || undefined,
        search: debouncedSearch || undefined,
      })
      .then((data) => {
        if (!cancelled) {
          setOrders(data.items);
          setTotalPages(data.pages);
          setTotalItems(data.total);
          setLoading(false);
          setSelectedIds(new Set());
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '주문 목록을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [statusFilter, page, refreshKey, debouncedSearch]);

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === orders.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(orders.map((o) => o.id)));
    }
  };

  const handleBulkStatus = async () => {
    if (!bulkStatus || selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      await ordersApi.bulkStatus({
        order_ids: Array.from(selectedIds),
        status: bulkStatus as OrderStatus,
      });
      setShowBulkModal(false);
      setBulkStatus('');
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '일괄 변경에 실패했습니다.');
    } finally {
      setBulkLoading(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    setDeleteLoading(true);
    try {
      const result = await ordersApi.bulkDelete(Array.from(selectedIds));
      setShowDeleteModal(false);
      setRefreshKey((k) => k + 1);
      if (result.detail?.errors?.length > 0) {
        alert(`일부 삭제 실패:\n${(result as any).detail.errors.join('\n')}`);
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || '일괄 삭제에 실패했습니다.');
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await ordersApi.exportList({
        status: statusFilter || undefined,
      });
      downloadBlob(blob, `주문목록_${new Date().toISOString().split('T')[0]}.xlsx`);
    } catch {
      alert('내보내기에 실패했습니다.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">주문 관리</h1>
          <p className="mt-1 text-sm text-gray-500">
            {activeTab === 'orders'
              ? '주문 목록을 조회하고 관리합니다.'
              : '자동 배정된 계정을 확인하고 캠페인 등록을 진행합니다.'}
          </p>
        </div>
        {activeTab === 'orders' && (
          <div className="flex gap-2">
            {canBulk && (
              <Button
                variant="secondary"
                onClick={handleExport}
                loading={exporting}
                icon={<ArrowDownTrayIcon className="h-4 w-4" />}
              >
                Excel
              </Button>
            )}
            {canCreate && (
              <Button
                onClick={() => navigate('/orders/grid')}
                icon={<PlusIcon className="h-4 w-4" />}
              >
                주문 접수
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setSearchParams({})}
            className={`whitespace-nowrap pb-3 px-1 border-b-2 text-sm font-medium transition-colors ${
              activeTab === 'orders'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            주문 내역
          </button>
          {canViewQueue && (
            <button
              onClick={() => setSearchParams({ tab: 'queue' })}
              className={`whitespace-nowrap pb-3 px-1 border-b-2 text-sm font-medium transition-colors ${
                activeTab === 'queue'
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              배정 대기열
            </button>
          )}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'queue' ? (
        <AssignmentQueuePage />
      ) : (
        <>
          {/* Bulk Actions */}
          {canBulk && selectedIds.size > 0 && (
            <div className="flex items-center gap-3 bg-primary-50 border border-primary-200 rounded-lg p-3">
              <span className="text-sm font-medium text-primary-700">{selectedIds.size}건 선택</span>
              <Button size="sm" variant="secondary" onClick={() => setShowBulkModal(true)} icon={<ArrowPathIcon className="h-3 w-3" />}>
                일괄 상태변경
              </Button>
              <Button size="sm" variant="danger" onClick={() => setShowDeleteModal(true)} icon={<TrashIcon className="h-3 w-3" />}>
                일괄 삭제
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
                선택 해제
              </Button>
            </div>
          )}

          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1 max-w-md">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="주문번호, 주문자 검색..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as OrderStatus | '');
                setPage(1);
              }}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              {statusOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Table with checkboxes */}
          {canBulk && orders.length > 0 && (
            <div className="flex items-center gap-2 px-1">
              <input
                type="checkbox"
                checked={selectedIds.size === orders.length && orders.length > 0}
                onChange={toggleSelectAll}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-xs text-gray-500">전체 선택</span>
            </div>
          )}
          <OrderList
            orders={orders}
            loading={loading}
            selectable={canBulk || false}
            selectedIds={selectedIds}
            onToggleSelect={toggleSelect}
          />

          {/* Pagination */}
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalItems={totalItems}
            pageSize={20}
          />

          {/* Bulk Delete Modal */}
          <Modal
            isOpen={showDeleteModal}
            onClose={() => setShowDeleteModal(false)}
            title="일괄 삭제"
            size="sm"
          >
            <div className="space-y-4 p-1">
              <p className="text-sm text-gray-600">
                {selectedIds.size}건의 주문을 삭제하시겠습니까?
              </p>
              <p className="text-xs text-red-500">
                임시저장/취소/반려 상태의 주문만 삭제됩니다. 이 작업은 되돌릴 수 없습니다.
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>취소</Button>
                <Button variant="danger" onClick={handleBulkDelete} loading={deleteLoading}>
                  삭제 확인
                </Button>
              </div>
            </div>
          </Modal>

          {/* Bulk Status Modal */}
          <Modal
            isOpen={showBulkModal}
            onClose={() => setShowBulkModal(false)}
            title="일괄 상태 변경"
            size="sm"
          >
            <div className="space-y-4 p-1">
              <p className="text-sm text-gray-600">{selectedIds.size}건의 주문 상태를 변경합니다.</p>
              <select
                value={bulkStatus}
                onChange={(e) => setBulkStatus(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">상태 선택</option>
                {bulkStatusOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <div className="flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setShowBulkModal(false)}>취소</Button>
                <Button onClick={handleBulkStatus} loading={bulkLoading} disabled={!bulkStatus}>변경</Button>
              </div>
            </div>
          </Modal>
        </>
      )}
    </div>
  );
}
