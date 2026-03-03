import { useNavigate } from 'react-router-dom';
import type { Order } from '@/types';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import {
  formatCurrency,
  formatDateTime,
  formatRelativeTime,
  getOrderStatusLabel,
  getRoleLabel,
} from '@/utils/format';

interface OrderListProps {
  orders: Order[];
  loading?: boolean;
  selectable?: boolean;
  selectedIds?: Set<number>;
  onToggleSelect?: (id: number) => void;
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

function getStatusIcon(status: string): string {
  const icons: Record<string, string> = {
    completed: '\u2713',
    payment_confirmed: '\u2713',
    processing: '\u23F3',
    submitted: '\u25CB',
    draft: '\u25CB',
    pending: '\u25CB',
    cancelled: '\u2715',
    rejected: '\u2715',
  };
  return icons[status] || '';
}

export default function OrderList({ orders, loading, selectable, selectedIds, onToggleSelect }: OrderListProps) {
  const navigate = useNavigate();

  const columns: Column<Order>[] = [
    ...(selectable
      ? [
          {
            key: 'checkbox' as keyof Order,
            header: '',
            render: (order: Order) => (
              <input
                type="checkbox"
                checked={selectedIds?.has(order.id) || false}
                onChange={(e) => {
                  e.stopPropagation();
                  onToggleSelect?.(order.id);
                }}
                onClick={(e) => e.stopPropagation()}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
            ),
          },
        ]
      : []),
    {
      key: 'order_number',
      header: '주문번호',
      render: (order) => (
        <span className="inline-block bg-gray-100 px-2 py-0.5 rounded text-xs font-mono text-gray-900">
          {order.order_number}
        </span>
      ),
    },
    {
      key: 'user',
      header: '주문자',
      render: (order) => (
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5">
            <span className="text-gray-900 font-medium">{order.user?.name || order.user_id || '-'}</span>
            {order.user?.role && (
              <span className="inline-block bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded text-[10px] leading-none font-medium">
                {getRoleLabel(order.user.role)}
              </span>
            )}
          </div>
          {order.company?.name && (
            <span className="inline-flex items-center bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded text-[11px] leading-none w-fit">
              {order.company.name}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'item_count',
      header: '항목수',
      render: (order) => {
        const count = order.item_count || order.items?.length || 0;
        const productNames = order.items
          ?.map((item) => item.product?.name)
          .filter(Boolean);
        const uniqueNames = productNames ? [...new Set(productNames)] : [];
        return (
          <div>
            <span className="text-gray-900 font-medium">{count}건</span>
            {uniqueNames.length > 0 && (
              <p className="text-[11px] text-gray-400 mt-0.5 truncate max-w-[120px]">
                {uniqueNames.join(', ')}
              </p>
            )}
          </div>
        );
      },
    },
    {
      key: 'total_amount',
      header: '금액',
      render: (order) => (
        <div className="text-right">
          <span className="font-medium text-gray-900 tabular-nums">
            {formatCurrency(order.total_amount)}
          </span>
        </div>
      ),
    },
    {
      key: 'status',
      header: '상태',
      render: (order) => (
        <Badge variant={getStatusBadgeVariant(order.status)}>
          <span className="mr-1">{getStatusIcon(order.status)}</span>
          {getOrderStatusLabel(order.status)}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: '접수일시',
      render: (order) => (
        <div>
          <p className="text-gray-700 text-xs">
            {formatDateTime(order.created_at)}
          </p>
          <p className="text-[11px] text-gray-400 mt-0.5">
            {formatRelativeTime(order.created_at)}
          </p>
        </div>
      ),
    },
  ];

  return (
    <Table<Order>
      columns={columns}
      data={orders}
      keyExtractor={(order) => order.id}
      onRowClick={(order) => navigate(`/orders/${order.id}`)}
      loading={loading}
      emptyMessage="주문이 없습니다."
    />
  );
}
