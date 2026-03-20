import { useState, useEffect, useCallback } from 'react';
import Button from '@/components/common/Button';
import { ordersApi } from '@/api/orders';
import { formatCurrency, formatRelativeTime } from '@/utils/format';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  BuildingStorefrontIcon,
  UserIcon,
  HashtagIcon,
} from '@heroicons/react/24/outline';

interface SubAccountOrder {
  id: number;
  order_number: string;
  user_id: string;
  user?: { name?: string; role?: string };
  status: string;
  total_amount: number;
  selection_status: string;
  intake_blocked?: boolean;
  intake_block_reason?: string | null;
  created_at: string;
  items?: {
    product?: { name?: string; code?: string };
    item_data?: { place_name?: string; place_url?: string; campaign_type?: string };
  }[];
  item_count?: number;
}

function getCampaignTypeBadge(items?: SubAccountOrder['items']) {
  if (!items || items.length === 0) return null;
  const types = new Set<string>();
  items.forEach((item) => {
    const ct = item.item_data?.campaign_type;
    const pname = item.product?.name || '';
    if (ct === 'traffic' || pname.includes('트래픽')) types.add('traffic');
    else if (ct === 'save' || pname.includes('저장')) types.add('save');
  });
  return Array.from(types);
}

function getPlaceName(items?: SubAccountOrder['items']): string {
  if (!items || items.length === 0) return '-';
  const name = items[0]?.item_data?.place_name;
  return name || '-';
}

