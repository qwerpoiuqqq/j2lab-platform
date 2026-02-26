import { useState, useEffect } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import Pagination from '@/components/common/Pagination';
import {
  ArrowDownTrayIcon,
  CalendarIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline';
import {
  formatCurrency,
  formatDate,
  formatNumber,
  getSettlementStatusLabel,
  getSettlementStatusColor,
  downloadBlob,
} from '@/utils/format';
import { settlementsApi } from '@/api/settlements';
import type { Settlement, SettlementSummary } from '@/types';

const statusOptions = [
  { value: '', label: '전체 상태' },
  { value: 'pending', label: '대기' },
  { value: 'confirmed', label: '확인' },
  { value: 'settled', label: '정산완료' },
];

export default function SettlementPage() {
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [summary, setSummary] = useState<SettlementSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    settlementsApi
      .list({
        page,
        size: 20,
        status: statusFilter || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      .then((data) => {
        if (!cancelled) {
          setSettlements(data.items);
          setSummary(data.summary);
          setTotalPages(data.pages);
          setTotalItems(data.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '정산 목록을 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [page, statusFilter, startDate, endDate]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await settlementsApi.export({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      downloadBlob(blob, `정산내역_${new Date().toISOString().split('T')[0]}.xlsx`);
    } catch {
      alert('내보내기에 실패했습니다.');
    } finally {
      setExporting(false);
    }
  };

  const columns: Column<Settlement>[] = [
    {
      key: 'order_number',
      header: '주문번호',
      render: (s) => <span className="font-mono text-sm">{s.order_number}</span>,
    },
    {
      key: 'product_name',
      header: '상품명',
      render: (s) => <span className="text-gray-900">{s.product_name}</span>,
    },
    {
      key: 'user_name',
      header: '주문자',
      render: (s) => <span className="text-gray-700">{s.user_name}</span>,
    },
    {
      key: 'amount',
      header: '금액',
      render: (s) => <span className="font-medium">{formatCurrency(s.amount)}</span>,
    },
    {
      key: 'commission',
      header: '수수료',
      render: (s) => <span className="text-gray-600">{formatCurrency(s.commission)}</span>,
    },
    {
      key: 'settlement_amount',
      header: '정산액',
      render: (s) => <span className="font-medium text-primary-600">{formatCurrency(s.settlement_amount)}</span>,
    },
    {
      key: 'status',
      header: '상태',
      render: (s) => (
        <Badge className={getSettlementStatusColor(s.status)}>
          {getSettlementStatusLabel(s.status)}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: '일자',
      render: (s) => <span className="text-gray-500 text-xs">{formatDate(s.created_at)}</span>,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">정산 관리</h1>
          <p className="mt-1 text-sm text-gray-500">주문별 정산 현황을 관리합니다.</p>
        </div>
        <Button
          variant="secondary"
          onClick={handleExport}
          loading={exporting}
          icon={<ArrowDownTrayIcon className="h-4 w-4" />}
        >
          Excel 내보내기
        </Button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <SummaryCard label="총 정산액" value={formatCurrency(summary.total_amount)} color="blue" />
          <SummaryCard label="미정산" value={formatCurrency(summary.pending_amount)} color="yellow" />
          <SummaryCard label="정산완료" value={formatCurrency(summary.settled_amount)} color="green" />
          <SummaryCard label="진행중" value={`${formatNumber(summary.processing_count)}건`} color="purple" />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 items-end">
        <div className="flex items-center gap-2">
          <CalendarIcon className="h-4 w-4 text-gray-400" />
          <input
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); setPage(1); }}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <span className="text-gray-400">~</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); setPage(1); }}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <FunnelIcon className="h-4 w-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {statusOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      {/* Table */}
      <Table<Settlement>
        columns={columns}
        data={settlements}
        keyExtractor={(s) => s.id}
        loading={loading}
        emptyMessage="정산 내역이 없습니다."
      />

      {/* Pagination */}
      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalItems={totalItems}
        pageSize={20}
      />
    </div>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: string; color: string }) {
  const borderColors: Record<string, string> = {
    blue: 'border-l-blue-500',
    yellow: 'border-l-yellow-500',
    green: 'border-l-green-500',
    purple: 'border-l-purple-500',
  };

  return (
    <div className={`bg-white rounded-xl border border-gray-200 shadow-sm p-4 border-l-4 ${borderColors[color] || 'border-l-gray-500'}`}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-xl font-bold text-gray-900 mt-1">{value}</p>
    </div>
  );
}
