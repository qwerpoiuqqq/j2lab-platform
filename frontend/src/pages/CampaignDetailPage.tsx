import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import CampaignDetailComponent from '@/components/features/campaigns/CampaignDetail';
import Button from '@/components/common/Button';
import { ArrowLeftIcon, PencilIcon, TrashIcon, PlusIcon, ClockIcon } from '@heroicons/react/24/outline';
import type { Campaign, CampaignKeyword, CampaignListItem, ExtensionHistoryItem } from '@/types';
import { campaignsApi } from '@/api/campaigns';
import { formatDate } from '@/utils/format';

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [keywords, setKeywords] = useState<CampaignKeyword[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Edit modal state
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    place_name: '',
    daily_limit: 0,
    total_limit: 0,
    end_date: '',
    agency_name: '',
  });

  // Extend modal state
  const [extendOpen, setExtendOpen] = useState(false);
  const [extendForm, setExtendForm] = useState({
    new_end_date: '',
    additional_total: 0,
    new_daily_limit: 0,
  });

  // Add keywords modal state
  const [keywordOpen, setKeywordOpen] = useState(false);
  const [newKeywords, setNewKeywords] = useState('');

  // Extension history collapse state
  const [historyOpen, setHistoryOpen] = useState(false);

  const loadCampaign = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [campaignData, keywordsData] = await Promise.all([
        campaignsApi.get(Number(id)),
        campaignsApi.getKeywords(Number(id)),
      ]);
      setCampaign(campaignData);
      setKeywords(keywordsData.items);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '캠페인을 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // eslint warns about loadCampaign not in deps, but loadCampaign references `id` from closure.
  // Including loadCampaign would cause infinite loop since it's redefined every render.
  // Using `id` as dep is the correct behavior: re-fetch when id changes.
  useEffect(() => {
    loadCampaign();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const handleAction = async (action: string) => {
    if (!id) return;
    setActionLoading(true);
    try {
      switch (action) {
        case 'pause': {
          const updated = await campaignsApi.pause(Number(id));
          setCampaign(updated);
          break;
        }
        case 'resume': {
          const updated = await campaignsApi.resume(Number(id));
          setCampaign(updated);
          break;
        }
        case 'rotate':
          await campaignsApi.rotateKeywords(Number(id));
          await loadCampaign();
          break;
        default:
          setActionLoading(false);
          return;
      }
    } catch (err: any) {
      alert(err?.response?.data?.detail || '작업에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  // Delete handler
  const handleDelete = async () => {
    if (!campaign) return;
    if (!confirm('이 캠페인을 삭제하시겠습니까?')) return;
    try {
      await campaignsApi.delete(campaign.id);
      navigate('/campaigns');
    } catch (err: any) {
      alert(err?.response?.data?.detail || '삭제에 실패했습니다.');
    }
  };

  // Edit handlers
  const openEditModal = () => {
    if (!campaign) return;
    setEditForm({
      place_name: campaign.place_name || '',
      daily_limit: campaign.daily_limit || 0,
      total_limit: campaign.total_limit || 0,
      end_date: campaign.end_date || '',
      agency_name: campaign.agency_name || '',
    });
    setEditOpen(true);
  };

  const handleEdit = async () => {
    if (!campaign) return;
    setActionLoading(true);
    try {
      const updateData: Record<string, any> = {};
      if (editForm.place_name !== campaign.place_name) updateData.place_name = editForm.place_name;
      if (editForm.daily_limit !== campaign.daily_limit) updateData.daily_limit = editForm.daily_limit;
      if (editForm.total_limit !== (campaign.total_limit || 0)) updateData.total_limit = editForm.total_limit;
      if (editForm.end_date !== campaign.end_date) updateData.end_date = editForm.end_date;
      if (editForm.agency_name !== (campaign.agency_name || '')) updateData.agency_name = editForm.agency_name;

      if (Object.keys(updateData).length > 0) {
        const updated = await campaignsApi.updateSettings(campaign.id, updateData);
        setCampaign(updated);
      }
      setEditOpen(false);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '수정에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  // Extend handler
  const openExtendModal = () => {
    if (!campaign) return;
    // Default: 30 days from current end_date
    const currentEnd = campaign.end_date ? new Date(campaign.end_date) : new Date();
    const newEnd = new Date(currentEnd);
    newEnd.setDate(newEnd.getDate() + 30);
    setExtendForm({
      new_end_date: newEnd.toISOString().split('T')[0],
      additional_total: 0,
      new_daily_limit: campaign.daily_limit || 0,
    });
    setExtendOpen(true);
  };

  const handleExtend = async () => {
    if (!campaign) return;
    setActionLoading(true);
    try {
      await campaignsApi.extend(campaign.id, {
        new_end_date: extendForm.new_end_date,
        additional_total: extendForm.additional_total,
        new_daily_limit: extendForm.new_daily_limit || undefined,
      });
      await loadCampaign();
      setExtendOpen(false);
    } catch (err: any) {
      alert(err?.response?.data?.detail || '연장에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  // Add keywords handler
  const handleAddKeywords = async () => {
    if (!campaign) return;
    const keywordList = newKeywords.split('\n').map(k => k.trim()).filter(Boolean);
    if (!keywordList.length) return;
    setActionLoading(true);
    try {
      await campaignsApi.addKeywords(campaign.id, keywordList);
      await loadCampaign();
      setKeywordOpen(false);
      setNewKeywords('');
    } catch (err: any) {
      alert(err?.response?.data?.detail || '키워드 추가에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  // Get extension history from campaign (may be on CampaignListItem)
  const extensionHistory: ExtensionHistoryItem[] = (campaign as CampaignListItem)?.extension_history || [];

  const canDelete = campaign && ['completed', 'paused', 'failed', 'expired', 'deactivated'].includes(campaign.status);

  if (error) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/campaigns')}
          icon={<ArrowLeftIcon className="h-4 w-4" />}
        >
          목록으로
        </Button>
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700 text-sm">
          {error}
        </div>
      </div>
    );
  }

  if (loading || !campaign) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="bg-white rounded-xl border border-gray-200 h-48" />
        <div className="bg-white rounded-xl border border-gray-200 h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/campaigns')}
          icon={<ArrowLeftIcon className="h-4 w-4" />}
        >
          목록으로
        </Button>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={openEditModal}
            icon={<PencilIcon className="h-4 w-4" />}
          >
            수정
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={openExtendModal}
            icon={<ClockIcon className="h-4 w-4" />}
          >
            연장
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setKeywordOpen(true)}
            icon={<PlusIcon className="h-4 w-4" />}
          >
            키워드 추가
          </Button>
          {canDelete && (
            <Button
              variant="danger"
              size="sm"
              onClick={handleDelete}
              icon={<TrashIcon className="h-4 w-4" />}
            >
              삭제
            </Button>
          )}
        </div>
      </div>

      <CampaignDetailComponent
        campaign={campaign}
        keywords={keywords}
        onPause={() => handleAction('pause')}
        onResume={() => handleAction('resume')}
        onRotateKeywords={() => handleAction('rotate')}
        actionLoading={actionLoading}
      />

      {/* Extension History */}
      {extensionHistory.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200">
          <button
            onClick={() => setHistoryOpen(!historyOpen)}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <h3 className="text-base font-semibold text-gray-900">
              연장 이력 ({extensionHistory.length}회)
            </h3>
            <svg
              className={`h-5 w-5 text-gray-400 transition-transform ${historyOpen ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {historyOpen && (
            <div className="border-t border-gray-200">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">회차</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">연장일시</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">종료일 변경</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">총 한도 변경</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">추가 수량</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {extensionHistory.map((item, idx) => (
                    <tr key={idx}>
                      <td className="px-6 py-3 text-sm text-gray-900">{idx + 1}</td>
                      <td className="px-6 py-3 text-sm text-gray-600">{formatDate(item.extended_at)}</td>
                      <td className="px-6 py-3 text-sm text-gray-600">{formatDate(item.previous_end_date)} → {formatDate(item.new_end_date)}</td>
                      <td className="px-6 py-3 text-sm text-gray-600">{item.previous_total_limit} → {item.new_total_limit}</td>
                      <td className="px-6 py-3 text-sm text-gray-600">+{item.added_quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Edit Modal */}
      {editOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">캠페인 수정</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">플레이스명</label>
                <input
                  type="text"
                  value={editForm.place_name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, place_name: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">광고주명</label>
                <input
                  type="text"
                  value={editForm.agency_name}
                  onChange={(e) => setEditForm(prev => ({ ...prev, agency_name: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">일일 한도</label>
                  <input
                    type="number"
                    value={editForm.daily_limit}
                    onChange={(e) => setEditForm(prev => ({ ...prev, daily_limit: Number(e.target.value) }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">총 한도</label>
                  <input
                    type="number"
                    value={editForm.total_limit}
                    onChange={(e) => setEditForm(prev => ({ ...prev, total_limit: Number(e.target.value) }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">종료일</label>
                <input
                  type="date"
                  value={editForm.end_date}
                  onChange={(e) => setEditForm(prev => ({ ...prev, end_date: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <Button
                variant="secondary"
                onClick={() => setEditOpen(false)}
                disabled={actionLoading}
              >
                취소
              </Button>
              <Button
                variant="primary"
                onClick={handleEdit}
                loading={actionLoading}
              >
                저장
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Extend Modal */}
      {extendOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">캠페인 연장</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">새 종료일</label>
                <input
                  type="date"
                  value={extendForm.new_end_date}
                  onChange={(e) => setExtendForm(prev => ({ ...prev, new_end_date: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">추가 총 전환수</label>
                  <input
                    type="number"
                    value={extendForm.additional_total}
                    onChange={(e) => setExtendForm(prev => ({ ...prev, additional_total: Number(e.target.value) }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">새 일일 한도 (선택)</label>
                  <input
                    type="number"
                    value={extendForm.new_daily_limit}
                    onChange={(e) => setExtendForm(prev => ({ ...prev, new_daily_limit: Number(e.target.value) }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    placeholder="0 = 변경 안함"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <Button
                variant="secondary"
                onClick={() => setExtendOpen(false)}
                disabled={actionLoading}
              >
                취소
              </Button>
              <Button
                variant="primary"
                onClick={handleExtend}
                loading={actionLoading}
              >
                연장
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Add Keywords Modal */}
      {keywordOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">키워드 추가</h3>
            <p className="text-sm text-gray-500 mb-3">한 줄에 하나씩 키워드를 입력하세요.</p>
            <textarea
              value={newKeywords}
              onChange={(e) => setNewKeywords(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 min-h-[150px]"
              placeholder={"키워드1\n키워드2\n키워드3"}
              autoFocus
            />
            <div className="flex justify-end gap-2 mt-4">
              <Button
                variant="secondary"
                onClick={() => { setKeywordOpen(false); setNewKeywords(''); }}
                disabled={actionLoading}
              >
                취소
              </Button>
              <Button
                variant="primary"
                onClick={handleAddKeywords}
                loading={actionLoading}
                disabled={!newKeywords.trim()}
              >
                추가
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
