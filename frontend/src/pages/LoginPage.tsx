import { Navigate } from 'react-router-dom';
import LoginForm from '@/components/features/auth/LoginForm';
import { useAuthStore } from '@/store/auth';

export default function LoginPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-primary-600 rounded-xl flex items-center justify-center text-white text-xl font-bold">
              J2
            </div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">J2LAB Platform</h1>
          <p className="mt-2 text-sm text-gray-500">
            네이버 플레이스 광고 자동화 플랫폼
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">로그인</h2>
          <LoginForm />
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          &copy; 2026 J2LAB. All rights reserved.
        </p>
      </div>
    </div>
  );
}
