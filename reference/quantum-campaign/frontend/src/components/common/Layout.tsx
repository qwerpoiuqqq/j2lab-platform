import { NavLink, Outlet } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/dashboard', label: '대시보드' },
  { to: '/upload', label: '엑셀 업로드' },
  { to: '/campaigns/add', label: '캠페인 추가' },
  { to: '/settings/accounts', label: '계정 관리' },
  { to: '/settings/templates', label: '템플릿 관리' },
];

export default function Layout() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 text-white flex flex-col shrink-0">
        <div className="px-4 py-5 text-lg font-bold border-b border-gray-700">
          QCA 관리자
        </div>
        <nav className="flex-1 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-gray-700 text-white font-medium'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 text-xs text-gray-500 border-t border-gray-700">
          Quantum Campaign v1.0
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
