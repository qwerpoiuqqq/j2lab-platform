import { useState, type FormEvent } from 'react';
import LoginInput from './LoginInput';
import LoginToggle from './LoginToggle';
import { useAuth } from '@/hooks/useAuth';

export default function LoginForm() {
  const { login } = useAuth();
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login({ login_id: loginId, password }, rememberMe);
    } catch {
      setError('아이디 또는 비밀번호가 올바르지 않습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {error && (
        <div role="alert" className="flex items-center gap-2">
          <svg aria-hidden="true" className="w-4 h-4 text-[#f04452] shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
          </svg>
          <p className="text-sm text-[#f04452]">{error}</p>
        </div>
      )}

      <LoginInput
        label="아이디"
        type="text"
        value={loginId}
        onChange={(e) => setLoginId(e.target.value)}
        required
        autoComplete="username"
      />

      <LoginInput
        label="비밀번호"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        autoComplete="current-password"
      />

      <LoginToggle
        label="로그인 유지"
        checked={rememberMe}
        onChange={setRememberMe}
      />

      <button
        type="submit"
        disabled={loading || !loginId || !password}
        className="
          w-full h-14 rounded-2xl
          bg-[#3182f6] hover:bg-[#1b64da]
          text-white font-semibold text-base
          transition-colors duration-200
          active:opacity-90
          disabled:opacity-50 disabled:cursor-not-allowed
          flex items-center justify-center gap-2
        "
      >
        {loading ? (
          <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        ) : '로그인'}
      </button>
    </form>
  );
}
