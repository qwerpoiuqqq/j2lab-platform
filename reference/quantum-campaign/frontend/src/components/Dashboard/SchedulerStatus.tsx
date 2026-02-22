import { useCallback, useEffect, useState } from 'react';
import type { SchedulerStatus as SchedulerStatusType } from '../../types';
import { fetchSchedulerStatus, triggerScheduler } from '../../services/api';

export default function SchedulerStatus() {
  const [status, setStatus] = useState<SchedulerStatusType | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const [showLogs, setShowLogs] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchSchedulerStatus();
      setStatus(data);
    } catch {
      // 조용히 실패
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, [load]);

  const handleTrigger = async () => {
    setTriggering(true);
    setTriggerResult(null);
    try {
      const res = await triggerScheduler();
      setTriggerResult(res.message);
      await load();
    } catch {
      setTriggerResult('실행 실패');
    } finally {
      setTriggering(false);
    }
  };

  if (!status) return null;

  const lastResult = status.last_result as Record<string, number | string[]> | null;

  return (
    <div className="bg-white rounded-lg shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="font-medium text-sm">키워드 자동 변경</h3>
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
              status.scheduler_active
                ? 'bg-green-100 text-green-700'
                : 'bg-red-100 text-red-700'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                status.scheduler_active ? 'bg-green-500' : 'bg-red-500'
              } ${status.is_running ? 'animate-pulse' : ''}`}
            />
            {status.is_running ? '실행 중' : status.scheduler_active ? '대기' : '정지'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            {showLogs ? '로그 숨기기' : '로그 보기'}
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggering || status.is_running}
            className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {triggering ? '실행 중...' : '수동 실행'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 text-xs">
        <div>
          <span className="text-gray-500">마지막 실행</span>
          <div className="font-medium mt-0.5">
            {status.last_run
              ? new Date(status.last_run).toLocaleString('ko-KR')
              : '없음'}
          </div>
        </div>
        <div>
          <span className="text-gray-500">실행 횟수</span>
          <div className="font-medium mt-0.5">{status.run_count}회</div>
        </div>
        <div>
          <span className="text-gray-500">키워드 변경</span>
          <div className="font-medium mt-0.5">
            {lastResult ? (
              <>
                <span className="text-green-600">{lastResult.rotated ?? 0}건</span>
                {(lastResult.rotation_failed as number) > 0 && (
                  <span className="text-red-600 ml-1">
                    (실패 {lastResult.rotation_failed})
                  </span>
                )}
              </>
            ) : (
              '-'
            )}
          </div>
        </div>
        <div>
          <span className="text-gray-500">오늘 건너뜀</span>
          <div className="font-medium mt-0.5">
            {lastResult ? `${lastResult.skipped_today ?? 0}건` : '-'}
          </div>
        </div>
      </div>

      {status.last_error && (
        <div className="mt-2 p-2 bg-red-50 text-red-700 text-xs rounded">
          {status.last_error}
        </div>
      )}

      {triggerResult && (
        <div className="mt-2 p-2 bg-blue-50 text-blue-700 text-xs rounded">
          {triggerResult}
        </div>
      )}

      {showLogs && status.recent_logs.length > 0 && (
        <div className="mt-3 p-2 bg-gray-900 text-gray-200 text-xs rounded max-h-60 overflow-y-auto font-mono">
          {status.recent_logs.map((log, i) => (
            <div
              key={i}
              className={
                log.includes('[ERROR]')
                  ? 'text-red-400'
                  : log.includes('[WARNING]')
                    ? 'text-yellow-400'
                    : ''
              }
            >
              {log}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
