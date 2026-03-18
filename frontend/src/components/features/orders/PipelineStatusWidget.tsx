import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Badge from '@/components/common/Badge';
import Button from '@/components/common/Button';
import { ChevronDownIcon, ChevronUpIcon, PlayIcon } from '@heroicons/react/24/outline';
import { assignmentsApi, type AssignmentQueueItem } from '@/api/assignments';
import { pipelineApi, type PipelineLogItem } from '@/api/pipeline';
import { useAuthStore } from '@/store/auth';
import type { PipelineState } from '@/types';
import { getCampaignTypeLabel } from '@/utils/format';

const TRIGGER_TYPE_LABELS: Record<string, string> = {
  user_action: '사용자 작업',
  auto_extraction_dispatch: '자동 키워드 추출',
  auto_assignment: '자동 계정 배정',
  auto_campaign_register: '자동 캠페인 등록',
  auto_extraction_running: '추출 진행',
  auto_extraction_complete: '추출 완료',
  auto_registration_complete: '등록 완료',
  auto_dispatch: '자동 세팅 진행',
  validation_error: '검증 오류',
  extraction_failed: '추출 실패',
  campaign_failed: '캠페인 실패',
  payment_confirmed: '입금 확인',
  user_choice_extend: '연장 선택',
  extend_fallback: '연장 대체',
  scheduler: '스케줄러',
  system: '시스템',
};

const PIPELINE_STAGES = [
  { key: 'draft', label: '임시저장' },
  { key: 'submitted', label: '제출' },
  { key: 'payment_confirmed', label: '입금확인' },
  { key: 'extraction_queued', label: '추출대기' },
  { key: 'extraction_running', label: '추출중' },
  { key: 'extraction_done', label: '추출완료' },
  { key: 'account_assigned', label: '계정배정' },
  { key: 'assignment_confirmed', label: '배정확인' },
  { key: 'campaign_registering', label: '등록중' },
  { key: 'campaign_active', label: '캠페인활성' },
  { key: 'management', label: '운영중' },
  { key: 'completed', label: '완료' },
  { key: 'failed', label: '실패' },
  { key: 'cancelled', label: '취소' },
];

// Map pipeline_state.current_stage values to PIPELINE_STAGES keys
// Backend PipelineStage enum values match display keys directly
const STAGE_KEY_MAP: Record<string, string> = {
  draft: 'draft',
  submitted: 'submitted',
  payment_confirmed: 'payment_confirmed',
  extraction_queued: 'extraction_queued',
  extraction_running: 'extraction_running',
  extraction_done: 'extraction_done',
  account_assigned: 'account_assigned',
  assignment_confirmed: 'assignment_confirmed',
  campaign_registering: 'campaign_registering',
  campaign_active: 'campaign_active',
  management: 'management',
  completed: 'completed',
  failed: 'failed',
  cancelled: 'cancelled',
};

interface Props {
  orderItemId: number;
  extractionJobId?: number;
  campaignId?: number;
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return ts;
  }
}

function getStageStatus(
  stageKey: string,
  currentStageKey: string,
  isFailed: boolean,
  isCancelled: boolean,
): 'passed' | 'current' | 'future' | 'failed' | 'cancelled' {
  if (stageKey === 'failed' && isFailed) return 'failed';
  if (stageKey === 'cancelled' && isCancelled) return 'cancelled';

  // For terminal error stages, skip them if not relevant
  if (stageKey === 'failed' && !isFailed) return 'future';
  if (stageKey === 'cancelled' && !isCancelled) return 'future';

  const mainStages = PIPELINE_STAGES.filter(
    (s) => s.key !== 'failed' && s.key !== 'cancelled',
  );
  const currentIdx = mainStages.findIndex((s) => s.key === currentStageKey);
  const stageIdx = mainStages.findIndex((s) => s.key === stageKey);

  if (currentIdx < 0 || stageIdx < 0) return 'future';
  if (stageIdx < currentIdx) return 'passed';
  if (stageIdx === currentIdx) return 'current';
  return 'future';
}

function getStageColor(status: 'passed' | 'current' | 'future' | 'failed' | 'cancelled'): string {
  switch (status) {
    case 'passed':
      return 'bg-green-500 text-white';
    case 'current':
      return 'bg-blue-500 text-white ring-2 ring-blue-300';
    case 'failed':
      return 'bg-red-500 text-white';
    case 'cancelled':
      return 'bg-red-400 text-white';
    case 'future':
    default:
      return 'bg-surface-overlay text-gray-400';
  }
}

function getConnectorColor(status: 'passed' | 'current' | 'future' | 'failed' | 'cancelled'): string {
  switch (status) {
    case 'passed':
      return 'bg-green-500';
    case 'current':
      return 'bg-blue-500';
    default:
      return 'bg-surface-overlay';
  }
}

