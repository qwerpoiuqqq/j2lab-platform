import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import Button from '@/components/common/Button';
import Badge from '@/components/common/Badge';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import { formatCurrency, getOrderStatusLabel, getOrderStatusColor } from '@/utils/format';
import { ordersApi } from '@/api/orders';
import type { CalendarDeadlines } from '@/types';

interface CalendarEntry {
  type: 'order' | 'campaign';
  id: number;
  label: string;
  status: string;
  amount?: number;
}

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [data, setData] = useState<CalendarDeadlines | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    ordersApi
      .getDeadlines(year, month + 1)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail || '캘린더 데이터를 불러오지 못했습니다.');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [year, month]);

  // Build calendar grid
  const calendarDays = useMemo(() => {
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startOffset = firstDay.getDay();
    const totalDays = lastDay.getDate();

    const days: { date: Date; isCurrentMonth: boolean }[] = [];

    // Previous month padding
    for (let i = startOffset - 1; i >= 0; i--) {
      const d = new Date(year, month, -i);
      days.push({ date: d, isCurrentMonth: false });
    }

    // Current month
    for (let i = 1; i <= totalDays; i++) {
      days.push({ date: new Date(year, month, i), isCurrentMonth: true });
    }

    // Next month padding
    const remaining = 42 - days.length;
    for (let i = 1; i <= remaining; i++) {
      days.push({ date: new Date(year, month + 1, i), isCurrentMonth: false });
    }

    return days;
  }, [year, month]);

  // Group entries by date (orders by deadline, campaigns by end_date)
  const entriesByDate = useMemo(() => {
    const map: Record<string, CalendarEntry[]> = {};
    if (!data) return map;

    data.orders.forEach((order) => {
      if (!order.deadline) return;
      const dateKey = order.deadline.split('T')[0];
      if (!map[dateKey]) map[dateKey] = [];
      map[dateKey].push({
        type: 'order',
        id: order.id,
        label: order.order_number,
        status: order.status,
        amount: order.total_amount,
      });
    });

    data.campaigns.forEach((campaign) => {
      if (!campaign.end_date) return;
      const dateKey = campaign.end_date.split('T')[0];
      if (!map[dateKey]) map[dateKey] = [];
      map[dateKey].push({
        type: 'campaign',
        id: campaign.id,
        label: campaign.place_name || campaign.campaign_code || `C-${campaign.id}`,
        status: campaign.status,
      });
    });

    return map;
  }, [data]);

  const navigateMonth = (delta: number) => {
    setCurrentDate(new Date(year, month + delta, 1));
    setSelectedDate(null);
  };

  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  const getUrgencyColor = (dateStr: string): string => {
    const diff = Math.floor((new Date(dateStr).getTime() - today.getTime()) / 86400000);
    if (diff <= 0) return 'bg-red-500';
    if (diff === 1) return 'bg-orange-500';
    if (diff === 2) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const selectedEntries = selectedDate ? (entriesByDate[selectedDate] || []) : [];

  const monthNames = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">마감 캘린더</h1>
        <p className="mt-1 text-sm text-gray-400">주문 마감일과 캠페인 종료일을 캘린더에서 확인합니다.</p>
      </div>

      {/* Calendar Navigation */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => navigateMonth(-1)} icon={<ChevronLeftIcon className="h-4 w-4" />}>
          이전
        </Button>
        <h2 className="text-lg font-bold text-gray-100">{year}년 {monthNames[month]}</h2>
        <Button variant="ghost" size="sm" onClick={() => navigateMonth(1)}>
          다음 <ChevronRightIcon className="h-4 w-4 ml-1" />
        </Button>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-red-500" /> 오늘 마감</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-orange-500" /> 1일 후</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-yellow-500" /> 2일 후</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-green-500" /> 3일+</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-blue-500" /> 캠페인 종료</div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-red-400 text-sm">{error}</div>
      )}

      {loading && (
        <div className="text-center py-4 text-sm text-gray-400">데이터 로딩 중...</div>
      )}

      <div className="flex gap-6">
        {/* Calendar Grid */}
        <div className="flex-1 bg-surface rounded-xl border border-border shadow-sm overflow-hidden">
          {/* Day headers */}
          <div className="grid grid-cols-7 bg-surface-raised border-b border-border">
            {dayNames.map((day) => (
              <div key={day} className="px-2 py-3 text-center text-xs font-medium text-gray-400 uppercase">
                {day}
              </div>
            ))}
          </div>

          {/* Day cells */}
          <div className="grid grid-cols-7">
            {calendarDays.map((day, idx) => {
              const dateStr = `${day.date.getFullYear()}-${String(day.date.getMonth() + 1).padStart(2, '0')}-${String(day.date.getDate()).padStart(2, '0')}`;
              const dayEntries = entriesByDate[dateStr] || [];
              const isToday = dateStr === todayStr;
              const isSelected = dateStr === selectedDate;

              return (
                <button
                  key={idx}
                  onClick={() => setSelectedDate(dateStr)}
                  className={`min-h-[80px] p-1.5 border-b border-r border-border-subtle text-left transition-colors hover:bg-surface-raised
                    ${!day.isCurrentMonth ? 'text-gray-300 bg-surface-raised/50' : ''}
                    ${isSelected ? 'bg-primary-900/20 ring-2 ring-primary-500 ring-inset' : ''}
                  `}
                >
                  <div className={`text-xs font-medium mb-1 w-6 h-6 flex items-center justify-center rounded-full
                    ${isToday ? 'bg-primary-500 text-white' : ''}
                  `}>
                    {day.date.getDate()}
                  </div>
                  {dayEntries.slice(0, 3).map((entry) => (
                    <div
                      key={`${entry.type}-${entry.id}`}
                      className={`text-[10px] px-1 py-0.5 mb-0.5 rounded truncate text-white ${
                        entry.type === 'campaign' ? 'bg-blue-500' : getUrgencyColor(dateStr)
                      }`}
                    >
                      {entry.type === 'campaign' ? `C: ${entry.label}` : entry.label}
                    </div>
                  ))}
                  {dayEntries.length > 3 && (
                    <div className="text-[10px] text-gray-400 px-1">+{dayEntries.length - 3}건</div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Selected Date Detail */}
        <div className="w-80 shrink-0">
          <div className="bg-surface rounded-xl border border-border shadow-sm p-4 sticky top-20">
            <h3 className="text-sm font-semibold text-gray-100 mb-3">
              {selectedDate ? `${selectedDate}` : '날짜를 선택하세요'}
            </h3>
            {selectedEntries.length === 0 ? (
              <p className="text-sm text-gray-400">해당 날짜에 항목이 없습니다.</p>
            ) : (
              <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                {selectedEntries.map((entry) => (
                  <Link
                    key={`${entry.type}-${entry.id}`}
                    to={entry.type === 'order' ? `/orders/${entry.id}` : `/campaigns/${entry.id}`}
                    className="block p-3 border border-border-subtle rounded-lg hover:bg-surface-raised"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs text-gray-400">{entry.label}</span>
                      <Badge
                        className={entry.type === 'campaign' ? 'bg-blue-900/30 text-blue-400' : getOrderStatusColor(entry.status)}
                        variant="default"
                      >
                        {entry.type === 'campaign' ? '캠페인' : getOrderStatusLabel(entry.status)}
                      </Badge>
                    </div>
                    {entry.type === 'order' && entry.amount !== undefined && (
                      <p className="text-xs text-gray-400 mt-1">{formatCurrency(entry.amount)}</p>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
