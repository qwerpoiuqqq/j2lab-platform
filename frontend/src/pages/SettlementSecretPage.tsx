import { useState } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Button from '@/components/common/Button';
import Input from '@/components/common/Input';
import {
  ArrowDownTrayIcon,
  LockClosedIcon,
  CalendarIcon,
} from '@heroicons/react/24/outline';
import { formatCurrency, formatNumber, getRoleLabel, downloadBlob } from '@/utils/format';
import { settlementsApi } from '@/api/settlements';
import type { SettlementSecretItem, SettlementSummary } from '@/types';

export default function SettlementSecretPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  const [data, setData] = useState<SettlementSecretItem[]>([]);
  const [summary, setSummary] = useState<SettlementSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const handleAuth = async () => {
    setAuthLoading(true);
    setAuthError('');
    try {
      const result = await settlementsApi.getSecret({ password });
      setData(result.items);
      setSummary(result.summary);
      setIsAuthenticated(true);
    } catch (err: any) {
      setAuthError(err?.response?.data?.detail || '비밀번호가 올바르지 않습니다.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await settlementsApi.getSecret({
        password,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      setData(result.items);
      setSummary(result.summary);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '데이터를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const blob = await settlementsApi.export({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      downloadBlob(blob, `수익분석_${new Date().toISOString().split('T')[0]}.xlsx`);
    } catch {
      alert('내보내기에 실패했습니다.');
    }
  };

  const totalRevenue = data.reduce((sum, item) => sum + item.subtotal, 0);
  const totalCost = data.reduce((sum, item) => sum + item.cost, 0);
  const totalProfit = data.reduce((sum, item) => sum + item.profit, 0);
  const avgMargin = data.length > 0
    ? data.reduce((sum, item) => sum + item.margin_pct, 0) / data.length
    : 0;

  const columns: Column<SettlementSecretItem>[] = [
    { key: 'order_number', header: '주문번호', render: (s) => <span className="font-mono text-xs">{s.order_number}</span> },
    { key: 'product_name', header: '상품', render: (s) => <span className="text-sm">{s.product_name}</span> },
    { key: 'user_name', header: '주문자', render: (s) => <span className="text-sm">{s.user_name}</span> },
    { key: 'user_role', header: '역할', render: (s) => <span className="text-xs text-gray-400">{getRoleLabel(s.user_role)}</span> },
    { key: 'quantity', header: '수량', render: (s) => <span className="text-sm">{formatNumber(s.quantity)}</span> },
    { key: 'unit_price', header: '판매단가', render: (s) => <span className="text-sm">{formatCurrency(s.unit_price)}</span> },
    { key: 'base_price', header: '매입단가', render: (s) => <span className="text-sm">{formatCurrency(s.base_price)}</span> },
    { key: 'subtotal', header: '매출', render: (s) => <span className="text-sm font-medium">{formatCurrency(s.subtotal)}</span> },
    { key: 'cost', header: '매입', render: (s) => <span className="text-sm">{formatCurrency(s.cost)}</span> },
    {
      key: 'profit',
      header: '이익',
      render: (s) => (
        <span className={`text-sm font-medium ${s.profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {formatCurrency(s.profit)}
        </span>
      ),
    },
    {
      key: 'margin_pct',
      header: '마진율',
      render: (s) => (
        <span className={`text-sm font-medium ${s.margin_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {s.margin_pct.toFixed(1)}%
        </span>
      ),
    },
  ];

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="bg-surface rounded-xl border border-border shadow-sm p-8 w-full max-w-md">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-red-900/30 rounded-lg flex items-center justify-center">
              <LockClosedIcon className="h-5 w-5 text-red-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-100">수익 분석 (비공개)</h2>
              <p className="text-sm text-gray-400">접근 비밀번호를 입력하세요.</p>
            </div>
          </div>

          <div className="space-y-4">
            <Input
              type="password"
              placeholder="비밀번호"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={authError}
              onKeyDown={(e) => { if (e.key === 'Enter') handleAuth(); }}
            />

            <Button onClick={handleAuth} loading={authLoading} className="w-full">
              확인
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">수익 분석 (비공개)</h1>
          <p className="mt-1 text-sm text-gray-400">상세 수익/비용 분석 데이터입니다.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleExport} icon={<ArrowDownTrayIcon className="h-4 w-4" />}>
            Excel
          </Button>
          <Button variant="ghost" onClick={() => setIsAuthenticated(false)} icon={<LockClosedIcon className="h-4 w-4" />}>
            잠금
          </Button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface rounded-xl border border-border shadow-sm p-4 border-l-4 border-l-blue-500">
          <p className="text-sm text-gray-400">총 매출</p>
          <p className="text-xl font-bold text-gray-100 mt-1">{formatCurrency(totalRevenue)}</p>
        </div>
        <div className="bg-surface rounded-xl border border-border shadow-sm p-4 border-l-4 border-l-red-500">
          <p className="text-sm text-gray-400">총 매입</p>
          <p className="text-xl font-bold text-gray-100 mt-1">{formatCurrency(totalCost)}</p>
        </div>
        <div className="bg-surface rounded-xl border border-border shadow-sm p-4 border-l-4 border-l-green-500">
          <p className="text-sm text-gray-400">순이익</p>
          <p className={`text-xl font-bold mt-1 ${totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatCurrency(totalProfit)}
          </p>
        </div>
        <div className="bg-surface rounded-xl border border-border shadow-sm p-4 border-l-4 border-l-purple-500">
          <p className="text-sm text-gray-400">평균 마진율</p>
          <p className={`text-xl font-bold mt-1 ${avgMargin >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {avgMargin.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Server-side summary (if available) */}
      {summary && (
        <div className="text-xs text-gray-400">
          서버 집계: 주문 {formatNumber(summary.order_count)}건 / 아이템 {formatNumber(summary.item_count)}건 /
          총매출 {formatCurrency(summary.total_revenue)} / 총이익 {formatCurrency(summary.total_profit)} / 마진 {summary.avg_margin_pct.toFixed(1)}%
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3">
        <CalendarIcon className="h-4 w-4 text-gray-400" />
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
        />
        <span className="text-gray-400">~</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="rounded-lg border border-border-strong px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
        />
        <Button variant="secondary" size="sm" onClick={handleRefresh} loading={loading}>
          조회
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-red-400 text-sm">{error}</div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <Table<SettlementSecretItem>
          columns={columns}
          data={data}
          keyExtractor={(s) => `${s.order_id}-${s.order_number}`}
          loading={loading}
          emptyMessage="데이터가 없습니다."
        />
      </div>

      <p className="text-xs text-gray-400">총 {formatNumber(data.length)}건</p>
    </div>
  );
}
