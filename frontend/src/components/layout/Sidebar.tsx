import { useState, useRef, useEffect, useCallback } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  HomeIcon,
  ClipboardDocumentListIcon,
  MegaphoneIcon,
  UsersIcon,
  BuildingOffice2Icon,
  CubeIcon,
  Cog6ToothIcon,
  XMarkIcon,
  TableCellsIcon,
  CalendarIcon,
  BanknotesIcon,
  PlusCircleIcon,
  ArrowUpTrayIcon,
  UserGroupIcon,
  SwatchIcon,
  TagIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ChartBarIcon,
  SignalIcon,
  BellIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  CircleStackIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '@/hooks/useAuth';
import { getRoleLabel, formatRelativeTime, getNotificationTypeLabel, formatNumber } from '@/utils/format';
import { notificationsApi } from '@/api/notifications';
import { pointsApi } from '@/api/points';
import type { UserRole, Notification } from '@/types';
import LogicLabLogo from '@/components/common/LogicLabLogo';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface NavItem {
  name: string;
  path: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  allowedRoles: UserRole[];
  children?: NavItem[];
  group?: string;
}

const ALL_ROLES: UserRole[] = ['system_admin', 'company_admin', 'order_handler', 'distributor', 'sub_account'];

const navItems: NavItem[] = [
  // ── 메인 ──
  { name: '대시보드', path: '/', icon: HomeIcon, allowedRoles: ALL_ROLES, group: '메인' },
  // ── 주문 ──
  { name: '주문 접수', path: '/orders/grid', icon: TableCellsIcon, allowedRoles: ALL_ROLES, group: '주문' },
  { name: '주문내역', path: '/orders', icon: ClipboardDocumentListIcon, allowedRoles: ALL_ROLES },
  { name: '마감 캘린더', path: '/calendar', icon: CalendarIcon, allowedRoles: ['system_admin', 'company_admin', 'order_handler', 'distributor'] },
  // ── 운영 ──
  {
    name: '캠페인 관리', path: '/campaigns', icon: MegaphoneIcon,
    allowedRoles: ['system_admin', 'company_admin', 'order_handler'], group: '운영',
    children: [
      { name: '캠페인 목록', path: '/campaigns', icon: ChartBarIcon, allowedRoles: ['system_admin', 'company_admin', 'order_handler'] },
      { name: '캠페인 추가', path: '/campaigns/add', icon: PlusCircleIcon, allowedRoles: ['system_admin', 'company_admin', 'order_handler'] },
      { name: '엑셀 업로드', path: '/campaigns/upload', icon: ArrowUpTrayIcon, allowedRoles: ['system_admin', 'company_admin', 'order_handler'] },
      { name: '계정 관리', path: '/campaigns/accounts', icon: UserGroupIcon, allowedRoles: ['system_admin', 'company_admin', 'order_handler'] },
      { name: '템플릿 관리', path: '/campaigns/templates', icon: SwatchIcon, allowedRoles: ['system_admin', 'company_admin'] },
    ],
  },
  { name: '포인트 관리', path: '/points', icon: CircleStackIcon, allowedRoles: ['system_admin', 'company_admin', 'distributor', 'order_handler'] },
  // ── 관리 ──
  {
    name: '상품 관리', path: '/products', icon: CubeIcon,
    allowedRoles: ['system_admin', 'company_admin'], group: '관리',
    children: [
      { name: '상품 목록', path: '/products', icon: CubeIcon, allowedRoles: ['system_admin', 'company_admin'] },
      { name: '카테고리', path: '/products/categories', icon: TagIcon, allowedRoles: ['system_admin', 'company_admin'] },
      { name: '일류 리워드 설정', path: '/products/reward-settings', icon: SignalIcon, allowedRoles: ['system_admin', 'company_admin'] },
    ],
  },
  { name: '유저 관리', path: '/users', icon: UsersIcon, allowedRoles: ['system_admin', 'company_admin', 'order_handler'] },
  { name: '회사 관리', path: '/companies', icon: BuildingOffice2Icon, allowedRoles: ['system_admin'] },
  // ── 시스템 ──
  { name: '시스템 설정', path: '/settings', icon: Cog6ToothIcon, allowedRoles: ['system_admin'], group: '시스템' },
];

