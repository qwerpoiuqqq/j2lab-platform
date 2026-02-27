import type { Order, OrderItem } from '@/types';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import {
  formatCurrency,
  formatDateTime,
  getOrderStatusLabel,
} from '@/utils/format';
import { useAuthStore } from '@/store/auth';

interface OrderDetailProps {
  order: Order;
  items: OrderItem[];
  onSubmit?: () => void;
  onConfirmPayment?: () => void;
  onReject?: () => void;
  onCancel?: () => void;
  actionLoading?: boolean;
}

function getStatusBadgeVariant(status: string) {
  const map: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    draft: 'default',
    submitted: 'info',
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
  actionLoading,
}: OrderDetailProps) {
  const user = useAuthStore((s) => s.user);
  const userRole = user?.role;

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
            {order.status === 'draft' && ['distributor', 'sub_account'].includes(userRole || '') && (
              <Button
                variant="primary"
                onClick={onSubmit}
                loading={actionLoading}
              >
                접수 제출
              </Button>
            )}
            {order.status === 'submitted' && ['system_admin', 'company_admin'].includes(userRole || '') && (
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
                  onClick={onReject}
                  loading={actionLoading}
                >
                  반려
                </Button>
              </>
            )}
            {['draft', 'submitted'].includes(order.status) &&
              ['system_admin', 'company_admin'].includes(userRole || '') && (
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
                items.map((item) => (
                  <tr key={item.id}>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {item.product?.name || `상품 #${item.product_id}`}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <div>
                        <p className="text-gray-900">
                          {item.item_data?.place_name || '-'}
                        </p>
                        <p className="text-xs text-gray-500 truncate max-w-[200px]">
                          {item.item_data?.place_url || '-'}
                        </p>
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
                      <Badge>{item.status}</Badge>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
