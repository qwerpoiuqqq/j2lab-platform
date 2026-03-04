import { Navigate } from 'react-router-dom';
import LoginForm from '@/components/features/auth/LoginForm';
import { useAuthStore } from '@/store/auth';
import LogicLabLogo from '@/components/common/LogicLabLogo';

export default function LoginPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-overlay px-4">
      <div className="w-full max-w-md animate-in fade-in slide-in-from-bottom-4 duration-500">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center mb-3">
            <LogicLabLogo size={140} />
          </div>
          <p className="text-xs text-gray-500">
            광고 자동화 플랫폼
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-surface rounded-2xl border border-border p-8 shadow-xl shadow-black/20">
          <h2 className="text-lg font-semibold text-gray-100 mb-6">로그인</h2>
          <LoginForm />
        </div>

        <p className="mt-6 text-center text-xs text-gray-600">
          &copy; 2026 로직연구소 (LOGIC LAB). All rights reserved.
        </p>
      </div>
    </div>
  );
}
