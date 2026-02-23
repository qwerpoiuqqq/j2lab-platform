import { NavLink } from 'react-router-dom';
import {
  HomeIcon,
  ClipboardDocumentListIcon,
  MegaphoneIcon,
  UsersIcon,
  BuildingOffice2Icon,
  CubeIcon,
  Cog6ToothIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useAuthStore } from '@/store/auth';
import type { UserRole } from '@/types';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface NavItem {
  name: string;
  path: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  allowedRoles: UserRole[];
}

const navItems: NavItem[] = [
  {
    name: '대시보드',
    path: '/',
    icon: HomeIcon,
    allowedRoles: ['system_admin', 'company_admin', 'order_handler', 'distributor', 'sub_account'],
  },
  {
    name: '주문 관리',
    path: '/orders',
    icon: ClipboardDocumentListIcon,
    allowedRoles: ['system_admin', 'company_admin', 'order_handler', 'distributor', 'sub_account'],
  },
  {
    name: '캠페인 관리',
    path: '/campaigns',
    icon: MegaphoneIcon,
    allowedRoles: ['system_admin', 'company_admin', 'order_handler'],
  },
  {
    name: '유저 관리',
    path: '/users',
    icon: UsersIcon,
    allowedRoles: ['system_admin', 'company_admin'],
  },
  {
    name: '회사 관리',
    path: '/companies',
    icon: BuildingOffice2Icon,
    allowedRoles: ['system_admin'],
  },
  {
    name: '상품 관리',
    path: '/products',
    icon: CubeIcon,
    allowedRoles: ['system_admin', 'company_admin'],
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

  const filteredItems = navItems.filter(
    (item) => userRole && item.allowedRoles.includes(userRole),
  );

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
          fixed top-0 left-0 z-50 h-full w-64 bg-sidebar text-white
          transform transition-transform duration-300 ease-in-out
          lg:translate-x-0 lg:static lg:z-auto
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center text-sm font-bold">
              J2
            </div>
            <span className="text-lg font-bold">J2LAB</span>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1 rounded-lg hover:bg-sidebar-hover transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {filteredItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-sidebar-active text-white'
                    : 'text-gray-300 hover:bg-sidebar-hover hover:text-white'
                }`
              }
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {item.name}
            </NavLink>
          ))}
        </nav>

        {/* Bottom info */}
        <div className="px-6 py-4 border-t border-white/10">
          <p className="text-xs text-gray-400">J2LAB Platform v1.0</p>
        </div>
      </aside>
    </>
  );
}
