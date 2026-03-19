import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import OrderList from '@/components/features/orders/OrderList';
import SubAccountOrders from '@/components/features/orders/SubAccountOrders';
import Pagination from '@/components/common/Pagination';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import {
  MagnifyingGlassIcon,
  PlusIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  TrashIcon,
  InboxStackIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';
import type { Order, OrderStatus } from '@/types';
import { useAuthStore } from '@/store/auth';
import { ordersApi } from '@/api/orders';
import { downloadBlob } from '@/utils/format';

type TabKey = 'all' | 'pending' | 'processing' | 'completed' | 'hold';

interface TabDef {
  key: TabKey;
  label: string;
  statuses: OrderStatus[];
}

const TABS: TabDef[] = [
  { key: 'all',        label: '전체',      statuses: [] },
  { key: 'pending',    label: '접수대기',  statuses: ['submitted', 'payment_hold'] },
  { key: 'processing', label: '처리중',    statuses: ['payment_confirmed', 'processing'] },
  { key: 'completed',  label: '완료',      statuses: ['completed'] },
  { key: 'hold',       label: '보류/반려', statuses: ['cancelled', 'rejected', 'payment_hold'] },
];

const orderTypeOptions: { value: string; label: string }[] = [
  { value: '', label: '전체 유형' },
  { value: 'regular', label: '일반' },
  { value: 'monthly_guarantee', label: '월보장' },
  { value: 'managed', label: '관리형' },
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
  const user = useAuthStore((s) => s.user);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [activeTab, setActiveTab] = useState<TabKey>('all');
  const [orderTypeFilter, setOrderTypeFilter] = useState('');
  const [search, setSearch] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkStatus, setBulkStatus] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [showPaymentConfirmModal, setShowPaymentConfirmModal] = useState(false);
  const [paymentConfirmLoading, setPaymentConfirmLoading] = useState(false);

  const canCreate = user && ['system_admin', 'company_admin', 'distributor', 'sub_account'].includes(user.role);
  const canBulk = user && ['system_admin', 'company_admin'].includes(user.role);
  const canPaymentConfirm = user && ['system_admin', 'company_admin', 'order_handler'].includes(user.role);
  const isDistributor = user?.role === 'distributor';
  const isPendingTab = activeTab === 'pending';

  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const currentTab = TABS.find((t) => t.key === activeTab)!;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const statusParam =
      currentTab.statuses.length === 1
        ? currentTab.statuses[0]
        : currentTab.statuses.length > 1
        ? currentTab.statuses.join(',')
        : undefined;

    ordersApi
      .list({
        page,
        size: 20,
        status: statusParam,
        search: debouncedSearch || undefined,
        order_type: orderTypeFilter || undefined,
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
  }, [activeTab, orderTypeFilter, page, refreshKey, debouncedSearch]);

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab);
    setPage(1);
    setSelectedIds(new Set());
  };

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
      if ((result as any).errors?.length > 0) {
        alert(`일부 삭제 실패:\n${(result as any).errors.join('\n')}`);
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || '일괄 삭제에 실패했습니다.');
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleBulkPaymentConfirm = async () => {
    if (selectedIds.size === 0) return;
    setPaymentConfirmLoading(true);
    try {
      await ordersApi.bulkPaymentConfirm(Array.from(selectedIds));
      setShowPaymentConfirmModal(false);
      setRefreshKey((k) => k + 1);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '일괄 입금확인에 실패했습니다.');
    } finally {
      setPaymentConfirmLoading(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const statusParam =
        currentTab.statuses.length === 1
          ? currentTab.statuses[0]
          : currentTab.statuses.length > 1
          ? currentTab.statuses.join(',')
          : undefined;
      const blob = await ordersApi.exportList({ status: statusParam });
      downloadBlob(blob, `주문목록_${new Date().toISOString().split('T')[0]}.xlsx`);
    } catch {
      alert('내보내기에 실패했습니다.');
    } finally {
      setExporting(false);
    }
  };

  const showSelectAll = (canBulk || (isPendingTab && canPaymentConfirm)) && orders.length > 0;
  const showBulkActions = selectedIds.size > 0;

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">주문 관리</h1>
          <p className="mt-1 text-sm text-gray-400">
            접수, 입금 확인, 추출, 세팅 진행 현황을 주문 단위로 관리합니다.
          </p>
        </div>
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
      </div>

      {/* 상태 탭 */}
      <div className="bg-surface rounded-xl p-1 flex gap-1 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? 'bg-primary-600 text-white'
                : 'bg-surface-raised text-gray-400 hover:text-gray-200 hover:bg-surface-raised/80'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 접수대기 탭: 하부계정 대기건 (distributor) */}
      {isPendingTab && isDistributor && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <InboxStackIcon className="h-4 w-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-gray-300">하부계정 대기 접수건</h2>
          </div>
          <SubAccountOrders />
        </div>
      )}

      {/* 일괄 액션 바 */}
      {showBulkActions && (
        <div className="flex items-center gap-3 bg-primary-900/20 border border-primary-800 rounded-lg p-3">
          <span className="text-sm font-medium text-primary-300">{selectedIds.size}건 선택</span>
          {isPendingTab && canPaymentConfirm && (
            <Button
              size="sm"
              onClick={() => setShowPaymentConfirmModal(true)}
              icon={<CheckCircleIcon className="h-3 w-3" />}
            >
              일괄 입금확인
            </Button>
          )}
          {canBulk && (
            <>
              <Button size="sm" variant="secondary" onClick={() => setShowBulkModal(true)} icon={<ArrowPathIcon className="h-3 w-3" />}>
                일괄 상태변경
              </Button>
              <Button size="sm" variant="danger" onClick={() => setShowDeleteModal(true)} icon={<TrashIcon className="h-3 w-3" />}>
                일괄 삭제
              </Button>
            </>
          )}
          <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
            선택 해제
          </Button>
        </div>
      )}

      {/* 검색 + 유형 필터 */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="주문번호, 주문자 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-border-strong text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400 bg-surface text-gray-200"
          />
        </div>
        <select
          value={orderTypeFilter}
          onChange={(e) => {
            setOrderTypeFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400 bg-surface text-gray-200"
        >
          {orderTypeOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* 전체 선택 체크박스 */}
      {showSelectAll && (
        <div className="flex items-center gap-2 px-1">
          <input
            type="checkbox"
            checked={selectedIds.size === orders.length && orders.length > 0}
            onChange={toggleSelectAll}
            className="rounded border-border-strong text-primary-400 focus:ring-primary-400/40"
          />
          <span className="text-xs text-gray-400">전체 선택</span>
        </div>
      )}

      <OrderList
        orders={orders}
        loading={loading}
        selectable={(canBulk || (isPendingTab && canPaymentConfirm)) || false}
        selectedIds={selectedIds}
        onToggleSelect={toggleSelect}
      />

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalItems={totalItems}
        pageSize={20}
      />

      {/* 일괄 입금확인 모달 */}
      <Modal
        isOpen={showPaymentConfirmModal}
        onClose={() => setShowPaymentConfirmModal(false)}
        title="일괄 입금확인"
        size="sm"
      >
        <div className="space-y-4 p-1">
          <p className="text-sm text-gray-400">
            선택한 {selectedIds.size}건의 주문을 입금 확인하시겠습니까?
          </p>
          <p className="text-xs text-cyan-500">
            확인 후 자동으로 세팅이 시작됩니다.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowPaymentConfirmModal(false)}>취소</Button>
            <Button onClick={handleBulkPaymentConfirm} loading={paymentConfirmLoading}>
              입금 확인
            </Button>
          </div>
        </div>
      </Modal>

      {/* 일괄 삭제 모달 */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="일괄 삭제"
        size="sm"
      >
        <div className="space-y-4 p-1">
          <p className="text-sm text-gray-400">
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

      {/* 일괄 상태변경 모달 */}
      <Modal
        isOpen={showBulkModal}
        onClose={() => setShowBulkModal(false)}
        title="일괄 상태 변경"
        size="sm"
      >
        <div className="space-y-4 p-1">
          <p className="text-sm text-gray-400">{selectedIds.size}건의 주문 상태를 변경합니다.</p>
          <select
            value={bulkStatus}
            onChange={(e) => setBulkStatus(e.target.value)}
            className="w-full rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
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
    </div>
  );
}
