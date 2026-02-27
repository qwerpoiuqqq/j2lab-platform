import { Link } from 'react-router-dom';
import type { KeywordWarning } from '@/types';

interface Props {
  warnings: KeywordWarning[];
}

export default function KeywordWarnings({ warnings }: Props) {
  if (warnings.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">키워드 부족 경고</h3>
        <p className="text-sm text-gray-400">키워드가 부족한 캠페인이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">
        키워드 부족 경고 <span className="text-gray-400 font-normal">({warnings.length})</span>
      </h3>
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {warnings.map((w) => (
          <div
            key={w.campaign_id}
            className="flex items-center justify-between p-2.5 rounded-lg border border-gray-100 hover:bg-gray-50"
          >
            <div>
              <Link to={`/campaigns/${w.campaign_id}`} className="text-xs font-medium text-gray-900 hover:text-primary-600 hover:underline">{w.place_name}</Link>
              {w.campaign_code && (
                <p className="text-[10px] text-gray-400 font-mono">{w.campaign_code}</p>
              )}
            </div>
            <div className="text-right">
              <span
                className={`text-xs font-medium ${
                  w.remaining === 0 ? 'text-red-600' : 'text-orange-600'
                }`}
              >
                {w.remaining}/{w.total}
              </span>
              <p className="text-[10px] text-gray-400">남은 키워드</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
