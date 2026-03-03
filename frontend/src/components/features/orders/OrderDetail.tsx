import type { Order, OrderItem } from '@/types';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import PipelineStatusWidget from '@/components/features/orders/PipelineStatusWidget';
import {
  formatCurrency,
  formatDateTime,
  getOrderStatusLabel,
  getItemStatusLabel,
} from '@/utils/format';
import { useAuthStore } from '@/store/auth';

interface OrderDetailProps {
  order: Order;
  items: OrderItem[];
  onSubmit?: () => void;
  onConfirmPayment?: () => void;
  onReject?: () => void;
  onCancel?: () => void;
  onHold?: () => void;
  onReleaseHold?: () => void;
  actionLoading?: boolean;
}

function getStatusBadgeVariant(status: string) {
  const map: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    draft: 'default',
    submitted: 'info',
    payment_hold: 'warning',
    payment_confirmed: 'success',
    processing: 'warning',
    completed: 'success',
    cancelled: 'danger',
    rejected: 'danger',
  };
  return map[status] || 'default';
}

export default function OrderDetail({
  order,
  items,
  onSubmit,
  onConfirmPayment,
  onReject,
  onCancel,
  onHold,
  onReleaseHold,
  actionLoading,
}: OrderDetailProps) {
  const user = useAuthStore((s) => s.user);
  const userRole = user?.role;
  const isAdmin = ['system_admin', 'company_admin'].includes(userRole || '');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-gray-900">
                {order.order_number}
              </h2>
              <Badge variant={getStatusBadgeVariant(order.status)}>
                {getOrderStatusLabel(order.status)}
              </Badge>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              {formatDateTime(order.created_at)} 접수
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {/* draft: 접수 제출 (모든 역할) */}
            {order.status === 'draft' && (
              <Button
                variant="primary"
                onClick={onSubmit}
                loading={actionLoading}
              >
                접수 제출
              </Button>
            )}

            {/* submitted: 입금 확인, 보류, 반려 (관리자) */}
            {order.status === 'submitted' && isAdmin && (
              <>
                <Button
                  variant="success"
                  onClick={onConfirmPayment}
                  loading={actionLoading}
                >
                  입금 확인
                </Button>
                <Button
                  variant="warning"
                  onClick={onHold}
                  loading={actionLoading}
                >
                  보류
                </Button>
                <Button
                  variant="warning"
                  onClick={onReject}
                  loading={actionLoading}
                >
                  반려
                </Button>
              </>
            )}

            {/* payment_hold: 입금 확인, 보류 해제, 반려 (관리자) */}
            {order.status === 'payment_hold' && isAdmin && (
              <>
                <Button
                  variant="success"
                  onClick={onConfirmPayment}
                  loading={actionLoading}
                >
                  입금 확인
                </Button>
                <Button
                  variant="secondary"
                  onClick={onReleaseHold}
                  loading={actionLoading}
                >
                  보류 해제
                </Button>
                <Button
                  variant="warning"
                  onClick={onReject}
                  loading={actionLoading}
                >
                  반려
                </Button>
              </>
            )}

            {/* draft/submitted/payment_hold: 취소 (관리자) */}
            {['draft', 'submitted', 'payment_hold'].includes(order.status) && isAdmin && (
              <Button
                variant="danger"
                onClick={onCancel}
                loading={actionLoading}
              >
                취소
              </Button>
            )}
          </div>
        </div>

        {/* Hold reason banner */}
        {order.status === 'payment_hold' && (order as any).hold_reason && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-xs text-amber-600 uppercase mb-1">보류 사유</p>
            <p className="text-sm text-amber-800">{(order as any).hold_reason}</p>
          </div>
        )}

        {/* Info grid */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-gray-500 uppercase">주문자</p>
            <p className="mt-1 text-sm font-medium text-gray-900">
              {order.user?.name || '-'}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase">소속 회사</p>
            <p className="mt-1 text-sm font-medium text-gray-900">
              {order.company?.name || '-'}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase">총 금액</p>
            <p className="mt-1 text-sm font-bold text-gray-900">
              {formatCurrency(order.total_amount)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase">VAT</p>
            <p className="mt-1 text-sm font-medium text-gray-900">
              {formatCurrency(order.vat_amount)}
            </p>
          </div>
        </div>

        {order.notes && (
          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 uppercase mb-1">메모</p>
            <p className="text-sm text-gray-700">{order.notes}</p>
          </div>
        )}
      </div>

      {/* Items */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-base font-semibold text-gray-900">
            주문 항목 ({items.length}건)
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  상품
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  플레이스
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  수량
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  단가
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  소계
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  상태
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {items.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-8 text-center text-sm text-gray-500"
                  >
                    주문 항목이 없습니다.
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const placeName = item.item_data?.place_name || item.item_data?.상호명 || '';
                  const placeUrl = item.item_data?.place_url || '';
                  const campaignType = item.item_data?.campaign_type || '';
                  const productLabel = item.product?.name
                    ? `${item.product.name}${campaignType ? ` (${campaignType === 'traffic' ? '트래픽' : campaignType === 'save' ? '저장하기' : campaignType})` : ''}`
                    : `상품 #${item.product_id}`;

                  return (
                    <tr key={item.id}>
                      <td className="px-6 py-4 text-sm text-gray-900">
                        {productLabel}
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <div>
                          <p className="text-gray-900 font-medium">
                            {placeName || (placeUrl ? placeUrl.split('/').pop()?.split('?')[0] || '-' : '-')}
                          </p>
                          {placeUrl && (
                            <a
                              href={placeUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-primary-500 hover:underline truncate block max-w-[250px]"
                            >
                              {placeUrl}
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {item.quantity}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {formatCurrency(item.unit_price)}
                      </td>
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">
                        {formatCurrency(item.subtotal)}
                      </td>
                      <td className="px-6 py-4">
                        <Badge>{getItemStatusLabel(item.status)}</Badge>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pipeline Status per Item */}
      {items.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-base font-semibold text-gray-900 px-6">파이프라인 현황</h3>
          {items.map((item) => (
            <div key={`pipeline-${item.id}`} className="px-6">
              <p className="text-sm text-gray-600 mb-2">
                {item.product?.name || `상품 #${item.product_id}`} - {item.item_data?.place_name || item.item_data?.상호명 || ''}
              </p>
              <PipelineStatusWidget orderItemId={item.id} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
