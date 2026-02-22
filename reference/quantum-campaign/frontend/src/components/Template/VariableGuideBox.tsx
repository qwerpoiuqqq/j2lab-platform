import type { ModuleInfo } from '../../types';

// 영문 변수명 → 한글 설명 매핑
const VARIABLE_DESCRIPTIONS: Record<string, { korean: string; description: string }> = {
  landmark_name: { korean: '명소명', description: '주변 명소 이름' },
  landmark_index: { korean: '명소순번', description: 'N번째 명소 (1부터)' },
  steps: { korean: '걸음수', description: '도보 걸음 수' },
  place_name: { korean: '상호명', description: '마스킹된 상호명' },
};

interface VariableGuideBoxProps {
  enabledModules: Set<string>;
  modules: ModuleInfo[];
}

export default function VariableGuideBox({ enabledModules, modules }: VariableGuideBoxProps) {
  const activeModules = modules.filter((m) => enabledModules.has(m.module_id));

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 sticky top-0">
      <h3 className="text-sm font-semibold text-blue-800 mb-3 flex items-center gap-1.5">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        사용 가능한 변수
      </h3>

      {/* 기본 제공 */}
      <div className="mb-3">
        <div className="text-xs font-medium text-blue-700 mb-1.5">기본 제공</div>
        <VariableItem variable="&상호명&" description="마스킹된 상호명" />
      </div>

      {/* 선택된 모듈 변수 */}
      {activeModules.length > 0 ? (
        <div className="mb-3">
          <div className="text-xs font-medium text-blue-700 mb-1.5">선택된 모듈</div>
          <div className="space-y-2.5">
            {activeModules.map((m) => (
              <div key={m.module_id}>
                <div className="text-xs text-blue-600 font-medium mb-1">{m.description}</div>
                <div className="ml-2 space-y-1">
                  {m.output_variables.map((v) => {
                    const info = VARIABLE_DESCRIPTIONS[v];
                    return (
                      <VariableItem
                        key={v}
                        variable={`&${info?.korean ?? v}&`}
                        description={info?.description ?? v}
                      />
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-xs text-blue-500 italic mb-3">
          모듈을 선택하면 추가 변수가 표시됩니다
        </div>
      )}

      {/* 사용 안내 */}
      <div className="border-t border-blue-200 pt-3 mt-3">
        <div className="text-xs text-blue-600 leading-relaxed">
          참여 방법 설명, 정답 힌트, 전환 인식 텍스트에서 사용할 수 있습니다.
        </div>
      </div>
    </div>
  );
}

function VariableItem({ variable, description }: { variable: string; description: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <code className="bg-blue-100 px-1.5 py-0.5 rounded text-blue-800 font-mono whitespace-nowrap">
        {variable}
      </code>
      <span className="text-blue-700">{description}</span>
    </div>
  );
}
