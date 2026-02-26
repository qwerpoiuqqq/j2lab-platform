import { useState } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Button from '@/components/common/Button';
import Input from '@/components/common/Input';
import {
  ArrowDownTrayIcon,
  LockClosedIcon,
  CalendarIcon,
} from '@heroicons/react/24/outline';
import { formatCurrency, formatNumber, downloadBlob } from '@/utils/format';
import { settlementsApi } from '@/api/settlements';
import type { SettlementSecretItem } from '@/types';

export default function SettlementSecretPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  const [data, setData] = useState<SettlementSecretItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const handleAuth = async () => {
    setAuthLoading(true);
    setAuthError('');
    try {
      const result = await settlementsApi.getSecret({ password, start_date: startDate, end_date: endDate });
      setData(result.items);
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

  const totalRevenue = data.reduce((sum, item) => sum + item.revenue, 0);
  const totalCost = data.reduce((sum, item) => sum + item.cost, 0);
  const totalProfit = data.reduce((sum, item) => sum + item.net_profit, 0);
  const avgProfitRate = data.length > 0
    ? data.reduce((sum, item) => sum + item.profit_rate, 0) / data.length
    : 0;

  const columns: Column<SettlementSecretItem>[] = [
    { key: 'order_number', header: '주문번호', render: (s) => <span className="font-mono text-xs">{s.order_number}</span> },
    { key: 'product', header: '상품', render: (s) => <span className="text-sm">{s.product}</span> },
    { key: 'seller', header: '판매자', render: (s) => <span className="text-sm">{s.seller}</span> },
    { key: 'revenue', header: '매출', render: (s) => <span className="text-sm font-medium">{formatCurrency(s.revenue)}</span> },
    { key: 'cost', header: '매입', render: (s) => <span className="text-sm">{formatCurrency(s.cost)}</span> },
    { key: 'margin', header: '마진', render: (s) => <span className="text-sm">{formatCurrency(s.margin)}</span> },
    { key: 'commission', header: '수수료', render: (s) => <span className="text-sm">{formatCurrency(s.commission)}</span> },
    { key: 'vat', header: '부가세', render: (s) => <span className="text-sm">{formatCurrency(s.vat)}</span> },
    {
      key: 'net_profit',
      header: '순이익',
      render: (s) => (
        <span className={`text-sm font-medium ${s.net_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {formatCurrency(s.net_profit)}
        </span>
      ),
    },
    {
      key: 'profit_rate',
      header: '이익률',
      render: (s) => (
        <span className={`text-sm font-medium ${s.profit_rate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {s.profit_rate.toFixed(1)}%
        </span>
      ),
    },
    { key: 'payment_status', header: '결제', render: (s) => <span className="text-xs">{s.payment_status}</span> },
    { key: 'settlement_status', header: '정산', render: (s) => <span className="text-xs">{s.settlement_status}</span> },
    { key: 'notes', header: '비고', render: (s) => <span className="text-xs text-gray-500">{s.notes || '-'}</span> },
  ];

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 w-full max-w-md">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <LockClosedIcon className="h-5 w-5 text-red-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900">수익 분석 (비공개)</h2>
              <p className="text-sm text-gray-500">접근 비밀번호를 입력하세요.</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <CalendarIcon className="h-4 w-4 text-gray-400" />
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <span className="text-gray-400">~</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

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
          <h1 className="text-2xl font-bold text-gray-900">수익 분석 (비공개)</h1>
          <p className="mt-1 text-sm text-gray-500">13컬럼 상세 수익 분석 데이터입니다.</p>
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
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 border-l-4 border-l-blue-500">
          <p className="text-sm text-gray-500">총 매출</p>
          <p className="text-xl font-bold text-gray-900 mt-1">{formatCurrency(totalRevenue)}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 border-l-4 border-l-red-500">
          <p className="text-sm text-gray-500">총 매입</p>
          <p className="text-xl font-bold text-gray-900 mt-1">{formatCurrency(totalCost)}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 border-l-4 border-l-green-500">
          <p className="text-sm text-gray-500">순이익</p>
          <p className={`text-xl font-bold mt-1 ${totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatCurrency(totalProfit)}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 border-l-4 border-l-purple-500">
          <p className="text-sm text-gray-500">평균 이익률</p>
          <p className={`text-xl font-bold mt-1 ${avgProfitRate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {avgProfitRate.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <CalendarIcon className="h-4 w-4 text-gray-400" />
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <span className="text-gray-400">~</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        <Button variant="secondary" size="sm" onClick={handleRefresh} loading={loading}>
          조회
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <Table<SettlementSecretItem>
          columns={columns}
          data={data}
          keyExtractor={(s) => s.order_number}
          loading={loading}
          emptyMessage="데이터가 없습니다."
        />
      </div>

      <p className="text-xs text-gray-400">총 {formatNumber(data.length)}건</p>
    </div>
  );
}
