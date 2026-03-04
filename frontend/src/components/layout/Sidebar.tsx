import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
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
  DocumentTextIcon,
  PlusCircleIcon,
  ArrowUpTrayIcon,
  UserGroupIcon,
  SwatchIcon,
  CurrencyDollarIcon,
  TagIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ChartBarIcon,
  LockClosedIcon,
  SignalIcon,
} from '@heroicons/react/24/outline';
import { useAuthStore } from '@/store/auth';
import type { UserRole } from '@/types';
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
}

const ALL_ROLES: UserRole[] = ['system_admin', 'company_admin', 'order_handler', 'distributor', 'sub_account'];

const navItems: NavItem[] = [
  {
    name: '대시보드',
    path: '/',
    icon: HomeIcon,
    allowedRoles: ALL_ROLES,
  },
  {
    name: '주문 접수',
    path: '/orders/grid',
    icon: TableCellsIcon,
    allowedRoles: ['system_admin', 'company_admin', 'distributor', 'sub_account'],
  },
  {
    name: '주문 내역',
    path: '/orders',
    icon: ClipboardDocumentListIcon,
    allowedRoles: ALL_ROLES,
  },
  {
    name: '캠페인 관리',
    path: '/campaigns',
    icon: MegaphoneIcon,
    allowedRoles: ['system_admin', 'company_admin', 'order_handler'],
    children: [
      {
        name: '캠페인 대시보드',
        path: '/campaigns',
        icon: ChartBarIcon,
        allowedRoles: ['system_admin', 'company_admin', 'order_handler'],
      },
      {
        name: '캠페인 추가',
        path: '/campaigns/add',
        icon: PlusCircleIcon,
        allowedRoles: ['system_admin', 'company_admin', 'order_handler'],
      },
      {
        name: '엑셀 업로드',
        path: '/campaigns/upload',
        icon: ArrowUpTrayIcon,
        allowedRoles: ['system_admin', 'company_admin', 'order_handler'],
      },
      {
        name: '계정 관리',
        path: '/campaigns/accounts',
        icon: UserGroupIcon,
        allowedRoles: ['system_admin', 'company_admin', 'order_handler'],
      },
      {
        name: '템플릿 관리',
        path: '/campaigns/templates',
        icon: SwatchIcon,
        allowedRoles: ['system_admin', 'company_admin', 'order_handler'],
      },
    ],
  },
  {
    name: '상품 관리',
    path: '/products',
    icon: CubeIcon,
    allowedRoles: ['system_admin', 'company_admin'],
    children: [
      {
        name: '상품 목록',
        path: '/products',
        icon: CubeIcon,
        allowedRoles: ['system_admin', 'company_admin'],
      },
      {
        name: '단가 설정',
        path: '/products/prices/matrix',
        icon: CurrencyDollarIcon,
        allowedRoles: ['system_admin', 'company_admin'],
      },
      {
        name: '카테고리',
        path: '/products/categories',
        icon: TagIcon,
        allowedRoles: ['system_admin', 'company_admin'],
      },
      {
        name: '일류 리워드 설정',
        path: '/products/reward-settings',
        icon: SignalIcon,
        allowedRoles: ['system_admin', 'company_admin'],
      },
    ],
  },
  {
    name: '유저 관리',
    path: '/users',
    icon: UsersIcon,
    allowedRoles: ['system_admin', 'company_admin'],
  },
  {
    name: '하부계정 관리',
    path: '/sub-accounts',
    icon: UserGroupIcon,
    allowedRoles: ['system_admin', 'company_admin', 'distributor'],
  },
  {
    name: '회사 관리',
    path: '/companies',
    icon: BuildingOffice2Icon,
    allowedRoles: ['system_admin'],
  },
  {
    name: '정산 관리',
    path: '/settlements',
    icon: BanknotesIcon,
    allowedRoles: ['system_admin', 'company_admin'],
    children: [
      {
        name: '정산 현황',
        path: '/settlements',
        icon: BanknotesIcon,
        allowedRoles: ['system_admin', 'company_admin'],
      },
      {
        name: '수익 분석',
        path: '/settlements/secret',
        icon: LockClosedIcon,
        allowedRoles: ['system_admin'],
      },
    ],
  },
  {
    name: '마감 캘린더',
    path: '/calendar',
    icon: CalendarIcon,
    allowedRoles: ['system_admin', 'company_admin', 'order_handler', 'distributor'],
  },
  {
    name: '공지사항',
    path: '/notices',
    icon: DocumentTextIcon,
    allowedRoles: ALL_ROLES,
  },
  {
    name: '시스템 설정',
    path: '/settings',
    icon: Cog6ToothIcon,
    allowedRoles: ['system_admin'],
  },
];

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const user = useAuthStore((s) => s.user);
  const userRole = user?.role;
  const location = useLocation();

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
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-border-subtle">
          <div className="flex items-center gap-3">
            <LogicLabLogo size={28} className="text-primary-400" />
            <span className="text-sm font-bold tracking-widest text-gray-100">LOGIC LAB</span>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1 rounded-lg hover:bg-sidebar-hover transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 8rem)' }}>
          {filteredItems.map((item) => {
            const hasChildren = item.children && item.children.length > 0;
            const isExpanded = expandedItems.has(item.path);
            const childActive = isChildActive(item);

            if (hasChildren) {
              const filteredChildren = item.children!.filter(
                (child) => userRole && child.allowedRoles.includes(userRole),
              );

              return (
                <div key={item.path}>
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
            return (
              <NavLink
                key={item.path}
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
                {item.name}
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom info */}
        <div className="px-6 py-4 border-t border-border-subtle">
          <p className="text-xs text-gray-500">LOGIC LAB v1.0</p>
        </div>
      </aside>
    </>
  );
}
