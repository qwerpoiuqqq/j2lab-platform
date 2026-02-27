import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bars3Icon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  BellIcon,
  ClipboardDocumentListIcon,
  MegaphoneIcon,
  Cog6ToothIcon,
  BanknotesIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '@/hooks/useAuth';
import { getRoleLabel, formatRelativeTime, getNotificationTypeLabel } from '@/utils/format';
import { notificationsApi } from '@/api/notifications';
import type { Notification } from '@/types';

interface HeaderProps {
  onMenuClick: () => void;
}

const NOTIFICATION_TYPE_ICONS: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  order: ClipboardDocumentListIcon,
  campaign: MegaphoneIcon,
  system: Cog6ToothIcon,
  settlement: BanknotesIcon,
};

const NOTIFICATION_TYPE_COLORS: Record<string, string> = {
  order: 'text-blue-500',
  campaign: 'text-green-500',
  system: 'text-gray-500',
  settlement: 'text-purple-500',
};

export default function Header({ onMenuClick }: HeaderProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showDropdown, setShowDropdown] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const notificationRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
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

  // Fetch recent notifications when dropdown opens
  const handleNotificationClick = async () => {
    const opening = !showNotifications;
    setShowNotifications(opening);
    setShowDropdown(false);

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

  // Mark single notification as read
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

  // Mark all as read
  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Silently fail
    }
  };

  return (
    <header className="sticky top-0 z-30 h-16 bg-white border-b border-gray-200 px-4 lg:px-6">
      <div className="flex items-center justify-between h-full">
        {/* Left */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
          >
            <Bars3Icon className="h-5 w-5" />
          </button>
        </div>

        {/* Right - Notifications + User menu */}
        <div className="flex items-center gap-2">
          {/* Notification Bell */}
          <div className="relative" ref={notificationRef}>
            <button
              onClick={handleNotificationClick}
              className="relative p-2 rounded-lg text-gray-500 hover:bg-gray-100 transition-colors"
            >
              <BellIcon className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-red-500 rounded-full">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </button>

            {/* Notification Dropdown */}
            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl border border-gray-200 shadow-lg overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                  <h3 className="text-sm font-semibold text-gray-900">알림</h3>
                  {unreadCount > 0 && (
                    <span className="text-xs text-gray-500">
                      {unreadCount}개 읽지 않음
                    </span>
                  )}
                </div>

                <div className="max-h-80 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-gray-400">
                      알림이 없습니다
                    </div>
                  ) : (
                    notifications.map((notification) => {
                      const TypeIcon = NOTIFICATION_TYPE_ICONS[notification.type] || Cog6ToothIcon;
                      const typeColor = NOTIFICATION_TYPE_COLORS[notification.type] || 'text-gray-500';

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
                            } else if (notification.type === 'campaign' && notification.related_id) {
                              navigate(`/campaigns/${notification.related_id}`);
                              setShowNotifications(false);
                            } else if (notification.type === 'settlement') {
                              navigate('/settlements');
                              setShowNotifications(false);
                            }
                          }}
                          className={`w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors border-b border-gray-50 ${
                            !notification.is_read ? 'bg-blue-50/50' : ''
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
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
                              )}
                            </div>
                            <p className="text-sm font-medium text-gray-900 truncate">
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
                  <div className="px-4 py-2.5 border-t border-gray-100">
                    <button
                      onClick={handleMarkAllRead}
                      className="w-full text-center text-xs font-medium text-primary-600 hover:text-primary-700 transition-colors"
                    >
                      전체 읽음 처리
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* User menu */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => {
                setShowDropdown(!showDropdown);
                setShowNotifications(false);
              }}
              className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <div className="text-right hidden sm:block">
                <p className="text-sm font-medium text-gray-700">
                  {user?.name || '사용자'}
                </p>
                <p className="text-xs text-gray-500">
                  {user?.role ? getRoleLabel(user.role) : ''}
                  {user?.company ? ` - ${user.company.name}` : ''}
                </p>
              </div>
              <div className="w-9 h-9 bg-primary-100 rounded-full flex items-center justify-center">
                <UserCircleIcon className="h-6 w-6 text-primary-600" />
              </div>
            </button>

            {/* Dropdown */}
            {showDropdown && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl border border-gray-200 shadow-lg py-1">
                <div className="px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-900">
                    {user?.name}
                  </p>
                  <p className="text-xs text-gray-500">{user?.email}</p>
                </div>
                <button
                  onClick={() => {
                    setShowDropdown(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  <ArrowRightOnRectangleIcon className="h-4 w-4" />
                  로그아웃
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
