import { useState, useEffect, useMemo } from 'react';
import Button from '@/components/common/Button';
import Badge from '@/components/common/Badge';
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import { formatCurrency, getOrderStatusLabel, getOrderStatusColor } from '@/utils/format';
import { ordersApi } from '@/api/orders';
import type { Order } from '@/types';

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    ordersApi
      .list({ page: 1, size: 100, status: 'processing' })
      .then((data) => {
        if (!cancelled) {
          setOrders(data.items);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
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

  // Group orders by created_at date (simplified - in real app, use deadline field)
  const ordersByDate = useMemo(() => {
    const map: Record<string, Order[]> = {};
    orders.forEach((order) => {
      const dateKey = order.created_at.split('T')[0];
      if (!map[dateKey]) map[dateKey] = [];
      map[dateKey].push(order);
    });
    return map;
  }, [orders]);

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

  const selectedOrders = selectedDate ? (ordersByDate[selectedDate] || []) : [];

  const monthNames = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">마감 캘린더</h1>
        <p className="mt-1 text-sm text-gray-500">주문 마감일을 캘린더에서 확인합니다.</p>
      </div>

      {/* Calendar Navigation */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => navigateMonth(-1)} icon={<ChevronLeftIcon className="h-4 w-4" />}>
          이전
        </Button>
        <h2 className="text-lg font-bold text-gray-900">{year}년 {monthNames[month]}</h2>
        <Button variant="ghost" size="sm" onClick={() => navigateMonth(1)}>
          다음 <ChevronRightIcon className="h-4 w-4 ml-1" />
        </Button>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-red-500" /> 오늘 마감</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-orange-500" /> 1일 후</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-yellow-500" /> 2일 후</div>
        <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-green-500" /> 3일+</div>
      </div>

      {loading && (
        <div className="text-center py-4 text-sm text-gray-400">주문 데이터 로딩 중...</div>
      )}

      <div className="flex gap-6">
        {/* Calendar Grid */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          {/* Day headers */}
          <div className="grid grid-cols-7 bg-gray-50 border-b border-gray-200">
            {dayNames.map((day) => (
              <div key={day} className="px-2 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                {day}
              </div>
            ))}
          </div>

          {/* Day cells */}
          <div className="grid grid-cols-7">
            {calendarDays.map((day, idx) => {
              const dateStr = `${day.date.getFullYear()}-${String(day.date.getMonth() + 1).padStart(2, '0')}-${String(day.date.getDate()).padStart(2, '0')}`;
              const dayOrders = ordersByDate[dateStr] || [];
              const isToday = dateStr === todayStr;
              const isSelected = dateStr === selectedDate;

              return (
                <button
                  key={idx}
                  onClick={() => setSelectedDate(dateStr)}
                  className={`min-h-[80px] p-1.5 border-b border-r border-gray-100 text-left transition-colors hover:bg-gray-50
                    ${!day.isCurrentMonth ? 'text-gray-300 bg-gray-50/50' : ''}
                    ${isSelected ? 'bg-primary-50 ring-2 ring-primary-500 ring-inset' : ''}
                  `}
                >
                  <div className={`text-xs font-medium mb-1 w-6 h-6 flex items-center justify-center rounded-full
                    ${isToday ? 'bg-primary-500 text-white' : ''}
                  `}>
                    {day.date.getDate()}
                  </div>
                  {dayOrders.slice(0, 3).map((order) => (
                    <div
                      key={order.id}
                      className={`text-[10px] px-1 py-0.5 mb-0.5 rounded truncate text-white ${getUrgencyColor(dateStr)}`}
                    >
                      {order.order_number}
                    </div>
                  ))}
                  {dayOrders.length > 3 && (
                    <div className="text-[10px] text-gray-400 px-1">+{dayOrders.length - 3}건</div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Selected Date Detail */}
        <div className="w-80 shrink-0">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 sticky top-20">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              {selectedDate ? `${selectedDate} 주문` : '날짜를 선택하세요'}
            </h3>
            {selectedOrders.length === 0 ? (
              <p className="text-sm text-gray-400">해당 날짜에 주문이 없습니다.</p>
            ) : (
              <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                {selectedOrders.map((order) => (
                  <div key={order.id} className="p-3 border border-gray-100 rounded-lg hover:bg-gray-50">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs text-gray-600">{order.order_number}</span>
                      <Badge className={getOrderStatusColor(order.status)} variant="default">
                        {getOrderStatusLabel(order.status)}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-900">{order.user?.name || '-'}</p>
                    <p className="text-xs text-gray-500 mt-1">{formatCurrency(order.total_amount)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
