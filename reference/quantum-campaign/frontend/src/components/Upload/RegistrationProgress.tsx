import type { RegistrationProgressItem, RegistrationStep } from '../../types';
import { REGISTRATION_STEP_LABELS, REGISTRATION_STEP_ORDER } from '../../types';

interface Props {
  campaigns: RegistrationProgressItem[];
  isRegistering: boolean;
}

function StepIndicator({ step }: { step: RegistrationStep | null }) {
  if (!step) return <span className="text-gray-400">-</span>;

  const stepIndex = REGISTRATION_STEP_ORDER.indexOf(step as RegistrationStep);
  const totalSteps = REGISTRATION_STEP_ORDER.length - 1;
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
        : 'bg-blue-500';

  const textColor =
    step === 'completed'
      ? 'text-green-700'
      : step === 'failed'
        ? 'text-red-700'
        : 'text-blue-700';

  return (
    <div className="flex items-center gap-2">
      <div className="w-24 bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${progress}%` }}
        />
      </div>
      <span className={`text-xs font-medium whitespace-nowrap ${textColor}`}>
        {REGISTRATION_STEP_LABELS[step as RegistrationStep] || step}
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
    <div className="bg-white rounded-lg shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <div className="font-medium text-sm">
          superap.io 등록 현황 ({completed}/{total} 완료
          {failed > 0 && <span className="text-red-600">, {failed} 실패</span>})
        </div>
        {isRegistering && (
          <div className="flex items-center gap-2 text-xs text-blue-600">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            처리 중...
          </div>
        )}
      </div>

      <div className="divide-y divide-gray-100">
        {campaigns.map((c) => (
          <div key={c.campaign_id} className="px-4 py-3 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm truncate">{c.place_name || `캠페인 #${c.campaign_id}`}</div>
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
