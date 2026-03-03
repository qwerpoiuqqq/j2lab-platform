import { useState, useEffect, useCallback } from 'react';
import Table, { type Column } from '@/components/common/Table';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import Pagination from '@/components/common/Pagination';
import {
  ArrowDownTrayIcon,
  CalendarIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import {
  formatCurrency,
  formatDate,
  formatNumber,
  getRoleLabel,
  downloadBlob,
} from '@/utils/format';
import {
  settlementsApi,
  type SettlementByHandlerRow,
  type SettlementByCompanyRow,
  type SettlementByDateRow,
} from '@/api/settlements';
import { ordersApi } from '@/api/orders';
import { useAuthStore } from '@/store/auth';
import type {
  Settlement,
  SettlementSummary,
  DailyCheckResponse,
  DailyCheckDistributor,
  OrderBrief,
} from '@/types';

type TabKey = 'all' | 'handler' | 'company' | 'date' | 'daily-check' | 'managed';

export default function SettlementPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'system_admin' || user?.role === 'company_admin';

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'all', label: '전체' },
    { key: 'handler', label: '담당자별' },
    { key: 'company', label: '회사별' },
    { key: 'date', label: '일자별' },
    ...(isAdmin ? [
      { key: 'managed' as TabKey, label: '월보장/관리형' },
      { key: 'daily-check' as TabKey, label: '정산 체크' },
    ] : []),
  ];

  const [activeTab, setActiveTab] = useState<TabKey>('all');

  // Shared date filters
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // All tab state
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [summary, setSummary] = useState<SettlementSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [exporting, setExporting] = useState(false);

  // Handler tab state
  const [handlerRows, setHandlerRows] = useState<SettlementByHandlerRow[]>([]);
  const [handlerLoading, setHandlerLoading] = useState(false);
  const [handlerError, setHandlerError] = useState<string | null>(null);

  // Company tab state
  const [companyRows, setCompanyRows] = useState<SettlementByCompanyRow[]>([]);
  const [companyLoading, setCompanyLoading] = useState(false);
  const [companyError, setCompanyError] = useState<string | null>(null);

  // Date tab state
  const [dateRows, setDateRows] = useState<SettlementByDateRow[]>([]);
  const [dateLoading, setDateLoading] = useState(false);
  const [dateError, setDateError] = useState<string | null>(null);

  // Daily check tab state
  const [checkDate, setCheckDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [dailyCheckData, setDailyCheckData] = useState<DailyCheckResponse | null>(null);
  const [dailyCheckLoading, setDailyCheckLoading] = useState(false);
  const [dailyCheckError, setDailyCheckError] = useState<string | null>(null);
  const [expandedDistributors, setExpandedDistributors] = useState<Set<string>>(new Set());
  const [selectedOrders, setSelectedOrders] = useState<Set<number>>(new Set());
  const [actionProcessing, setActionProcessing] = useState(false);
  const [holdModalOpen, setHoldModalOpen] = useState(false);
  const [holdReason, setHoldReason] = useState('');
  const [holdAction, setHoldAction] = useState<'single' | 'bulk'>('bulk');
  const [holdTargetId, setHoldTargetId] = useState<number | null>(null);

  // Managed tab state
  const [managedRows, setManagedRows] = useState<Settlement[]>([]);
  const [managedSummary, setManagedSummary] = useState<SettlementSummary | null>(null);
  const [managedLoading, setManagedLoading] = useState(false);
  const [managedError, setManagedError] = useState<string | null>(null);
  const [managedPage, setManagedPage] = useState(1);
  const [managedTotalPages, setManagedTotalPages] = useState(1);
  const [managedTotalItems, setManagedTotalItems] = useState(0);

  // Fetch "All" tab data
  useEffect(() => {
    if (activeTab !== 'all') return;
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
  }, [activeTab, page, startDate, endDate]);

  // Fetch "By Handler" tab data
  useEffect(() => {
    if (activeTab !== 'handler') return;
    let cancelled = false;
    setHandlerLoading(true);
    setHandlerError(null);

    settlementsApi
      .byHandler({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      .then((data) => {
        if (!cancelled) {
          setHandlerRows(data);
          setHandlerLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setHandlerError(err?.response?.data?.detail || '담당자별 정산을 불러오지 못했습니다.');
          setHandlerLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [activeTab, startDate, endDate]);

  // Fetch "By Company" tab data
  useEffect(() => {
    if (activeTab !== 'company') return;
    let cancelled = false;
    setCompanyLoading(true);
    setCompanyError(null);

    settlementsApi
      .byCompany({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      .then((data) => {
        if (!cancelled) {
          setCompanyRows(data);
          setCompanyLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setCompanyError(err?.response?.data?.detail || '회사별 정산을 불러오지 못했습니다.');
          setCompanyLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [activeTab, startDate, endDate]);

  // Fetch "By Date" tab data
  useEffect(() => {
    if (activeTab !== 'date') return;
    let cancelled = false;
    setDateLoading(true);
    setDateError(null);

    settlementsApi
      .byDate({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      .then((data) => {
        if (!cancelled) {
          setDateRows(data);
          setDateLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setDateError(err?.response?.data?.detail || '일자별 정산을 불러오지 못했습니다.');
          setDateLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [activeTab, startDate, endDate]);

  // Fetch "Managed" tab data
  useEffect(() => {
    if (activeTab !== 'managed') return;
    let cancelled = false;
    setManagedLoading(true);
    setManagedError(null);

    settlementsApi
      .list({
        page: managedPage,
        size: 20,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        order_type: 'monthly_guarantee,managed',
      })
      .then((data) => {
        if (!cancelled) {
          setManagedRows(data.items);
          setManagedSummary(data.summary);
          setManagedTotalPages(data.pages);
          setManagedTotalItems(data.total);
          setManagedLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setManagedError(err?.response?.data?.detail || '월보장/관리형 정산을 불러오지 못했습니다.');
          setManagedLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [activeTab, managedPage, startDate, endDate]);

  // Fetch "Daily Check" tab data
  const fetchDailyCheck = useCallback(async () => {
    setDailyCheckLoading(true);
    setDailyCheckError(null);
    try {
      const data = await settlementsApi.dailyCheck({ date: checkDate });
      setDailyCheckData(data);
    } catch (err: any) {
      setDailyCheckError(err?.response?.data?.detail || '정산 체크 데이터를 불러오지 못했습니다.');
    } finally {
      setDailyCheckLoading(false);
    }
  }, [checkDate]);

  useEffect(() => {
    if (activeTab !== 'daily-check') return;
    fetchDailyCheck();
  }, [activeTab, fetchDailyCheck]);

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

  // ─── Daily check actions ─────────────────────────────────────
  const toggleDistributor = (distributorId: string) => {
    setExpandedDistributors((prev) => {
      const next = new Set(prev);
      if (next.has(distributorId)) next.delete(distributorId);
      else next.add(distributorId);
      return next;
    });
  };

  const toggleOrderSelect = (orderId: number) => {
    setSelectedOrders((prev) => {
      const next = new Set(prev);
      if (next.has(orderId)) next.delete(orderId);
      else next.add(orderId);
      return next;
    });
  };

  const toggleAllInDistributor = (orders: OrderBrief[]) => {
    const ids = orders.map((o) => o.id);
    setSelectedOrders((prev) => {
      const allSelected = ids.every((id) => prev.has(id));
      const next = new Set(prev);
      if (allSelected) {
        ids.forEach((id) => next.delete(id));
      } else {
        ids.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const handleBulkApprove = async () => {
    if (selectedOrders.size === 0) return;
    setActionProcessing(true);
    try {
      await ordersApi.bulkPaymentConfirm(Array.from(selectedOrders));
      setSelectedOrders(new Set());
      await fetchDailyCheck();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '승인 처리에 실패했습니다.');
    } finally {
      setActionProcessing(false);
    }
  };

  const handleBulkReject = async () => {
    if (selectedOrders.size === 0) return;
    const reason = prompt('반려 사유를 입력하세요:');
    if (!reason) return;
    setActionProcessing(true);
    try {
      for (const orderId of selectedOrders) {
        await ordersApi.reject(orderId, reason);
      }
      setSelectedOrders(new Set());
      await fetchDailyCheck();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '반려 처리에 실패했습니다.');
    } finally {
      setActionProcessing(false);
    }
  };

  const openHoldModal = (action: 'single' | 'bulk', orderId?: number) => {
    setHoldAction(action);
    setHoldTargetId(orderId ?? null);
    setHoldReason('');
    setHoldModalOpen(true);
  };

  const handleHoldConfirm = async () => {
    if (!holdReason.trim()) return;
    setActionProcessing(true);
    try {
      if (holdAction === 'single' && holdTargetId) {
        await ordersApi.holdOrder(holdTargetId, holdReason);
      } else {
        await ordersApi.bulkHold(Array.from(selectedOrders), holdReason);
      }
      setSelectedOrders(new Set());
      setHoldModalOpen(false);
      await fetchDailyCheck();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '보류 처리에 실패했습니다.');
    } finally {
      setActionProcessing(false);
    }
  };

  const handleSingleApprove = async (orderId: number) => {
    setActionProcessing(true);
    try {
      await ordersApi.confirmPayment(orderId);
      await fetchDailyCheck();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '승인 처리에 실패했습니다.');
    } finally {
      setActionProcessing(false);
    }
  };

  const handleSingleReject = async (orderId: number) => {
    const reason = prompt('반려 사유를 입력하세요:');
    if (!reason) return;
    setActionProcessing(true);
    try {
      await ordersApi.reject(orderId, reason);
      await fetchDailyCheck();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '반려 처리에 실패했습니다.');
    } finally {
      setActionProcessing(false);
    }
  };

  // ─── Column definitions ────────────────────────────────────────

  const allColumns: Column<Settlement>[] = [
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

  const handlerColumns: Column<SettlementByHandlerRow>[] = [
    {
      key: 'handler_name',
      header: '담당자명',
      render: (r) => <span className="font-medium text-gray-900">{r.handler_name}</span>,
    },
    {
      key: 'handler_role',
      header: '역할',
      render: (r) => (
        <Badge className="bg-gray-100 text-gray-700">{getRoleLabel(r.handler_role)}</Badge>
      ),
    },
    {
      key: 'order_count',
      header: '주문수',
      render: (r) => <span className="text-gray-700">{formatNumber(r.order_count)}</span>,
    },
    {
      key: 'item_count',
      header: '아이템수',
      render: (r) => <span className="text-gray-700">{formatNumber(r.item_count)}</span>,
    },
    {
      key: 'total_revenue',
      header: '매출',
      render: (r) => <span className="font-medium">{formatCurrency(r.total_revenue)}</span>,
    },
    {
      key: 'total_cost',
      header: '매입',
      render: (r) => <span className="text-gray-600">{formatCurrency(r.total_cost)}</span>,
    },
    {
      key: 'total_profit',
      header: '이익',
      render: (r) => (
        <span className={`font-medium ${r.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {formatCurrency(r.total_profit)}
        </span>
      ),
    },
    {
      key: 'avg_margin_pct',
      header: '마진율',
      render: (r) => (
        <Badge className={r.avg_margin_pct >= 20 ? 'bg-green-100 text-green-800' : r.avg_margin_pct >= 10 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}>
          {r.avg_margin_pct.toFixed(1)}%
        </Badge>
      ),
    },
  ];

  const companyColumns: Column<SettlementByCompanyRow>[] = [
    {
      key: 'company_name',
      header: '회사명',
      render: (r) => <span className="font-medium text-gray-900">{r.company_name}</span>,
    },
    {
      key: 'order_count',
      header: '주문수',
      render: (r) => <span className="text-gray-700">{formatNumber(r.order_count)}</span>,
    },
    {
      key: 'item_count',
      header: '아이템수',
      render: (r) => <span className="text-gray-700">{formatNumber(r.item_count)}</span>,
    },
    {
      key: 'total_revenue',
      header: '매출',
      render: (r) => <span className="font-medium">{formatCurrency(r.total_revenue)}</span>,
    },
    {
      key: 'total_cost',
      header: '매입',
      render: (r) => <span className="text-gray-600">{formatCurrency(r.total_cost)}</span>,
    },
    {
      key: 'total_profit',
      header: '이익',
      render: (r) => (
        <span className={`font-medium ${r.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {formatCurrency(r.total_profit)}
        </span>
      ),
    },
    {
      key: 'avg_margin_pct',
      header: '마진율',
      render: (r) => (
        <Badge className={r.avg_margin_pct >= 20 ? 'bg-green-100 text-green-800' : r.avg_margin_pct >= 10 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'}>
          {r.avg_margin_pct.toFixed(1)}%
        </Badge>
      ),
    },
  ];

  const dateColumns: Column<SettlementByDateRow>[] = [
    {
      key: 'date',
      header: '날짜',
      render: (r) => <span className="font-medium text-gray-900">{r.date}</span>,
    },
    {
      key: 'order_count',
      header: '주문수',
      render: (r) => <span className="text-gray-700">{formatNumber(r.order_count)}</span>,
    },
    {
      key: 'item_count',
      header: '아이템수',
      render: (r) => <span className="text-gray-700">{formatNumber(r.item_count)}</span>,
    },
    {
      key: 'total_revenue',
      header: '매출',
      render: (r) => <span className="font-medium">{formatCurrency(r.total_revenue)}</span>,
    },
    {
      key: 'total_cost',
      header: '매입',
      render: (r) => <span className="text-gray-600">{formatCurrency(r.total_cost)}</span>,
    },
    {
      key: 'total_profit',
      header: '이익',
      render: (r) => (
        <span className={`font-medium ${r.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {formatCurrency(r.total_profit)}
        </span>
      ),
    },
  ];

  // ─── Render helpers ─────────────────────────────────────────────

  const renderError = (msg: string | null) =>
    msg ? (
      <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{msg}</div>
    ) : null;

  const renderAllTab = () => (
    <>
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

      {renderError(error)}

      <Table<Settlement>
        columns={allColumns}
        data={settlements}
        keyExtractor={(s) => `${s.order_id}-${s.order_number}`}
        loading={loading}
        emptyMessage="정산 내역이 없습니다."
      />

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalItems={totalItems}
        pageSize={20}
      />
    </>
  );

  const renderHandlerTab = () => (
    <>
      {renderError(handlerError)}

      <Table<SettlementByHandlerRow>
        columns={handlerColumns}
        data={handlerRows}
        keyExtractor={(r) => r.handler_id}
        loading={handlerLoading}
        emptyMessage="담당자별 정산 내역이 없습니다."
      />
    </>
  );

  const renderCompanyTab = () => (
    <>
      {renderError(companyError)}

      <Table<SettlementByCompanyRow>
        columns={companyColumns}
        data={companyRows}
        keyExtractor={(r) => String(r.company_id ?? 'none')}
        loading={companyLoading}
        emptyMessage="회사별 정산 내역이 없습니다."
      />
    </>
  );

  const renderDateTab = () => (
    <>
      {renderError(dateError)}

      <Table<SettlementByDateRow>
        columns={dateColumns}
        data={dateRows}
        keyExtractor={(r) => r.date}
        loading={dateLoading}
        emptyMessage="일자별 정산 내역이 없습니다."
      />
    </>
  );

  const managedColumns: Column<Settlement>[] = [
    {
      key: 'order_number',
      header: '주문번호',
      render: (s) => <span className="font-mono text-sm">{s.order_number}</span>,
    },
    {
      key: 'product_name',
      header: '상품',
      render: (s) => <span className="text-gray-900">{s.product_name}</span>,
    },
    {
      key: 'user_name',
      header: '주문자',
      render: (s) => <span className="text-gray-700">{s.user_name}</span>,
    },
    {
      key: 'quantity',
      header: '수량',
      render: (s) => <span className="text-gray-700">{formatNumber(s.quantity)}</span>,
    },
    {
      key: 'cost',
      header: '매입단가',
      render: (s) => {
        const costPerUnit = s.quantity > 0 ? Math.round(s.cost / s.quantity) : 0;
        return <span className="text-gray-600">{formatCurrency(costPerUnit)}</span>;
      },
    },
    {
      key: 'cost_total',
      header: '매입합계',
      render: (s) => <span className="font-medium text-red-600">{formatCurrency(s.cost)}</span>,
    },
    {
      key: 'created_at',
      header: '일자',
      render: (s) => <span className="text-gray-500 text-xs">{formatDate(s.created_at)}</span>,
    },
  ];

  const renderManagedTab = () => (
    <>
      {managedSummary && (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <SummaryCard
            label="총 건수"
            value={`${formatNumber(managedSummary.item_count)}건`}
            subtitle={`주문 ${formatNumber(managedSummary.order_count)}건`}
            color="blue"
          />
          <SummaryCard
            label="총 매입 비용"
            value={formatCurrency(managedSummary.total_cost)}
            color="red"
          />
          <SummaryCard
            label="매출"
            value={formatCurrency(managedSummary.total_revenue)}
            subtitle="월보장/관리형은 매출 0원"
            color="yellow"
          />
        </div>
      )}

      {renderError(managedError)}

      <Table<Settlement>
        columns={managedColumns}
        data={managedRows}
        keyExtractor={(s) => `${s.order_id}-${s.order_number}`}
        loading={managedLoading}
        emptyMessage="월보장/관리형 정산 내역이 없습니다."
      />

      <Pagination
        page={managedPage}
        totalPages={managedTotalPages}
        onPageChange={setManagedPage}
        totalItems={managedTotalItems}
        pageSize={20}
      />
    </>
  );

  const getStatusBadge = (status: string) => {
    const map: Record<string, { variant: 'warning' | 'info' | 'success' | 'danger' | 'default'; label: string }> = {
      submitted: { variant: 'info', label: '제출됨' },
      payment_hold: { variant: 'warning', label: '보류' },
      payment_confirmed: { variant: 'success', label: '승인됨' },
      rejected: { variant: 'danger', label: '반려됨' },
    };
    const info = map[status] || { variant: 'default' as const, label: status };
    return <Badge variant={info.variant}>{info.label}</Badge>;
  };

  const renderDailyCheckTab = () => {
    if (dailyCheckLoading) {
      return (
        <div className="bg-white rounded-xl border border-gray-200 p-8">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded w-1/3" />
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-4 bg-gray-200 rounded w-2/3" />
          </div>
        </div>
      );
    }

    return (
      <>
        {/* Date picker for daily check */}
        <div className="flex items-center gap-3">
          <CalendarIcon className="h-4 w-4 text-gray-400" />
          <input
            type="date"
            value={checkDate}
            onChange={(e) => setCheckDate(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {renderError(dailyCheckError)}

        {/* Summary cards */}
        {dailyCheckData && (
          <div className="grid grid-cols-3 gap-4">
            <SummaryCard
              label="총 접수건"
              value={formatNumber(dailyCheckData.summary.total_orders)}
              color="blue"
            />
            <SummaryCard
              label="총 금액"
              value={formatCurrency(dailyCheckData.summary.total_amount)}
              color="green"
            />
            <SummaryCard
              label="총판 수"
              value={String(dailyCheckData.summary.distributor_count)}
              color="purple"
            />
          </div>
        )}

        {/* Bulk action bar */}
        {selectedOrders.size > 0 && (
          <div className="bg-primary-50 border border-primary-200 rounded-lg p-3 flex items-center justify-between">
            <span className="text-sm text-primary-700 font-medium">
              {selectedOrders.size}건 선택됨
            </span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="success"
                onClick={handleBulkApprove}
                loading={actionProcessing}
              >
                일괄 승인
              </Button>
              <Button
                size="sm"
                variant="warning"
                onClick={() => openHoldModal('bulk')}
                loading={actionProcessing}
              >
                일괄 보류
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={handleBulkReject}
                loading={actionProcessing}
              >
                일괄 반려
              </Button>
            </div>
          </div>
        )}

        {/* Distributor groups */}
        {dailyCheckData?.distributors.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500">
            해당 날짜에 정산 체크 대상 접수건이 없습니다.
          </div>
        )}

        {dailyCheckData?.distributors.map((dist: DailyCheckDistributor) => {
          const isExpanded = expandedDistributors.has(dist.distributor_id);
          const allSelected = dist.orders.every((o) => selectedOrders.has(o.id));

          return (
            <div key={dist.distributor_id} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              {/* Distributor header row */}
              <button
                onClick={() => toggleDistributor(dist.distributor_id)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  {isExpanded ? (
                    <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <ChevronRightIcon className="h-5 w-5 text-gray-400" />
                  )}
                  <div className="text-left">
                    <span className="font-semibold text-gray-900">{dist.distributor_name}</span>
                    <span className="ml-2 text-sm text-gray-500">
                      ({formatNumber(dist.order_count)}건)
                    </span>
                  </div>
                </div>
                <span className="font-medium text-gray-700">
                  {formatCurrency(dist.total_amount)}
                </span>
              </button>

              {/* Expanded order list */}
              {isExpanded && (
                <div className="border-t border-gray-200">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left">
                          <input
                            type="checkbox"
                            checked={allSelected && dist.orders.length > 0}
                            onChange={() => toggleAllInDistributor(dist.orders)}
                            className="rounded border-gray-300 text-primary-600"
                          />
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          주문 ID
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          업체명
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          금액
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          상태
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          접수일
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          작업
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {dist.orders.map((order: OrderBrief) => (
                        <tr key={order.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              checked={selectedOrders.has(order.id)}
                              onChange={() => toggleOrderSelect(order.id)}
                              className="rounded border-gray-300 text-primary-600"
                            />
                          </td>
                          <td className="px-4 py-3 text-sm font-mono text-primary-600">
                            #{order.id}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            {order.place_name || '-'}
                          </td>
                          <td className="px-4 py-3 text-sm font-medium text-gray-700">
                            {formatCurrency(order.total_amount)}
                          </td>
                          <td className="px-4 py-3">
                            {getStatusBadge(order.status)}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500">
                            {order.created_at ? formatDate(order.created_at) : '-'}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex gap-1">
                              <Button
                                size="sm"
                                variant="success"
                                onClick={() => handleSingleApprove(order.id)}
                                disabled={actionProcessing}
                              >
                                승인
                              </Button>
                              <Button
                                size="sm"
                                variant="warning"
                                onClick={() => openHoldModal('single', order.id)}
                                disabled={actionProcessing}
                              >
                                보류
                              </Button>
                              <Button
                                size="sm"
                                variant="danger"
                                onClick={() => handleSingleReject(order.id)}
                                disabled={actionProcessing}
                              >
                                반려
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}

        {/* Hold reason modal */}
        {holdModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">보류 사유 입력</h3>
              <textarea
                value={holdReason}
                onChange={(e) => setHoldReason(e.target.value)}
                placeholder="보류 사유를 입력하세요..."
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[100px]"
              />
              <div className="flex justify-end gap-2 mt-4">
                <Button
                  variant="secondary"
                  onClick={() => setHoldModalOpen(false)}
                  disabled={actionProcessing}
                >
                  취소
                </Button>
                <Button
                  variant="warning"
                  onClick={handleHoldConfirm}
                  loading={actionProcessing}
                  disabled={!holdReason.trim()}
                >
                  보류 처리
                </Button>
              </div>
            </div>
          </div>
        )}
      </>
    );
  };

  // ─── Main render ────────────────────────────────────────────────

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

      {/* Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setActiveTab(tab.key); setPage(1); }}
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

      {/* Filters (not shown for daily-check tab which has its own date picker) */}
      {activeTab !== 'daily-check' && (
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
      )}

      {/* Tab content */}
      {activeTab === 'all' && renderAllTab()}
      {activeTab === 'handler' && renderHandlerTab()}
      {activeTab === 'company' && renderCompanyTab()}
      {activeTab === 'date' && renderDateTab()}
      {activeTab === 'managed' && renderManagedTab()}
      {activeTab === 'daily-check' && renderDailyCheckTab()}
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