function getSelectionBadge(status: string) {
  if (status === 'included') {
    return (
      <span className="inline-flex items-center gap-1 bg-green-900/40 text-green-400 px-2 py-0.5 rounded text-[11px] font-medium">
        <CheckCircleIcon className="h-3 w-3" />
        포함됨
      </span>
    );
  }
  if (status === 'excluded') {
    return (
      <span className="inline-flex items-center gap-1 bg-red-900/40 text-red-400 px-2 py-0.5 rounded text-[11px] font-medium">
        <XCircleIcon className="h-3 w-3" />
        제외됨
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 bg-yellow-900/40 text-yellow-400 px-2 py-0.5 rounded text-[11px] font-medium">
      <ClockIcon className="h-3 w-3" />
      대기중
    </span>
  );
}

export default function SubAccountOrders() {
  const [orders, setOrders] = useState<SubAccountOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [processing, setProcessing] = useState<number | null>(null);
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const [submitResults, setSubmitResults] = useState<{ success: number; failed: number } | null>(null);

  const fetchOrders = useCallback(async () => {
    try {
      setError(null);
      const response = await ordersApi.getSubAccountPending();
      setOrders(response.items as SubAccountOrder[]);
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

  // Bulk confirm: submit (if draft) then confirmPayment — pipeline starts immediately
  const handleBulkSubmit = async () => {
    const toProcess = orders.filter(
      (o) =>
        selectedIds.has(o.id)
        && o.selection_status === 'included'
        && !o.intake_blocked
        && (o.status === 'draft' || o.status === 'submitted' || o.status === 'payment_hold')
    );
    if (toProcess.length === 0) {
      alert('접수할 수 있는 건이 없습니다. 접수건을 선택해 주세요.');
      return;
    }
    setBulkSubmitting(true);
    setSubmitResults(null);
    let success = 0;
    let failed = 0;
    for (const order of toProcess) {
      try {
        // Step 1: submit if still draft
        if (order.status === 'draft') {
          await ordersApi.submit(order.id);
        }
        // Step 2: confirm payment → pipeline starts immediately
        await ordersApi.confirmPayment(order.id);
        success++;
      } catch {
        failed++;
      }
    }
    setSubmitResults({ success, failed });
    setSelectedIds(new Set());
    await fetchOrders();
    setBulkSubmitting(false);
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
        <div className="animate-pulse h-32 rounded-lg bg-surface-raised" />
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
    return null;
  }

  const pendingCount = orders.filter((o) => o.selection_status === 'pending' || !o.selection_status).length;
  const includedCount = orders.filter((o) => o.selection_status === 'included').length;

  return (
    <div className="bg-surface rounded-xl border border-border shadow-sm">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-gray-100">대기 접수건</h3>
              <span className="inline-flex items-center bg-cyan-900/40 text-cyan-400 text-xs font-medium px-2 py-0.5 rounded-full">
                {orders.length}건
              </span>
              {pendingCount > 0 && (
                <span className="inline-flex items-center bg-yellow-900/40 text-yellow-400 text-xs font-medium px-2 py-0.5 rounded-full">
                  대기 {pendingCount}
                </span>
              )}
              {includedCount > 0 && (
                <span className="inline-flex items-center bg-green-900/40 text-green-400 text-xs font-medium px-2 py-0.5 rounded-full">
                  포함 {includedCount}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              하부계정 최종 접수 건입니다. 포함 처리 후 총판 단계에서 최종 접수를 넘기면 세팅이 시작됩니다.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {selectedIds.size > 0 && (
              <>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleBulkInclude}
                  loading={processing === -1}
                >
                  {selectedIds.size}건 포함
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={handleBulkSubmit}
                  loading={bulkSubmitting}
                >
                  {selectedIds.size}건 총판 최종 접수
                </Button>
              </>
            )}
          </div>
        </div>
        {submitResults && (
          <div className={`mt-3 text-xs rounded-lg px-3 py-2 flex items-center gap-2 ${
            submitResults.failed > 0
              ? 'bg-yellow-900/30 text-yellow-400 border border-yellow-800/50'
              : 'bg-green-900/30 text-green-400 border border-green-800/50'
          }`}>
            <CheckCircleIcon className="h-4 w-4 flex-shrink-0" />
            <span>
              총판 최종 접수 완료: 성공 {submitResults.success}건
              {submitResults.failed > 0 && ` / 실패 ${submitResults.failed}건`}
            </span>
            <button
              className="ml-auto text-gray-400 hover:text-gray-200"
              onClick={() => setSubmitResults(null)}
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Select all bar */}
      <div className="px-5 py-2.5 border-b border-border bg-surface-raised flex items-center gap-3">
        <input
          type="checkbox"
          checked={selectedIds.size === orders.length && orders.length > 0}
          onChange={toggleAll}
          className="rounded border-border-strong text-primary-600 focus:ring-primary-400/40"
        />
        <span className="text-xs text-gray-400">
          {selectedIds.size > 0 ? `${selectedIds.size}건 선택됨` : '전체 선택'}
        </span>
      </div>

      {/* Card grid */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {orders.map((order) => {
          const placeName = getPlaceName(order.items);
          const campaignTypes = getCampaignTypeBadge(order.items);
          const isSelected = selectedIds.has(order.id);
          const isProcessing = processing === order.id;

          return (
            <div
              key={order.id}
              className={`relative rounded-lg border p-4 cursor-pointer transition-colors ${
                isSelected
                  ? 'border-primary-500/70 bg-primary-900/10'
                  : 'border-border hover:border-border-strong hover:bg-surface-raised'
              }`}
              onClick={() => toggleSelect(order.id)}
            >
              {/* Checkbox */}
              <div className="absolute top-3 right-3">
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => toggleSelect(order.id)}
                  onClick={(e) => e.stopPropagation()}
                  className="rounded border-border-strong text-primary-600 focus:ring-primary-400/40"
                />
              </div>

              {/* Order number + selection status */}
              <div className="flex items-center gap-2 mb-2.5 pr-6">
                <span className="inline-block bg-surface-raised px-2 py-0.5 rounded text-xs font-mono text-gray-100">
                  <HashtagIcon className="h-3 w-3 inline mr-0.5 opacity-60" />
                  {order.order_number}
                </span>
                {getSelectionBadge(order.selection_status)}
                {order.intake_blocked && (
                  <span className="inline-flex items-center gap-1 bg-red-900/40 text-red-400 px-2 py-0.5 rounded text-[11px] font-medium">
                    <XCircleIcon className="h-3 w-3" />
                    접수 불가
                  </span>
                )}
              </div>

              {/* Place name */}
              <div className="flex items-start gap-1.5 mb-1.5">
                <BuildingStorefrontIcon className="h-3.5 w-3.5 text-gray-400 flex-shrink-0 mt-0.5" />
                <span className="text-sm font-medium text-gray-100 leading-tight">{placeName}</span>
              </div>

              {/* Orderer name */}
              <div className="flex items-center gap-1.5 mb-2.5">
                <UserIcon className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
                <span className="text-xs text-gray-300">
                  {order.user?.name || order.user_id || '-'}
                </span>
                {order.user?.role === 'sub_account' && (
                  <span className="inline-block bg-violet-900/40 text-violet-400 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none">
                    하부
                  </span>
                )}
              </div>

              {/* Campaign type badges + amount */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 flex-wrap">
                  {campaignTypes && campaignTypes.length > 0 ? (
                    campaignTypes.map((ct) => (
                      <span
                        key={ct}
                        className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${
                          ct === 'traffic'
                            ? 'bg-blue-900/40 text-blue-400'
                            : 'bg-emerald-900/40 text-emerald-400'
                        }`}
                      >
                        {ct === 'traffic' ? '트래픽' : '저장하기'}
                      </span>
                    ))
                  ) : (
                    <span className="text-[11px] text-gray-500">
                      {order.item_count || order.items?.length || 0}건
                    </span>
                  )}
                </div>
                <span className="text-sm font-medium text-gray-100 tabular-nums">
                  {formatCurrency(order.total_amount)}
                </span>
              </div>

              {/* Date + action buttons */}
              <div className="mt-3 pt-2.5 border-t border-border flex items-center justify-between">
                <div className="min-w-0">
                  <span className="text-[11px] text-gray-500">
                    {formatRelativeTime(order.created_at)}
                  </span>
                  {order.intake_blocked && order.intake_block_reason && (
                    <p className="mt-1 text-[11px] text-red-400 truncate max-w-[220px]">
                      {order.intake_block_reason}
                    </p>
                  )}
                </div>
                <div className="flex gap-1.5" onClick={(e) => e.stopPropagation()}>
                  <button
                    className="px-2.5 py-1 rounded text-xs font-medium bg-green-900/40 text-green-400 hover:bg-green-900/60 transition-colors disabled:opacity-50"
                    onClick={() => handleInclude(order.id)}
                    disabled={isProcessing || order.selection_status === 'included' || order.intake_blocked}
                  >
                    {isProcessing ? '처리중...' : '포함'}
                  </button>
                  <button
                    className="px-2.5 py-1 rounded text-xs font-medium bg-red-900/40 text-red-400 hover:bg-red-900/60 transition-colors disabled:opacity-50"
                    onClick={() => handleExclude(order.id)}
                    disabled={isProcessing || order.selection_status === 'excluded' || order.intake_blocked}
                  >
                    제외
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
