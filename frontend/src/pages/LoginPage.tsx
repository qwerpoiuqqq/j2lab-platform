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
          <div className="inline-flex items-center justify-center mb-4">
            <LogicLabLogo size={64} className="text-primary-400 drop-shadow-[0_0_12px_rgba(6,182,212,0.3)]" />
          </div>
          <h1 className="text-2xl font-bold text-gray-100" style={{ letterSpacing: '0.2em' }}>LOGIC LAB</h1>
          <p className="mt-1 text-sm text-gray-400">로직연구소</p>
          <p className="mt-1 text-xs text-gray-500">
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
