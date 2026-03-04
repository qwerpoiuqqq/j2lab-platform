import { useCallback, useEffect, useState } from 'react';
import { schedulerApi } from '@/api/scheduler';
import type { SchedulerStatus as SchedulerStatusType, SchedulerLog } from '@/types';
import Button from '@/components/common/Button';

export default function SchedulerStatus() {
  const [status, setStatus] = useState<SchedulerStatusType | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<string | null>(null);
  const [showLogs, setShowLogs] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await schedulerApi.getStatus();
      setStatus(data);
    } catch {
      // silently fail
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
      const res = await schedulerApi.trigger();
      setTriggerResult(res.message);
      await load();
    } catch {
      setTriggerResult('실행 실패');
    } finally {
      setTriggering(false);
    }
  };

  if (!status) return null;

  const statusLabel =
    status.status === 'running'
      ? '실행 중'
      : status.status === 'waiting'
        ? '대기'
        : '정지';

  const statusColor =
    status.status === 'running'
      ? 'bg-green-900/30 text-green-400'
      : status.status === 'waiting'
        ? 'bg-yellow-900/30 text-yellow-400'
        : 'bg-red-900/30 text-red-400';

  const dotColor =
    status.status === 'running'
      ? 'bg-green-500'
      : status.status === 'waiting'
        ? 'bg-yellow-500'
        : 'bg-red-500';

  return (
    <div className="bg-surface rounded-xl border border-border p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-sm text-gray-100">키워드 자동 변경</h3>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColor}`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${dotColor} ${status.status === 'running' ? 'animate-pulse' : ''}`}
            />
            {statusLabel}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="text-xs text-gray-400 hover:text-gray-200 underline"
          >
            {showLogs ? '로그 숨기기' : '로그 보기'}
          </button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleTrigger}
            loading={triggering}
            disabled={status.status === 'running'}
          >
            수동 실행
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-gray-400">마지막 실행</span>
          <div className="font-medium mt-0.5 text-gray-100">
            {status.last_run
              ? new Date(status.last_run).toLocaleString('ko-KR')
              : '없음'}
          </div>
        </div>
        <div>
          <span className="text-gray-400">실행 횟수</span>
          <div className="font-medium mt-0.5 text-gray-100">{status.execution_count}회</div>
        </div>
        <div>
          <span className="text-gray-400">키워드 변경</span>
          <div className="font-medium mt-0.5">
            <span className="text-green-600">{status.keyword_changes}건</span>
            {status.keyword_failures > 0 && (
              <span className="text-red-600 ml-1">(실패 {status.keyword_failures})</span>
            )}
          </div>
        </div>
        <div>
          <span className="text-gray-400">오늘 건너뜀</span>
          <div className="font-medium mt-0.5 text-gray-100">
            {status.skipped_today}건
          </div>
        </div>
      </div>

      {status.error_message && (
        <div className="mt-3 p-2.5 bg-red-900/20 text-red-400 text-xs rounded-lg">
          {status.error_message}
        </div>
      )}

      {triggerResult && (
        <div className="mt-3 p-2.5 bg-blue-900/20 text-blue-400 text-xs rounded-lg">
          {triggerResult}
        </div>
      )}

      {showLogs && status.recent_logs && status.recent_logs.length > 0 && (
        <div className="mt-3 p-3 bg-gray-900 text-gray-200 text-xs rounded-lg max-h-60 overflow-y-auto font-mono">
          {status.recent_logs.map((log: SchedulerLog, i: number) => (
            <div
              key={i}
              className={
                log.level === 'error'
                  ? 'text-red-400'
                  : log.level === 'warning'
                    ? 'text-yellow-400'
                    : ''
              }
            >
              [{log.timestamp}] [{log.level.toUpperCase()}] {log.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
