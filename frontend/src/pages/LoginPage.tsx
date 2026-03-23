import { Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import LoginForm from '@/components/features/auth/LoginForm';
import { useAuthStore } from '@/store/auth';
import LogicLabLogo from '@/components/common/LogicLabLogo';

const STATS = [
  { value: '12,847', label: '상위노출 달성', suffix: '건' },
  { value: '3,200', label: '누적 캠페인 세팅', suffix: '건' },
  { value: '4.2', label: '평균 노출 순위', suffix: '위' },
  { value: '150', label: '운영 파트너사', suffix: '+' },
];

export default function LoginPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen flex bg-[#f2f4f6]">
      {/* 왼쪽: 소개 + 실적 */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-[55%] items-center justify-center relative overflow-hidden bg-[#191f28]">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[#3182f6]/8 rounded-full blur-[120px] translate-x-1/3 -translate-y-1/3" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-[#3182f6]/5 rounded-full blur-[100px] -translate-x-1/3 translate-y-1/3" />

        <div
          className={`relative z-10 px-12 xl:px-20 max-w-xl transition-all duration-700 ease-out ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
        >
          <div className="mb-10">
            <LogicLabLogo size={56} />
          </div>

          <h1 className="text-[36px] xl:text-[42px] font-bold text-white leading-[1.3] mb-4">
            네이버 플레이스<br />
            <span className="text-[#3182f6]">상위노출</span> 자동화
          </h1>
          <p className="text-[16px] text-[#8b95a1] mb-14 leading-relaxed">
            키워드 추출부터 캠페인 세팅까지<br />
            하나의 플랫폼에서 자동으로 관리합니다.
          </p>

          <div className="grid grid-cols-2 gap-4">
            {STATS.map((stat, i) => (
              <div
                key={stat.label}
                className={`
                  rounded-2xl border border-[#333d4b] bg-[#252b36]/60 backdrop-blur-sm p-5
                  transition-all duration-500 ease-out
                  ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}
                `}
                style={{ transitionDelay: `${200 + i * 100}ms` }}
              >
                <div className="text-[28px] xl:text-[32px] font-bold text-white tracking-tight">
                  {stat.value}
                  <span className="text-[#3182f6] text-[18px] ml-0.5 font-semibold">{stat.suffix}</span>
                </div>
                <div className="text-[13px] text-[#8b95a1] mt-1">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 오른쪽: 로그인 폼 */}
      <div className="w-full lg:w-1/2 xl:w-[45%] flex items-center justify-center px-6">
        <div
          className={`
            w-full max-w-[420px]
            transition-all duration-500 ease-out
            ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}
          `}
        >
          {/* 모바일 로고 */}
          <div className="text-center mb-6 lg:hidden">
            <div className="inline-flex items-center justify-center">
              <LogicLabLogo size={280} />
            </div>
          </div>

          {/* 데스크톱 타이틀 */}
          <div className="hidden lg:block mb-8">
            <h2 className="text-[24px] font-bold text-[#191f28]">로그인</h2>
            <p className="text-[14px] text-[#8b95a1] mt-1">계정 정보를 입력해 주세요.</p>
          </div>

          {/* 폼 카드 */}
          <div className="bg-white rounded-2xl px-8 py-10 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
            <h2 className="text-[20px] font-bold text-[#191f28] mb-6 lg:hidden">로그인</h2>
            <LoginForm />
          </div>

          <p className="mt-16 text-center text-[11px] text-[#adb5bd]">
            &copy; 2026 로직연구소 (LOGIC LAB). All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
}
