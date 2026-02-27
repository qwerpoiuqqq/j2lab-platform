import { useState, useEffect, useCallback } from 'react';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import { assignmentsApi, type AssignmentQueueItem } from '@/api/assignments';

type StatusTab = 'all' | 'auto_assigned' | 'pending';

const STATUS_TABS: { key: StatusTab; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'auto_assigned', label: '자동배정' },
  { key: 'pending', label: '대기중' },
];

function getAssignmentBadgeVariant(status: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    auto_assigned: 'info',
    pending: 'warning',
    confirmed: 'success',
    manual: 'primary',
  };
  return map[status] || 'default';
}

function getAssignmentStatusLabel(status: string): string {
  const map: Record<string, string> = {
    auto_assigned: '자동배정',
    pending: '대기중',
    confirmed: '확인완료',
    manual: '수동배정',
  };
  return map[status] || status;
}

export default function AssignmentQueuePage() {
  const [activeTab, setActiveTab] = useState<StatusTab>('all');
  const [items, setItems] = useState<AssignmentQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [bulkConfirming, setBulkConfirming] = useState(false);

  const fetchQueue = useCallback(async () => {
    try {
      setError(null);
      const params: { assignment_status?: string } = {};
      if (activeTab !== 'all') {
        params.assignment_status = activeTab;
      }
      const response = await assignmentsApi.getQueue(params);
      setItems(response.items);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '배정 대기열을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    setLoading(true);
    setSelectedIds(new Set());
    fetchQueue();
  }, [fetchQueue]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchQueue();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchQueue]);

  const handleConfirm = async (itemId: number) => {
    setConfirmingId(itemId);
    try {
      await assignmentsApi.confirm(itemId);
      await fetchQueue();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '확인 처리에 실패했습니다.');
    } finally {
      setConfirmingId(null);
    }
  };

  const handleBulkConfirm = async () => {
    if (selectedIds.size === 0) return;
    setBulkConfirming(true);
    try {
      await assignmentsApi.bulkConfirm(Array.from(selectedIds));
      setSelectedIds(new Set());
      await fetchQueue();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '벌크 확인 처리에 실패했습니다.');
    } finally {
      setBulkConfirming(false);
    }
  };

  const toggleSelect = (itemId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((item) => item.order_item_id)));
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">배정 대기열</h1>
        <p className="mt-1 text-sm text-gray-500">
          자동 배정된 계정을 확인하고 캠페인 등록을 진행합니다.
        </p>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`
              flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors
              ${
                activeTab === tab.key
                  ? 'bg-primary-600 text-white shadow-sm'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }
            `}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200">
        {loading ? (
          <div className="px-6 py-12 text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
            <p className="mt-2 text-sm text-gray-500">불러오는 중...</p>
          </div>
        ) : error ? (
          <div className="px-6 py-12 text-center">
            <p className="text-sm text-red-600">{error}</p>
            <button
              onClick={fetchQueue}
              className="mt-2 text-sm text-primary-600 hover:underline"
            >
              다시 시도
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-sm text-gray-500">배정 대기열이 비어 있습니다.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === items.length && items.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    주문번호
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    업체명
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    플레이스
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    캠페인유형
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    배정계정
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    상태
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    작업
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {items.map((item) => (
                  <tr key={item.order_item_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.order_item_id)}
                        onChange={() => toggleSelect(item.order_item_id)}
                        className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-primary-600">
                      {item.order_number || `#${item.order_id}`}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {item.company_name || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {item.place_name || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {item.campaign_type || '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {item.assigned_account_name || '-'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={getAssignmentBadgeVariant(item.assignment_status)}>
                        {getAssignmentStatusLabel(item.assignment_status)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {item.assignment_status === 'auto_assigned' && (
                        <Button
                          size="sm"
                          variant="success"
                          onClick={() => handleConfirm(item.order_item_id)}
                          loading={confirmingId === item.order_item_id}
                        >
                          확인
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bulk confirm bar */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg px-6 py-3 flex items-center justify-between z-40">
          <p className="text-sm text-gray-700">
            <span className="font-semibold">{selectedIds.size}</span>건 선택됨
          </p>
          <Button
            variant="success"
            onClick={handleBulkConfirm}
            loading={bulkConfirming}
          >
            선택 항목 벌크 확인
          </Button>
        </div>
      )}
    </div>
  );
}
