import { useState, useEffect, useCallback } from 'react';
import Button from '@/components/common/Button';
import Badge from '@/components/common/Badge';
import { ordersApi } from '@/api/orders';
import { formatCurrency, formatDate } from '@/utils/format';

interface SubAccountOrder {
  id: number;
  order_number: string;
  user_id: string;
  status: string;
  total_amount: number;
  selection_status: string;
  created_at: string;
}

export default function SubAccountOrders() {
  const [orders, setOrders] = useState<SubAccountOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [processing, setProcessing] = useState<number | null>(null);

  const fetchOrders = useCallback(async () => {
    try {
      setError(null);
      const response = await ordersApi.getSubAccountPending();
      setOrders(response.items);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '하부계정 접수건을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleInclude = async (orderId: number) => {
    setProcessing(orderId);
    try {
      await ordersApi.includeOrder(orderId);
      await fetchOrders();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '포함 처리에 실패했습니다.');
    } finally {
      setProcessing(null);
    }
  };

  const handleExclude = async (orderId: number) => {
    setProcessing(orderId);
    try {
      await ordersApi.excludeOrder(orderId);
      await fetchOrders();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '제외 처리에 실패했습니다.');
    } finally {
      setProcessing(null);
    }
  };

  const handleBulkInclude = async () => {
    if (selectedIds.size === 0) return;
    setProcessing(-1);
    try {
      await ordersApi.bulkInclude(Array.from(selectedIds));
      setSelectedIds(new Set());
      await fetchOrders();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '일괄 포함 처리에 실패했습니다.');
    } finally {
      setProcessing(null);
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === orders.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(orders.map((o) => o.id)));
    }
  };

  if (loading) {
    return (
      <div className="bg-surface rounded-xl border border-border p-6">
        <div className="animate-pulse h-32" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4 text-sm text-red-400">
        {error}
      </div>
    );
  }

  if (orders.length === 0) {
    return null; // Don't show the section if no pending orders
  }

  return (
    <div className="bg-surface rounded-xl border border-border shadow-sm">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-100">하부계정 접수건</h3>
          <p className="text-sm text-gray-400 mt-0.5">대기 중인 접수건을 포함/제외하세요.</p>
        </div>
        {selectedIds.size > 0 && (
          <Button
            size="sm"
            variant="primary"
            onClick={handleBulkInclude}
            loading={processing === -1}
          >
            {selectedIds.size}건 일괄 포함
          </Button>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-surface-raised">
            <tr>
              <th className="px-4 py-3 text-left">
                <input
                  type="checkbox"
                  checked={selectedIds.size === orders.length && orders.length > 0}
                  onChange={toggleAll}
                  className="rounded border-border-strong text-primary-600"
                />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">주문번호</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">상태</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">금액</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">접수일</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">작업</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {orders.map((order) => (
              <tr key={order.id} className="hover:bg-surface-raised">
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(order.id)}
                    onChange={() => toggleSelect(order.id)}
                    className="rounded border-border-strong text-primary-600"
                  />
                </td>
                <td className="px-4 py-3 text-sm font-medium text-primary-600">
                  {order.order_number}
                </td>
                <td className="px-4 py-3">
                  <Badge variant="warning">{order.status}</Badge>
                </td>
                <td className="px-4 py-3 text-sm text-gray-300">
                  {formatCurrency(order.total_amount)}
                </td>
                <td className="px-4 py-3 text-sm text-gray-400">
                  {order.created_at ? formatDate(order.created_at) : '-'}
                </td>
                <td className="px-4 py-3 flex gap-2">
                  <Button
                    size="sm"
                    variant="success"
                    onClick={() => handleInclude(order.id)}
                    loading={processing === order.id}
                  >
                    포함
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => handleExclude(order.id)}
                    loading={processing === order.id}
                  >
                    제외
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
