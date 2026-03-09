import { useState } from 'react';
import type { CampaignListItem } from '@/types';
import { getCampaignExtendedStatusLabel, getCampaignExtendedStatusColor, getKeywordStatusLabel, getKeywordStatusColor } from '@/utils/format';
import Pagination from '@/components/common/Pagination';
import CampaignDetailModal from './CampaignDetailModal';
import CampaignEditModal from './CampaignEditModal';
import KeywordAddModal from './KeywordAddModal';
import { campaignsApi } from '@/api/campaigns';

interface CampaignTableProps {
  campaigns: CampaignListItem[];
  loading: boolean;
  page: number;
  totalPages: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
}

function fmtDate(dateStr: string | null | undefined) {
  if (!dateStr) return '-';
  return dateStr.slice(5, 10).replace('-', '/');
}

function StatusBadge({ status, registrationStep }: { status: string; registrationStep?: string | null }) {
  if (status === 'pending' && registrationStep === 'failed') {
    return (
      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-red-900/30 text-red-400">
        등록실패
      </span>
    );
  }
  if (status === 'pending' && registrationStep && registrationStep !== 'completed') {
    return (
      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-900/30 text-yellow-400">
        등록중
      </span>
    );
  }
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${getCampaignExtendedStatusColor(status)}`}>
      {getCampaignExtendedStatusLabel(status)}
    </span>
  );
}

export default function CampaignTable({
  campaigns,
  loading,
  page,
  totalPages,
  totalItems,
  onPageChange,
  onRefresh,
}: CampaignTableProps) {
  const [keywordModal, setKeywordModal] = useState<{ id: number; name: string } | null>(null);
  const [editModal, setEditModal] = useState<CampaignListItem | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === campaigns.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(campaigns.map((c) => c.id)));
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`'${name}' 캠페인을 삭제하시겠습니까?`)) return;
    try {
      setDeleting(true);
      await campaignsApi.delete(id);
      setSelected((prev) => { const next = new Set(prev); next.delete(id); return next; });
      onRefresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '삭제 실패');
    } finally {
      setDeleting(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selected.size === 0) return;
    if (!confirm(`선택한 ${selected.size}개 캠페인을 삭제하시겠습니까?`)) return;
    try {
      setDeleting(true);
      await campaignsApi.batchDelete([...selected]);
      setSelected(new Set());
      onRefresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '삭제 실패');
    } finally {
      setDeleting(false);
    }
  };

  const handleRetry = async (id: number) => {
    try {
      setRetrying(true);
      await campaignsApi.retryRegistration(id);
      onRefresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '재시도 실패');
    } finally {
      setRetrying(false);
    }
  };

  const handleRegister = async (id: number) => {
    try {
      setActionLoading(id);
      await campaignsApi.register(id);
      onRefresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '등록 실패');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRotateKeywords = async (id: number) => {
    try {
      setActionLoading(id);
      await campaignsApi.rotateKeywords(id);
      onRefresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '키워드 로테이션 실패');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSync = async (id: number) => {
    try {
      setActionLoading(id);
      await campaignsApi.syncToSuperap(id);
      onRefresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '동기화 실패');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-surface rounded-xl border border-border">
        <div className="animate-pulse">
          <div className="h-12 bg-surface-raised border-b border-border" />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 border-b border-border-subtle px-6 flex items-center gap-4">
              <div className="h-4 bg-surface-raised rounded w-1/4" />
              <div className="h-4 bg-surface-raised rounded w-1/3" />
              <div className="h-4 bg-surface-raised rounded w-1/6" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (campaigns.length === 0) {
    return (
      <div className="bg-surface rounded-xl border border-border p-12 text-center text-gray-400">
        캠페인이 없습니다.
      </div>
    );
  }

  return (
    <>
      {/* Batch delete bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-2 px-4 py-2.5 bg-red-900/20 rounded-xl border border-red-800">
          <span className="text-sm text-red-400 font-medium">{selected.size}개 선택</span>
          <button
            onClick={handleBatchDelete}
            disabled={deleting}
            className="text-xs px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
          >
            {deleting ? '삭제 중...' : '선택 삭제'}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-xs px-2 py-1 text-gray-400 hover:text-gray-200"
          >
            선택 해제
          </button>
        </div>
      )}

      <div className="bg-surface rounded-xl border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-surface-raised">
              <tr>
                <th className="px-2 py-3 text-center w-8">
                  <input
                    type="checkbox"
                    checked={campaigns.length > 0 && selected.size === campaigns.length}
                    onChange={toggleAll}
                    className="rounded border-border-strong"
                  />
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">번호</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">상호명</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">상태</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">전환수</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">시작일</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">마감일</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">작업일</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">키워드잔량</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">최근변경</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase">작업</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {campaigns.map((c) => (
                <tr
                  key={c.id}
                  className={`hover:bg-surface-raised cursor-pointer transition-colors ${selected.has(c.id) ? 'bg-blue-900/20' : ''}`}
                  onClick={() => setDetailId(c.id)}
                >
                  <td className="px-2 py-2.5 text-center" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.has(c.id)}
                      onChange={() => toggleSelect(c.id)}
                      className="rounded border-border-strong"
                    />
                  </td>
                  <td className="px-3 py-2.5 text-gray-400 font-mono text-xs">
                    {c.campaign_code || '-'}
                  </td>
                  <td className="px-3 py-2.5 font-medium text-gray-100">
                    {c.place_name || <span className="text-gray-400 text-xs">(등록 대기)</span>}
                  </td>
                  <td className="px-3 py-2.5">
                    <StatusBadge status={c.status} registrationStep={c.registration_step} />
                  </td>
                  <td className="px-3 py-2.5 text-gray-400">
                    {c.current_conversions}
                    {c.total_limit ? `/${c.total_limit}` : ''}
                  </td>
                  <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">
                    {fmtDate(c.start_date)}
                  </td>
                  <td className="px-3 py-2.5 text-gray-400 text-xs whitespace-nowrap">
                    {fmtDate(c.end_date)}
                    {c.extension_history && c.extension_history.length > 0 && (
                      <span
                        className="ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-900/30 text-purple-400"
                        title={c.extension_history.map(
                          (ext, idx) => `연장 ${idx + 1}회: ${ext.previous_end_date} → ${ext.new_end_date} / +${ext.added_quantity}개`
                        ).join('\n')}
                      >
                        연장{c.extension_history.length}회
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-gray-400">
                    {c.days_running > 0 ? `D+${c.days_running}` : '-'}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${getKeywordStatusColor(c.keyword_status)}`}>
                      {getKeywordStatusLabel(c.keyword_status)}
                      <span className="text-[10px] opacity-75">
                        {c.keyword_remaining}/{c.keyword_total}
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-gray-400 text-xs">
                    {fmtDate(c.last_keyword_change)}
                  </td>
                  <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1 flex-wrap">
                      {/* Pending with no registration step: Register button */}
                      {c.status === 'pending' && !c.registration_step && (
                        <button
                          onClick={() => handleRegister(c.id)}
                          disabled={actionLoading === c.id}
                          className="text-xs px-2 py-1 bg-green-900/20 text-green-400 rounded-md hover:bg-green-900/30 disabled:opacity-50"
                        >
                          등록
                        </button>
                      )}
                      {/* Failed registration: Retry */}
                      {(c.status === 'failed' || (c.status === 'pending' && c.registration_step === 'failed')) && (
                        <button
                          onClick={() => handleRetry(c.id)}
                          disabled={retrying}
                          className="text-xs px-2 py-1 bg-orange-900/20 text-orange-400 rounded-md hover:bg-orange-900/30 disabled:opacity-50"
                        >
                          재시도
                        </button>
                      )}
                      <button
                        onClick={() => setEditModal(c)}
                        className="text-xs px-2 py-1 bg-surface-raised text-gray-400 rounded-md hover:bg-surface-raised"
                      >
                        수정
                      </button>
                      <button
                        onClick={() => setKeywordModal({ id: c.id, name: c.place_name || `#${c.campaign_code || c.id}` })}
                        className="text-xs px-2 py-1 bg-blue-900/20 text-blue-400 rounded-md hover:bg-blue-900/30"
                      >
                        +키워드
                      </button>
                      <button
                        onClick={() => handleDelete(c.id, c.place_name || `#${c.campaign_code || c.id}`)}
                        disabled={deleting}
                        className="text-xs px-2 py-1 bg-red-900/20 text-red-400 rounded-md hover:bg-red-900/30 disabled:opacity-50"
                      >
                        삭제
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="border-t border-border">
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={onPageChange}
            totalItems={totalItems}
            pageSize={20}
          />
        </div>
      </div>

      {detailId !== null && (
        <CampaignDetailModal
          campaignId={detailId}
          onClose={() => setDetailId(null)}
        />
      )}

      {keywordModal && (
        <KeywordAddModal
          campaignId={keywordModal.id}
          campaignName={keywordModal.name}
          onClose={() => setKeywordModal(null)}
          onSuccess={onRefresh}
        />
      )}

      {editModal && (
        <CampaignEditModal
          campaign={editModal}
          onClose={() => setEditModal(null)}
          onSuccess={onRefresh}
        />
      )}
    </>
  );
}
