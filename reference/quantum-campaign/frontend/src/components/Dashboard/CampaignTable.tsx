import { useState } from 'react';
import type { CampaignListItem } from '../../types';
import { getStatusLabel } from '../../types';
import { deleteCampaign, batchDeleteCampaigns, retryRegistration, getErrorMessage } from '../../services/api';
import KeywordBadge from '../common/KeywordBadge';
import KeywordAddModal from '../Campaign/KeywordAddModal';
import CampaignEditModal from '../Campaign/CampaignEditModal';
import CampaignDetailModal from '../Campaign/CampaignDetailModal';

interface CampaignTableProps {
  campaigns: CampaignListItem[];
  loading: boolean;
  page: number;
  pages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-';
  return dateStr.slice(5, 10).replace('-', '/');
}

export default function CampaignTable({
  campaigns,
  loading,
  page,
  pages,
  onPageChange,
  onRefresh,
}: CampaignTableProps) {
  const [keywordModal, setKeywordModal] = useState<{ id: number; name: string } | null>(null);
  const [editModal, setEditModal] = useState<CampaignListItem | null>(null);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [retrying, setRetrying] = useState(false);

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
      await deleteCampaign(id);
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      onRefresh();
    } catch (err) {
      alert(getErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selected.size === 0) return;
    if (!confirm(`선택한 ${selected.size}개 캠페인을 삭제하시겠습니까?`)) return;
    try {
      setDeleting(true);
      await batchDeleteCampaigns([...selected]);
      setSelected(new Set());
      onRefresh();
    } catch (err) {
      alert(getErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  const handleRetry = async (id: number) => {
    try {
      setRetrying(true);
      const result = await retryRegistration([id]);
      if (result.success) {
        onRefresh();
      } else {
        alert(result.message);
      }
    } catch (err) {
      alert(getErrorMessage(err));
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
        로딩 중...
      </div>
    );
  }

  if (campaigns.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-8 text-center text-gray-500">
        캠페인이 없습니다.
      </div>
    );
  }

  return (
    <>
      {/* Batch delete bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-2 px-3 py-2 bg-red-50 rounded-lg border border-red-200">
          <span className="text-sm text-red-700 font-medium">
            {selected.size}개 선택
          </span>
          <button
            onClick={handleBatchDelete}
            disabled={deleting}
            className="text-xs px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
          >
            {deleting ? '삭제 중...' : '선택 삭제'}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-xs px-2 py-1 text-gray-600 hover:text-gray-800"
          >
            선택 해제
          </button>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-2 py-2.5 text-center w-8">
                  <input
                    type="checkbox"
                    checked={campaigns.length > 0 && selected.size === campaigns.length}
                    onChange={toggleAll}
                    className="rounded border-gray-300"
                  />
                </th>
                <th className="px-3 py-2.5 text-left font-medium">번호</th>
                <th className="px-3 py-2.5 text-left font-medium">상호명</th>
                <th className="px-3 py-2.5 text-left font-medium">상태</th>
                <th className="px-3 py-2.5 text-left font-medium">전환수</th>
                <th className="px-3 py-2.5 text-left font-medium">시작일</th>
                <th className="px-3 py-2.5 text-left font-medium">마감일</th>
                <th className="px-3 py-2.5 text-left font-medium">작업일</th>
                <th className="px-3 py-2.5 text-left font-medium">키워드잔량</th>
                <th className="px-3 py-2.5 text-left font-medium">최근변경</th>
                <th className="px-3 py-2.5 text-left font-medium">작업</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {campaigns.map((c) => (
                <tr
                  key={c.id}
                  className={`hover:bg-gray-50 cursor-pointer ${selected.has(c.id) ? 'bg-blue-50/50' : ''}`}
                  onClick={() => setDetailId(c.id)}
                >
                  <td className="px-2 py-2 text-center" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.has(c.id)}
                      onChange={() => toggleSelect(c.id)}
                      className="rounded border-gray-300"
                    />
                  </td>
                  <td className="px-3 py-2 text-gray-500 font-mono text-xs">
                    {c.campaign_code || '-'}
                  </td>
                  <td className="px-3 py-2 font-medium">
                    {c.place_name || <span className="text-gray-400 text-xs">(등록 대기)</span>}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge
                      status={c.status}
                      registrationStep={c.registration_step}
                    />
                  </td>
                  <td className="px-3 py-2">
                    {c.current_conversions}
                    {c.total_limit ? `/${c.total_limit}` : ''}
                  </td>
                  <td className="px-3 py-2 text-gray-600 text-xs whitespace-nowrap">
                    {formatDate(c.start_date)}
                  </td>
                  <td className="px-3 py-2 text-gray-600 text-xs whitespace-nowrap">
                    {formatDate(c.end_date)}
                    {c.extension_history && c.extension_history.length > 0 && (
                      <span
                        className="ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-100 text-purple-700 cursor-help"
                        title={c.extension_history.map(
                          (ext) => `연장 ${ext.round}회: ${ext.start_date} ~ ${ext.end_date} / 일 ${ext.daily_limit}타`
                        ).join('\n')}
                      >
                        연장{c.extension_history.length}회
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {c.days_running > 0 ? `D+${c.days_running}` : '-'}
                  </td>
                  <td className="px-3 py-2">
                    <KeywordBadge
                      status={c.keyword_status}
                      remaining={c.keyword_remaining}
                      total={c.keyword_total}
                    />
                  </td>
                  <td className="px-3 py-2 text-gray-500 text-xs">
                    {formatDate(c.last_keyword_change)}
                  </td>
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-1">
                      {c.status === 'pending' && c.registration_step === 'failed' && (
                        <button
                          onClick={() => handleRetry(c.id)}
                          disabled={retrying}
                          className="text-xs px-2 py-1 bg-orange-50 text-orange-600 rounded hover:bg-orange-100 disabled:opacity-50"
                        >
                          {retrying ? '...' : '재시도'}
                        </button>
                      )}
                      <button
                        onClick={() => setEditModal(c)}
                        className="text-xs px-2 py-1 bg-gray-50 text-gray-600 rounded hover:bg-gray-100"
                      >
                        수정
                      </button>
                      <button
                        onClick={() => setKeywordModal({ id: c.id, name: c.place_name || `#${c.campaign_code || c.id}` })}
                        className="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
                      >
                        +키워드
                      </button>
                      <button
                        onClick={() => handleDelete(c.id, c.place_name || `#${c.campaign_code || c.id}`)}
                        disabled={deleting}
                        className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100 disabled:opacity-50"
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

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-center gap-2 py-3 border-t">
            <button
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="px-3 py-1 text-sm border rounded disabled:opacity-30"
            >
              이전
            </button>
            <span className="text-sm text-gray-600">
              {page} / {pages}
            </span>
            <button
              disabled={page >= pages}
              onClick={() => onPageChange(page + 1)}
              className="px-3 py-1 text-sm border rounded disabled:opacity-30"
            >
              다음
            </button>
          </div>
        )}
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

function StatusBadge({
  status,
  registrationStep,
}: {
  status: string;
  registrationStep?: string | null;
}) {
  // pending + failed step → 등록실패 표시
  if (status === 'pending' && registrationStep === 'failed') {
    return (
      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
        등록실패
      </span>
    );
  }
  // pending + queued/in-progress step → 등록중 표시
  if (status === 'pending' && registrationStep && registrationStep !== 'completed') {
    return (
      <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
        등록중
      </span>
    );
  }

  const map: Record<string, string> = {
    active: 'bg-green-100 text-green-800',
    daily_exhausted: 'bg-orange-100 text-orange-800',
    campaign_exhausted: 'bg-red-100 text-red-800',
    deactivated: 'bg-red-100 text-red-700',
    paused: 'bg-yellow-100 text-yellow-800',
    pending: 'bg-gray-100 text-gray-600',
    pending_extend: 'bg-purple-100 text-purple-800',
    completed: 'bg-gray-100 text-gray-500',
  };
  const cls = map[status] || 'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {getStatusLabel(status)}
    </span>
  );
}
