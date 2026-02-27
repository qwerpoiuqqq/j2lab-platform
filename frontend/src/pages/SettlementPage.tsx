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
  getRoleLabel,
  downloadBlob,
} from '@/utils/format';
import { settlementsApi } from '@/api/settlements';
import type { Settlement, SettlementSummary } from '@/types';

export default function SettlementPage() {
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [summary, setSummary] = useState<SettlementSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
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
  }, [page, startDate, endDate]);

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
      render: (s) => (
        <div>
          <span className="text-gray-700">{s.user_name}</span>
          <span className="ml-1 text-xs text-gray-400">({getRoleLabel(s.user_role)})</span>
        </div>
      ),
    },
    {
      key: 'quantity',
      header: '수량',
      render: (s) => <span className="text-gray-700">{formatNumber(s.quantity)}</span>,
    },
    {
      key: 'subtotal',
      header: '매출',
      render: (s) => <span className="font-medium">{formatCurrency(s.subtotal)}</span>,
    },
    {
      key: 'cost',
      header: '매입',
      render: (s) => <span className="text-gray-600">{formatCurrency(s.cost)}</span>,
    },
    {
      key: 'profit',
      header: '이익',
      render: (s) => (
        <span className={`font-medium ${s.profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {formatCurrency(s.profit)}
        </span>
      ),
    },
    {
      key: 'margin_pct',
      header: '마진율',
      render: (s) => (
        <Badge className={s.margin_pct >= 20 ? 'bg-green-100 text-green-800' : s.margin_pct >= 10 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}>
          {s.margin_pct.toFixed(1)}%
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
          <p className="mt-1 text-sm text-gray-500">주문별 수익/비용 현황을 관리합니다.</p>
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
          <SummaryCard label="총 매출" value={formatCurrency(summary.total_revenue)} color="blue" />
          <SummaryCard label="총 매입" value={formatCurrency(summary.total_cost)} color="yellow" />
          <SummaryCard
            label="총 이익"
            value={formatCurrency(summary.total_profit)}
            color={summary.total_profit >= 0 ? 'green' : 'red'}
          />
          <SummaryCard
            label="평균 마진율"
            value={`${summary.avg_margin_pct.toFixed(1)}%`}
            subtitle={`주문 ${formatNumber(summary.order_count)}건 / 아이템 ${formatNumber(summary.item_count)}건`}
            color="purple"
          />
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
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      {/* Table */}
      <Table<Settlement>
        columns={columns}
        data={settlements}
        keyExtractor={(s) => `${s.order_id}-${s.order_number}`}
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

function SummaryCard({ label, value, color, subtitle }: { label: string; value: string; color: string; subtitle?: string }) {
  const borderColors: Record<string, string> = {
    blue: 'border-l-blue-500',
    yellow: 'border-l-yellow-500',
    green: 'border-l-green-500',
    red: 'border-l-red-500',
    purple: 'border-l-purple-500',
  };

  return (
    <div className={`bg-white rounded-xl border border-gray-200 shadow-sm p-4 border-l-4 ${borderColors[color] || 'border-l-gray-500'}`}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-xl font-bold text-gray-900 mt-1">{value}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
    </div>
  );
}