const NOTIFICATION_TYPE_ICONS: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  order: ClipboardDocumentListIcon,
  campaign: MegaphoneIcon,
  system: Cog6ToothIcon,
  settlement: BanknotesIcon,
};

const NOTIFICATION_TYPE_COLORS: Record<string, string> = {
  order: 'text-primary-400',
  campaign: 'text-green-400',
  system: 'text-gray-400',
  settlement: 'text-purple-400',
};

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { user, logout } = useAuth();
  const userRole = user?.role;
  const location = useLocation();
  const navigate = useNavigate();

  // Track which parent items are expanded
  const [expandedItems, setExpandedItems] = useState<Set<string>>(() => {
    // Auto-expand parent if current path matches a child
    const initial = new Set<string>();
    for (const item of navItems) {
      if (item.children) {
        const childMatch = item.children.some(
          (child) => location.pathname === child.path || location.pathname.startsWith(child.path + '/'),
        );
        if (childMatch) {
          initial.add(item.path);
        }
      }
    }
    return initial;
  });

  // Notification state
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const notificationRef = useRef<HTMLDivElement>(null);

  // Close notification dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        notificationRef.current &&
        !notificationRef.current.contains(event.target as Node)
      ) {
        setShowNotifications(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch unread count
  const fetchUnreadCount = useCallback(async () => {
    try {
      const data = await notificationsApi.list({ page: 1, size: 1 });
      setUnreadCount(data.unread_count);
    } catch {
      // Silently fail for notification polling
    }
  }, []);

  // Poll for unread count every 60 seconds
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 60000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Points balance state (for distributor)
  const [pointsBalance, setPointsBalance] = useState<number | null>(null);
  const [pointsOwnerName, setPointsOwnerName] = useState<string | null>(null);
  const [pointsOwnerRole, setPointsOwnerRole] = useState<UserRole | null>(null);

  // Pending charge request count (for admin)
  const [pendingChargeCount, setPendingChargeCount] = useState(0);

   // Fetch effective points balance for the actual charge owner
   const fetchPointsBalance = useCallback(async () => {
     if (!user || !['distributor', 'order_handler'].includes(user.role)) return;
     try {
       const data = await pointsApi.getEffectiveMyBalance();
       setPointsBalance(data.balance);
       setPointsOwnerName(data.effective_user_name);
       setPointsOwnerRole(data.effective_user_role as UserRole);
     } catch {
       // Silently fail for balance polling
     }
   }, [user]);

  // Fetch pending charge count for admin
  const fetchPendingChargeCount = useCallback(async () => {
    if (!user || !['system_admin', 'company_admin'].includes(user.role)) return;
    try {
      const data = await pointsApi.getChargeSummary();
      setPendingChargeCount(data.pending_count);
    } catch {
      // Silently fail for charge summary polling
    }
  }, [user]);

  // Poll balance every 60s for distributor
  useEffect(() => {
    fetchPointsBalance();
    const interval = setInterval(fetchPointsBalance, 60000);
    return () => clearInterval(interval);
  }, [fetchPointsBalance]);

  // Poll pending charge count every 60s for admin
  useEffect(() => {
    fetchPendingChargeCount();
    const interval = setInterval(fetchPendingChargeCount, 60000);
    return () => clearInterval(interval);
  }, [fetchPendingChargeCount]);

  const handleNotificationClick = async () => {
    const opening = !showNotifications;
    setShowNotifications(opening);
    if (opening) {
      try {
        const data = await notificationsApi.list({ page: 1, size: 10 });
        setNotifications(data.items);
        setUnreadCount(data.unread_count);
      } catch {
        // Silently fail
      }
    }
  };

  const handleMarkRead = async (id: number) => {
    try {
      await notificationsApi.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Silently fail
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Silently fail
    }
  };

  const toggleExpand = (path: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const filteredItems = navItems.filter(
    (item) => userRole && item.allowedRoles.includes(userRole),
  );

  const isChildActive = (item: NavItem): boolean => {
    if (!item.children) return false;
    return item.children.some(
      (child) => location.pathname === child.path || location.pathname.startsWith(child.path + '/'),
    );
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 z-50 h-full w-64 bg-sidebar text-gray-100
          border-r border-border-subtle
          transform transition-transform duration-300 ease-in-out
          lg:translate-x-0 lg:static lg:z-auto
          flex flex-col
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Logo */}
        <div className="shrink-0 flex items-center justify-between h-16 px-6 border-b border-border-subtle">
          <div className="flex items-center">
            <LogicLabLogo size={36} />
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1 rounded-lg hover:bg-sidebar-hover transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto min-h-0">
          {filteredItems.map((item, idx) => {
            // Group header: show when item has a group label
            const showGroupHeader = item.group && (
              idx === 0 || filteredItems[idx - 1]?.group !== item.group
            );
            const groupHeader = showGroupHeader ? (
              <div className={`px-3 pt-4 pb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-500 ${idx > 0 ? 'mt-2' : ''}`}>
                {item.group}
              </div>
            ) : null;
            const hasChildren = item.children && item.children.length > 0;
            const isExpanded = expandedItems.has(item.path);
            const childActive = isChildActive(item);

            if (hasChildren) {
              const filteredChildren = item.children!.filter(
                (child) => userRole && child.allowedRoles.includes(userRole),
              );

              return (
                <div key={item.path}>
                  {groupHeader}
                  {/* Parent item - clickable to expand/collapse */}
                  <button
                    onClick={() => toggleExpand(item.path)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      childActive
                        ? 'bg-sidebar-active text-gray-100'
                        : 'text-gray-300 hover:bg-sidebar-hover hover:text-gray-100'
                    }`}
                  >
                    <item.icon className="h-5 w-5 shrink-0" />
                    <span className="flex-1 text-left">{item.name}</span>
                    {isExpanded ? (
                      <ChevronDownIcon className="h-4 w-4 shrink-0" />
                    ) : (
                      <ChevronRightIcon className="h-4 w-4 shrink-0" />
                    )}
                  </button>

                  {/* Children */}
                  {isExpanded && (
                    <div className="mt-1 ml-4 space-y-1">
                      {filteredChildren.map((child) => (
                        <NavLink
                          key={child.path}
                          to={child.path}
                          onClick={onClose}
                          className={({ isActive }) =>
                            `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                              isActive
                                ? 'bg-sidebar-active text-gray-100'
                                : 'text-gray-400 hover:bg-sidebar-hover hover:text-gray-100'
                            }`
                          }
                        >
                          <child.icon className="h-4 w-4 shrink-0" />
                          {child.name}
                        </NavLink>
                      ))}
                    </div>
                  )}
                </div>
              );
            }

            // Regular item (no children)
            const showPointsBadge =
              item.path === '/points' &&
              pendingChargeCount > 0 &&
              userRole &&
              ['system_admin', 'company_admin'].includes(userRole);

            return (
              <div key={item.path}>
              {groupHeader}
              <NavLink
                to={item.path}
                end={item.path === '/' || item.path === '/orders'}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-sidebar-active text-gray-100'
                      : 'text-gray-300 hover:bg-sidebar-hover hover:text-gray-100'
                  }`
                }
              >
                <item.icon className="h-5 w-5 shrink-0" />
                <span className="flex-1">{item.name}</span>
                {showPointsBadge && (
                  <span className="flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-orange-500 rounded-full">
                    {pendingChargeCount > 99 ? '99+' : pendingChargeCount}
                  </span>
                )}
              </NavLink>
              </div>
            );
          })}
        </nav>

        {/* User Profile & Notifications */}
        <div className="shrink-0 border-t border-border-subtle p-3 space-y-1">
           {/* Points Balance for Distributor and Order Handler */}
           {(userRole === 'distributor' || userRole === 'order_handler') && pointsBalance !== null && (
             <NavLink
               to="/points"
               onClick={onClose}
               className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-primary-900/20 border border-primary-800/30 text-sm transition-colors hover:bg-primary-900/30 mb-1"
             >
               <CircleStackIcon className="h-5 w-5 shrink-0 text-primary-400" />
               <div className="flex-1 min-w-0">
                 <p className="text-[11px] text-gray-500">
                   {pointsOwnerName ? `차감 기준: ${pointsOwnerName}${pointsOwnerRole ? ` (${getRoleLabel(pointsOwnerRole)})` : ''}` : '차감 기준 포인트'}
                 </p>
                 <p className="text-sm font-bold text-primary-300">{formatNumber(pointsBalance)}P</p>
               </div>
               <span className="text-[11px] text-primary-400 font-medium whitespace-nowrap">충전 요청 →</span>
             </NavLink>
           )}

          {/* Notification button */}
          <div className="relative" ref={notificationRef}>
            <button
              onClick={handleNotificationClick}
              className="relative flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-sidebar-hover hover:text-gray-200 transition-colors"
            >
              <BellIcon className="h-5 w-5 shrink-0" />
              <span>알림</span>
              {unreadCount > 0 && (
                <span className="ml-auto flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-red-500 rounded-full">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>

            {/* Notification dropdown — opens upward */}
            {showNotifications && (
              <div className="absolute bottom-full left-0 mb-1 w-80 bg-surface rounded-xl border border-border shadow-lg overflow-hidden z-[60]">
                <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
                  <h3 className="text-sm font-semibold text-gray-100">알림</h3>
                  {unreadCount > 0 && (
                    <span className="text-xs text-gray-400">
                      {unreadCount}개 읽지 않음
                    </span>
                  )}
                </div>

                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-gray-500">
                      알림이 없습니다
                    </div>
                  ) : (
                    notifications.map((notification) => {
                      const TypeIcon = NOTIFICATION_TYPE_ICONS[notification.type] || Cog6ToothIcon;
                      const typeColor = NOTIFICATION_TYPE_COLORS[notification.type] || 'text-gray-400';

                      return (
                        <button
                          key={notification.id}
                          onClick={() => {
                            if (!notification.is_read) {
                              handleMarkRead(notification.id);
                            }
                            if (notification.type === 'order' && notification.related_id) {
                              navigate(`/orders/${notification.related_id}`);
                              setShowNotifications(false);
                              onClose();
                            } else if (notification.type === 'campaign' && notification.related_id) {
                              navigate(`/campaigns/${notification.related_id}`);
                              setShowNotifications(false);
                              onClose();
                            } else if (notification.type === 'settlement') {
                              navigate('/adjustment');
                              setShowNotifications(false);
                              onClose();
                            }
                          }}
                          className={`w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-surface-raised transition-colors border-b border-border-subtle ${
                            !notification.is_read ? 'bg-primary-900/20' : ''
                          }`}
                        >
                          <div className={`mt-0.5 shrink-0 ${typeColor}`}>
                            <TypeIcon className="h-5 w-5" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-400">
                                {getNotificationTypeLabel(notification.type)}
                              </span>
                              {!notification.is_read && (
                                <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shrink-0" />
                              )}
                            </div>
                            <p className="text-sm font-medium text-gray-100 truncate">
                              {notification.title}
                            </p>
                            <p className="text-xs text-gray-500 mt-0.5">
                              {formatRelativeTime(notification.created_at)}
                            </p>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>

                {notifications.length > 0 && (
                  <div className="px-4 py-2.5 border-t border-border-subtle">
                    <button
                      onClick={handleMarkAllRead}
                      className="w-full text-center text-xs font-medium text-primary-400 hover:text-primary-300 transition-colors"
                    >
                      전체 읽음 처리
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* User info + logout */}
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="w-8 h-8 bg-primary-900/30 rounded-full flex items-center justify-center shrink-0">
              <UserCircleIcon className="h-5 w-5 text-primary-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-200 truncate">{user?.name || '사용자'}</p>
              <p className="text-xs text-gray-500 truncate">
                {user?.role ? getRoleLabel(user.role) : ''}
              </p>
            </div>
            <button
              onClick={logout}
              className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-900/20 transition-colors"
              title="로그아웃"
            >
              <ArrowRightOnRectangleIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
