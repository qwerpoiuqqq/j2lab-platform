import type { RegistrationProgressItem } from '@/types';

interface Props {
  campaigns: RegistrationProgressItem[];
  isRegistering: boolean;
}

const STEP_LABELS: Record<string, string> = {
  queued: '대기',
  logging_in: '로그인 중',
  running_modules: '모듈 실행',
  filling_form: '폼 입력',
  submitting: '제출 중',
  extracting_code: '코드 추출',
  completed: '완료',
  failed: '실패',
};

const STEP_ORDER = ['queued', 'logging_in', 'running_modules', 'filling_form', 'submitting', 'extracting_code', 'completed'];

function StepIndicator({ step }: { step: string | null }) {
  if (!step) return <span className="text-gray-400">-</span>;

  const stepIndex = STEP_ORDER.indexOf(step);
  const totalSteps = STEP_ORDER.length - 1;
  const progress =
    step === 'completed'
      ? 100
      : step === 'failed'
        ? 0
        : Math.round((Math.max(stepIndex, 0) / totalSteps) * 100);

  const barColor =
    step === 'completed'
      ? 'bg-green-500'
      : step === 'failed'
        ? 'bg-red-500'
        : 'bg-primary-500';

  const textColor =
    step === 'completed'
      ? 'text-green-700'
      : step === 'failed'
        ? 'text-red-700'
        : 'text-primary-700';

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${progress}%` }}
        />
      </div>
      <span className={`text-xs font-medium whitespace-nowrap ${textColor}`}>
        {STEP_LABELS[step] || step}
      </span>
    </div>
  );
}

export default function RegistrationProgress({ campaigns, isRegistering }: Props) {
  if (campaigns.length === 0) return null;

  const completed = campaigns.filter((c) => c.registration_step === 'completed').length;
  const failed = campaigns.filter((c) => c.registration_step === 'failed').length;
  const total = campaigns.length;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="font-semibold text-sm text-gray-900">
          superap.io 등록 현황 ({completed}/{total} 완료
          {failed > 0 && <span className="text-red-600">, {failed} 실패</span>})
        </div>
        {isRegistering && (
          <div className="flex items-center gap-2 text-xs text-primary-600">
            <div className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" />
            처리 중...
          </div>
        )}
      </div>

      <div className="divide-y divide-gray-100">
        {campaigns.map((c) => (
          <div key={c.campaign_id} className="px-5 py-3 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm text-gray-900 truncate">
                {c.place_name || `캠페인 #${c.campaign_id}`}
              </div>
              {c.registration_message && (
                <div className="text-xs text-gray-500 mt-0.5 truncate">
                  {c.registration_message}
                </div>
              )}
            </div>
            <div className="flex-shrink-0">
              <StepIndicator step={c.registration_step} />
            </div>
            {c.campaign_code && (
              <div className="text-xs font-mono text-green-600 flex-shrink-0">
                #{c.campaign_code}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