export default function PipelineStatusWidget({ orderItemId, extractionJobId, campaignId }: Props) {
  const [pipelineState, setPipelineState] = useState<PipelineState | null>(null);
  const [assignmentItem, setAssignmentItem] = useState<AssignmentQueueItem | null>(null);
  const [logs, setLogs] = useState<PipelineLogItem[]>([]);
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingExtraction, setStartingExtraction] = useState(false);
  const [choosingAction, setChoosingAction] = useState<'new' | 'extend' | null>(null);
  const user = useAuthStore((s) => s.user);
  const canStartExtraction = user && ['system_admin', 'company_admin', 'order_handler'].includes(user.role);
  const canManageAssignment = canStartExtraction;

  const fetchPipeline = useCallback(async () => {
    setError(null);
    const state = await pipelineApi.getState(orderItemId);
    setPipelineState(state);
    return state;
  }, [orderItemId]);

  const fetchAssignmentItem = useCallback(async () => {
    if (!canManageAssignment) {
      setAssignmentItem(null);
      return null;
    }

    try {
      const response = await assignmentsApi.getQueue({
        order_item_id: orderItemId,
        limit: 1,
      });
      const item = response.items[0] ?? null;
      setAssignmentItem(item);
      return item;
    } catch {
      setAssignmentItem(null);
      return null;
    }
  }, [canManageAssignment, orderItemId]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const state = await fetchPipeline();
        if (!cancelled) {
          if (
            canManageAssignment
            && ['account_assigned', 'assignment_confirmed', 'campaign_registering'].includes(state.current_stage)
          ) {
            await fetchAssignmentItem();
          } else {
            setAssignmentItem(null);
          }
        }
      } catch (err: any) {
        if (!cancelled) {
          // 404 is expected if pipeline not started yet
          if (err?.response?.status === 404) {
            setPipelineState(null);
          } else {
            setError('파이프라인 상태를 불러오지 못했습니다.');
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [canManageAssignment, fetchAssignmentItem, fetchPipeline]);

  useEffect(() => {
    if (!logsExpanded || !pipelineState) return;
    let cancelled = false;

    async function fetchLogs() {
      try {
        const resp = await pipelineApi.getLogs(orderItemId);
        if (!cancelled) {
          setLogs(resp.items);
        }
      } catch {
        // Silently ignore log fetch errors
      }
    }

    fetchLogs();
    return () => {
      cancelled = true;
    };
  }, [logsExpanded, orderItemId, pipelineState]);

  if (loading) {
    return (
      <div className="bg-surface-raised rounded-lg p-4">
        <div className="animate-pulse flex space-x-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-6 w-16 bg-surface-overlay rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 rounded-lg p-4">
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  if (!pipelineState) {
    return (
      <div className="bg-surface-raised rounded-lg p-4">
        <p className="text-sm text-gray-400">파이프라인이 아직 시작되지 않았습니다.</p>
      </div>
    );
  }

  const currentStage = pipelineState.current_stage;
  const mappedKey = STAGE_KEY_MAP[currentStage] || currentStage;
  const isFailed = currentStage === 'failed';
  const isCancelled = currentStage === 'cancelled';

  // Show only the main flow stages (not failed/cancelled unless relevant)
  const displayStages = PIPELINE_STAGES.filter((s) => {
    if (s.key === 'failed') return isFailed;
    if (s.key === 'cancelled') return isCancelled;
    return true;
  });

  const effectiveExtractionJobId = extractionJobId ?? pipelineState.extraction_job_id;
  const effectiveCampaignId = campaignId ?? pipelineState.campaign_id;
  const isExtendRecommended = assignmentItem?.ai_recommendation === 'extend' && assignmentItem.extend_target_campaign_id != null;

  const handleChooseAssignment = async (action: 'new' | 'extend') => {
    setChoosingAction(action);
    try {
      await assignmentsApi.choose(orderItemId, action);
      await Promise.all([fetchPipeline(), fetchAssignmentItem()]);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '세팅 선택에 실패했습니다.');
    } finally {
      setChoosingAction(null);
    }
  };

  return (
    <div className="bg-surface-raised rounded-lg p-4 space-y-3">
      {/* Progress stepper */}
      <div className="flex items-center overflow-x-auto pb-2 gap-0">
        {displayStages.map((stage, idx) => {
          const status = getStageStatus(stage.key, mappedKey, isFailed, isCancelled);
          return (
            <div key={stage.key} className="flex items-center shrink-0">
              {idx > 0 && (
                <div className={`w-4 h-0.5 ${getConnectorColor(status)}`} />
              )}
              <div className="flex flex-col items-center">
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${getStageColor(status)}`}
                  title={stage.label}
                >
                  {status === 'passed' ? (
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : status === 'failed' || status === 'cancelled' ? (
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    idx + 1
                  )}
                </div>
                <span className="text-[10px] text-gray-400 mt-1 whitespace-nowrap">
                  {stage.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Manual extraction start button */}
      {currentStage === 'payment_confirmed' && canStartExtraction && (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="primary"
            loading={startingExtraction}
            icon={<PlayIcon className="h-3.5 w-3.5" />}
            onClick={async () => {
              setStartingExtraction(true);
              try {
                await pipelineApi.startExtraction(orderItemId);
                const updated = await pipelineApi.getState(orderItemId);
                setPipelineState(updated);
              } catch (err: any) {
                alert(err?.response?.data?.detail || '세팅 시작에 실패했습니다.');
              } finally {
                setStartingExtraction(false);
              }
            }}
          >
            세팅 시작
          </Button>
          <span className="text-xs text-gray-400">마감시간 전에 수동으로 키워드 추출을 시작합니다</span>
        </div>
      )}

      {assignmentItem?.assignment_status === 'auto_assigned' && canManageAssignment && (
        <div className="rounded-lg border border-border bg-surface p-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400">
            <span>배정 계정: <span className="font-medium text-gray-200">{assignmentItem.assigned_account_name || '-'}</span></span>
            {assignmentItem.campaign_type && (
              <span>유형: <span className="font-medium text-gray-200">{getCampaignTypeLabel(assignmentItem.campaign_type)}</span></span>
            )}
            <Badge variant={isExtendRecommended ? 'info' : 'default'}>
              {isExtendRecommended ? '연장 추천' : '신규 세팅'}
            </Badge>
          </div>

          {assignmentItem.extend_target_info && (
            <div className="text-xs text-gray-400 rounded-md bg-surface-raised px-3 py-2">
              기존 캠페인 #{assignmentItem.extend_target_info.campaign_id}
              {assignmentItem.extend_target_info.total_limit != null && (
                <span> / 총 한도 {assignmentItem.extend_target_info.total_limit.toLocaleString()}</span>
              )}
              {assignmentItem.extend_target_info.end_date && (
                <span> / 종료일 {assignmentItem.extend_target_info.end_date}</span>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {isExtendRecommended && (
              <Button
                size="sm"
                variant="primary"
                loading={choosingAction === 'extend'}
                onClick={() => handleChooseAssignment('extend')}
              >
                연장 세팅
              </Button>
            )}
            <Button
              size="sm"
              variant="success"
              loading={choosingAction === 'new'}
              onClick={() => handleChooseAssignment('new')}
            >
              신규 세팅
            </Button>
          </div>
        </div>
      )}

      {/* Error message */}
      {pipelineState.error_message && (
        <div className="bg-red-900/20 border border-red-800/50 rounded p-2">
          <p className="text-xs text-red-400">{pipelineState.error_message}</p>
        </div>
      )}

      {/* Links */}
      <div className="flex gap-3 text-xs">
        {effectiveExtractionJobId && (
          <span className="text-gray-400">
            추출 작업:{' '}
            <span className="text-primary-600 font-medium">
              #{effectiveExtractionJobId}
            </span>
          </span>
        )}
        {effectiveCampaignId && (
          <Link
            to={`/campaigns/${effectiveCampaignId}`}
            className="text-primary-600 hover:underline font-medium"
          >
            캠페인 #{effectiveCampaignId}
          </Link>
        )}
      </div>

      {/* Collapsible timeline logs — hidden for distributor/sub_account */}
      {user && !['distributor', 'sub_account'].includes(user.role) && (
        <>
          <button
            onClick={() => setLogsExpanded((prev) => !prev)}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-300 transition-colors"
          >
            {logsExpanded ? (
              <ChevronUpIcon className="w-3.5 h-3.5" />
            ) : (
              <ChevronDownIcon className="w-3.5 h-3.5" />
            )}
            타임라인 로그
          </button>

          {logsExpanded && (
            <div className="border-l-2 border-border ml-2 pl-3 space-y-2 max-h-60 overflow-y-auto">
              {logs.length === 0 ? (
                <p className="text-xs text-gray-400">로그가 없습니다.</p>
              ) : (
                logs.map((log) => (
                  <div key={log.id} className="text-xs">
                    <div className="flex items-center gap-2">
                      <Badge variant={log.to_stage === 'failed' ? 'danger' : 'default'}>
                        {log.from_stage ? `${log.from_stage} → ${log.to_stage}` : log.to_stage}
                      </Badge>
                      {log.trigger_type && (
                        <span className="text-gray-400">
                          [{TRIGGER_TYPE_LABELS[log.trigger_type] || log.trigger_type}]
                        </span>
                      )}
                      {log.actor_name && (
                        <span className="text-gray-300">담당자: {log.actor_name}</span>
                      )}
                    </div>
                    {log.message && (
                      <p className="text-gray-400 mt-0.5">{log.message}</p>
                    )}
                    <p className="text-gray-400 mt-0.5">
                      {formatTimestamp(log.created_at)}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
