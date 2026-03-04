import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import OrderDetailComponent from '@/components/features/orders/OrderDetail';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import {
  ArrowLeftIcon,
  ArrowDownTrayIcon,
  CalendarIcon,
  ArrowPathIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import type { Order, OrderItem } from '@/types';
import { ordersApi } from '@/api/orders';
import { useAuthStore } from '@/store/auth';
import { downloadBlob } from '@/utils/format';

export default function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [order, setOrder] = useState<Order | null>(null);
  const [items, setItems] = useState<OrderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Reject modal
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  // Hold modal
  const [showHoldModal, setShowHoldModal] = useState(false);
  const [holdReason, setHoldReason] = useState('');

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Deadline modal
  const [showDeadlineModal, setShowDeadlineModal] = useState(false);
  const [deadlineValue, setDeadlineValue] = useState('');
  const [deadlineLoading, setDeadlineLoading] = useState(false);

  const isAdmin = user && ['system_admin', 'company_admin'].includes(user.role);
  const canDelete = isAdmin && order && ['draft', 'cancelled', 'rejected'].includes(order.status);

  const loadOrder = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await ordersApi.get(Number(id));
      setOrder(data);
      setItems(data.items || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '주문을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // eslint warns about loadOrder not in deps, but loadOrder references `id` from closure.
  // Including loadOrder would cause infinite loop since it's redefined every render.
  // Using `id` as dep is the correct behavior: re-fetch when id changes.
  useEffect(() => {
    loadOrder();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleAction = async (action: string) => {
    if (!id) return;
    setActionLoading(true);
    try {
      let updated: Order;
      switch (action) {
        case 'submit':
          updated = await ordersApi.submit(Number(id));
          break;
        case 'confirm-payment':
          updated = await ordersApi.confirmPayment(Number(id));
          if ((updated as any).pipeline_warnings?.length > 0) {
            alert('파이프라인 경고:\n' + (updated as any).pipeline_warnings.join('\n'));
          }
          break;
        case 'approve':
          updated = await ordersApi.approve(Number(id));
          break;
        case 'reject': {
          setShowRejectModal(true);
          setActionLoading(false);
          return;
        }
        case 'hold': {
          setShowHoldModal(true);
          setActionLoading(false);
          return;
        }
        case 'release-hold':
          updated = await ordersApi.releaseHold(Number(id));
          break;
        case 'cancel':
          updated = await ordersApi.cancel(Number(id));
          break;
        default:
          setActionLoading(false);
          return;
      }
      setOrder(updated);
      setItems(updated.items || []);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '작업에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRejectConfirm = async () => {
    if (!id || !rejectReason.trim()) return;
    setActionLoading(true);
    try {
      const updated = await ordersApi.reject(Number(id), rejectReason);
      setOrder(updated);
      setItems(updated.items || []);
      setShowRejectModal(false);
      setRejectReason('');
    } catch (err: any) {
      alert(err?.response?.data?.detail || '반려에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleHoldConfirm = async () => {
    if (!id || !holdReason.trim()) return;
    setActionLoading(true);
    try {
      const updated = await ordersApi.holdOrder(Number(id), holdReason);
      setOrder(updated);
      setItems(updated.items || []);
      setShowHoldModal(false);
      setHoldReason('');
    } catch (err: any) {
      alert(err?.response?.data?.detail || '보류에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleExportItems = async () => {
    if (!id) return;
    try {
      const blob = await ordersApi.exportItems(Number(id));
      downloadBlob(blob, `주문항목_${order?.order_number || id}.xlsx`);
    } catch {
      alert('내보내기에 실패했습니다.');
    }
  };

  const handleDelete = async () => {
    if (!id) return;
    setDeleteLoading(true);
    try {
      await ordersApi.delete(Number(id));
      navigate('/orders');
    } catch (err: any) {
      alert(err?.response?.data?.detail || '삭제에 실패했습니다.');
    } finally {
      setDeleteLoading(false);
      setShowDeleteModal(false);
    }
  };

  const handleDeadlineUpdate = async () => {
    if (!id || !deadlineValue) return;
    setDeadlineLoading(true);
    try {
      const updated = await ordersApi.updateDeadline(Number(id), { deadline: deadlineValue });
      setOrder(updated);
      setShowDeadlineModal(false);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '마감일 변경에 실패했습니다.');
    } finally {
      setDeadlineLoading(false);
    }
  };

  if (error) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/orders')}
          icon={<ArrowLeftIcon className="h-4 w-4" />}
        >
          목록으로
        </Button>
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-red-400 text-sm">
          {error}
        </div>
      </div>
    );
  }

  if (loading || !order) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="bg-surface rounded-xl border border-border h-48" />
        <div className="bg-surface rounded-xl border border-border h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/orders')}
          icon={<ArrowLeftIcon className="h-4 w-4" />}
        >
          목록으로
        </Button>

        {/* Top action buttons */}
        <div className="flex gap-2">
          {isAdmin && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowDeadlineModal(true)}
              icon={<CalendarIcon className="h-4 w-4" />}
            >
              마감일 변경
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={handleExportItems}
            icon={<ArrowDownTrayIcon className="h-4 w-4" />}
          >
            항목 Excel
          </Button>
          {canDelete && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setShowDeleteModal(true)}
              icon={<TrashIcon className="h-4 w-4" />}
            >
              삭제
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={loadOrder}
            icon={<ArrowPathIcon className="h-4 w-4" />}
          >
            갱신
          </Button>
        </div>
      </div>

      <OrderDetailComponent
        order={order}
        items={items}
        onSubmit={() => handleAction('submit')}
        onConfirmPayment={() => handleAction('confirm-payment')}
        onReject={() => handleAction('reject')}
        onCancel={() => handleAction('cancel')}
        onHold={() => handleAction('hold')}
        onReleaseHold={() => handleAction('release-hold')}
        actionLoading={actionLoading}
      />

      {/* Reject Modal */}
      <Modal
        isOpen={showRejectModal}
        onClose={() => { setShowRejectModal(false); setRejectReason(''); }}
        title="주문 반려"
        size="sm"
      >
        <div className="space-y-4 p-1">
          <p className="text-sm text-gray-400">반려 사유를 입력하세요.</p>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="반려 사유를 입력하세요..."
            rows={4}
            className="w-full rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400 bg-surface text-gray-200"
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => { setShowRejectModal(false); setRejectReason(''); }}>
              취소
            </Button>
            <Button
              variant="warning"
              onClick={handleRejectConfirm}
              loading={actionLoading}
              disabled={!rejectReason.trim()}
            >
              반려 확인
            </Button>
          </div>
        </div>
      </Modal>

      {/* Hold Modal */}
      <Modal
        isOpen={showHoldModal}
        onClose={() => { setShowHoldModal(false); setHoldReason(''); }}
        title="입금 보류"
        size="sm"
      >
        <div className="space-y-4 p-1">
          <p className="text-sm text-gray-400">보류 사유를 입력하세요.</p>
          <textarea
            value={holdReason}
            onChange={(e) => setHoldReason(e.target.value)}
            placeholder="보류 사유를 입력하세요..."
            rows={4}
            className="w-full rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 focus:border-primary-400 bg-surface text-gray-200"
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => { setShowHoldModal(false); setHoldReason(''); }}>
              취소
            </Button>
            <Button
              variant="warning"
              onClick={handleHoldConfirm}
              loading={actionLoading}
              disabled={!holdReason.trim()}
            >
              보류 확인
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirm Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="주문 삭제"
        size="sm"
      >
        <div className="space-y-4 p-1">
          <p className="text-sm text-gray-400">
            주문 <span className="font-semibold">#{order.order_number}</span>을(를) 삭제하시겠습니까?
          </p>
          <p className="text-xs text-red-500">이 작업은 되돌릴 수 없습니다.</p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowDeleteModal(false)}>취소</Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              loading={deleteLoading}
            >
              삭제 확인
            </Button>
          </div>
        </div>
      </Modal>

      {/* Deadline Modal */}
      <Modal
        isOpen={showDeadlineModal}
        onClose={() => setShowDeadlineModal(false)}
        title="마감일 변경"
        size="sm"
      >
        <div className="space-y-4 p-1">
          <p className="text-sm text-gray-400">주문 #{order.order_number}의 마감일을 변경합니다.</p>
          <input
            type="datetime-local"
            value={deadlineValue}
            onChange={(e) => setDeadlineValue(e.target.value)}
            className="w-full rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
          />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowDeadlineModal(false)}>취소</Button>
            <Button onClick={handleDeadlineUpdate} loading={deadlineLoading} disabled={!deadlineValue}>변경</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
