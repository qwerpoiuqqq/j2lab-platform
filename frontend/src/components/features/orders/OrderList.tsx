import { useNavigate } from 'react-router-dom';
import type { Order } from '@/types';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import {
  formatCurrency,
  formatDateTime,
  getOrderStatusLabel,
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
        <span className="font-medium text-gray-900">{order.order_number}</span>
      ),
    },
    {
      key: 'user',
      header: '주문자',
      render: (order) => (
        <div>
          <p className="text-gray-900">{order.user?.name || order.user_id || '-'}</p>
          <p className="text-xs text-gray-500">{order.company?.name || ''}</p>
        </div>
      ),
    },
    {
      key: 'item_count',
      header: '항목수',
      render: (order) => (
        <span className="text-gray-600">{order.item_count || order.items?.length || 0}건</span>
      ),
    },
    {
      key: 'total_amount',
      header: '금액',
      render: (order) => (
        <span className="font-medium text-gray-900">
          {formatCurrency(order.total_amount)}
        </span>
      ),
    },
    {
      key: 'status',
      header: '상태',
      render: (order) => (
        <Badge variant={getStatusBadgeVariant(order.status)}>
          {getOrderStatusLabel(order.status)}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: '접수일시',
      render: (order) => (
        <span className="text-gray-500 text-xs">
          {formatDateTime(order.created_at)}
        </span>
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
