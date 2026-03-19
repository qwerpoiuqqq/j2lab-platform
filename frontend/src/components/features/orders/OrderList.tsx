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
import { useAuthStore } from '@/store/auth';

// Unified status for dashboard / external consumers
const unifiedStatusMap: Record<string, { color: string; dotColor: string; label: string }> = {
  draft:             { color: 'bg-surface-raised text-gray-500 ring-gray-500/20',    dotColor: 'bg-gray-500',    label: '임시저장' },
  submitted:         { color: 'bg-blue-900/40 text-blue-400 ring-blue-400/20',       dotColor: 'bg-blue-400',    label: '접수완료' },
  payment_confirmed: { color: 'bg-amber-900/40 text-amber-400 ring-amber-400/20',    dotColor: 'bg-amber-400',   label: '입금확인' },
  payment_hold:      { color: 'bg-amber-900/40 text-amber-400 ring-amber-400/20',    dotColor: 'bg-amber-400',   label: '보류' },
  processing:        { color: 'bg-amber-900/40 text-amber-400 ring-amber-400/20',    dotColor: 'bg-amber-400',   label: '처리중' },
  completed:         { color: 'bg-emerald-900/40 text-emerald-400 ring-emerald-400/20', dotColor: 'bg-emerald-400', label: '완료' },
  cancelled:         { color: 'bg-red-900/40 text-red-400 ring-red-400/20',          dotColor: 'bg-red-400',     label: '취소' },
  rejected:          { color: 'bg-red-900/40 text-red-400 ring-red-400/20',          dotColor: 'bg-red-400',     label: '반려' },
};

export function getUnifiedStatus(order: Order) {
  return unifiedStatusMap[order.status] || unifiedStatusMap.draft;
}

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
    payment_hold: 'warning',
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

function getOrderTypeLabel(orderType?: string): string {
  const map: Record<string, string> = {
    regular: '일반',
    monthly_guarantee: '월보장',
    managed: '관리형',
  };
  return map[orderType || 'regular'] || orderType || '일반';
}

function getOrderTypeBadgeClass(orderType?: string): string {
  const map: Record<string, string> = {
    regular: 'bg-surface-raised text-gray-400',
    monthly_guarantee: 'bg-blue-900/30 text-blue-400',
    managed: 'bg-purple-900/30 text-purple-400',
  };
  return map[orderType || 'regular'] || 'bg-surface-raised text-gray-400';
}

export default function OrderList({ orders, loading, selectable, selectedIds, onToggleSelect }: OrderListProps) {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const canViewPrices = user?.role !== 'sub_account';

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
                className="rounded border-border-strong text-primary-600 focus:ring-primary-400/40"
              />
            ),
          },
        ]
      : []),
    {
      key: 'order_number',
      header: '주문번호',
      render: (order) => (
        <span className="inline-block bg-surface-raised px-2 py-0.5 rounded text-xs font-mono text-gray-100">
          {order.order_number}
        </span>
      ),
    },
    {
      key: 'user',
      header: '주문자',
      render: (order) => (
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-gray-100 font-medium">{order.user?.name || order.user_id || '-'}</span>
            {order.user?.role === 'sub_account' && (
              <span className="inline-block bg-violet-900/40 text-violet-400 px-1.5 py-0.5 rounded text-[10px] leading-none font-medium">
                하부
              </span>
            )}
            {order.user?.role && order.user.role !== 'sub_account' && (
              <span className="inline-block bg-surface-raised text-gray-400 px-1.5 py-0.5 rounded text-[10px] leading-none font-medium">
                {getRoleLabel(order.user.role)}
              </span>
            )}
          </div>
          {order.company?.name && (
            <span className="inline-flex items-center bg-blue-900/30 text-blue-400 px-1.5 py-0.5 rounded text-[11px] leading-none w-fit">
              {order.company.name}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'item_count',
      header: '플레이스 / 상품',
      render: (order) => {
        const count = order.item_count || order.items?.length || 0;
        // Extract place name from first item's item_data
        const placeName = order.items?.[0]?.item_data?.place_name as string | undefined;
        // Derive campaign type badges
        const types = new Set<string>();
        order.items?.forEach((item) => {
          const ct = (item.item_data as any)?.campaign_type as string | undefined;
          const pname = item.product?.name || '';
          if (ct === 'traffic' || pname.includes('트래픽')) types.add('traffic');
          else if (ct === 'save' || pname.includes('저장')) types.add('save');
        });
        const productNames = order.items
          ?.map((item) => item.product?.name)
          .filter(Boolean);
        const uniqueNames = productNames ? [...new Set(productNames)] : [];
        return (
          <div className="flex flex-col gap-0.5">
            {placeName ? (
              <span className="text-gray-100 font-medium text-sm truncate max-w-[160px]">
                {placeName}
              </span>
            ) : (
              <span className="text-gray-100 font-medium">{count}건</span>
            )}
            <div className="flex items-center gap-1 flex-wrap">
              {types.has('traffic') && (
                <span className="inline-block bg-blue-900/40 text-blue-400 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none">
                  트래픽
                </span>
              )}
              {types.has('save') && (
                <span className="inline-block bg-emerald-900/40 text-emerald-400 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none">
                  저장
                </span>
              )}
              {types.size === 0 && uniqueNames.length > 0 && (
                <p className="text-[11px] text-gray-400 truncate max-w-[140px]">
                  {uniqueNames.join(', ')}
                </p>
              )}
            </div>
          </div>
        );
      },
    },
    ...(canViewPrices
      ? [
          {
            key: 'total_amount' as keyof Order,
            header: '금액',
            render: (order: Order) => (
              <div className="text-right">
                <span className="font-medium text-gray-100 tabular-nums">
                  {formatCurrency(order.total_amount)}
                </span>
              </div>
            ),
          },
        ]
      : []),
    {
      key: 'order_type',
      header: '유형',
      render: (order) => {
        if (!order.order_type || order.order_type === 'regular') return null;
        return (
          <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${getOrderTypeBadgeClass(order.order_type)}`}>
            {getOrderTypeLabel(order.order_type)}
          </span>
        );
      },
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
          <p className="text-gray-300 text-xs">
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
