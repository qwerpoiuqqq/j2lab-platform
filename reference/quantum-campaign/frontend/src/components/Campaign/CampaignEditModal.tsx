import { useState } from 'react';
import Modal from '../common/Modal';
import { updateCampaignSettings, syncCampaignToSuperap, fetchCampaignDetail, getErrorMessage } from '../../services/api';
import type { CampaignListItem } from '../../types';

interface CampaignEditModalProps {
  campaign: CampaignListItem;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CampaignEditModal({
  campaign,
  onClose,
  onSuccess,
}: CampaignEditModalProps) {
  const [campaignCode, setCampaignCode] = useState(campaign.campaign_code || '');
  const [placeName, setPlaceName] = useState(campaign.place_name || '');
  const [agencyName, setAgencyName] = useState(campaign.agency_name || '');
  const [dailyLimit, setDailyLimit] = useState(String(campaign.daily_limit));
  const [totalLimit, setTotalLimit] = useState(
    campaign.total_limit ? String(campaign.total_limit) : '',
  );
  const [startDate, setStartDate] = useState(campaign.start_date);
  const [endDate, setEndDate] = useState(campaign.end_date);
  const [keywords, setKeywords] = useState('');
  const [loadingKeywords, setLoadingKeywords] = useState(false);
  const [keywordsLoaded, setKeywordsLoaded] = useState(false);
  const [syncSuperap, setSyncSuperap] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const loadKeywords = async () => {
    setLoadingKeywords(true);
    try {
      const detail = await fetchCampaignDetail(campaign.id);
      const allKeywords = detail.keywords.map((k) => k.keyword);
      setKeywords(allKeywords.join(', '));
      setKeywordsLoaded(true);
    } catch (err) {
      setError('키워드 로딩 실패: ' + getErrorMessage(err));
    } finally {
      setLoadingKeywords(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    setResult(null);

    const data: Record<string, unknown> = {};

    if (campaignCode !== (campaign.campaign_code || '')) data.campaign_code = campaignCode;
    if (placeName !== (campaign.place_name || '')) data.place_name = placeName;
    if (agencyName !== (campaign.agency_name || '')) data.agency_name = agencyName || null;
    const newDaily = Number(dailyLimit);
    const newTotal = totalLimit ? Number(totalLimit) : null;

    if (newDaily !== campaign.daily_limit) data.daily_limit = newDaily;
    if (newTotal !== campaign.total_limit) data.total_limit = newTotal;
    if (startDate !== campaign.start_date) data.start_date = startDate;
    if (endDate !== campaign.end_date) data.end_date = endDate;
    if (keywordsLoaded && keywords.trim()) data.keywords = keywords;
    data.sync_superap = syncSuperap;

    if (Object.keys(data).length <= 1) {
      // sync_superap만 있으면 변경사항 없음
      onClose();
      return;
    }

    try {
      const res = await updateCampaignSettings(campaign.id, data);
      if (res.superap_synced) {
        setResult(res.message);
        setTimeout(() => {
          onSuccess();
          onClose();
        }, 1500);
      } else {
        setResult(res.message);
        setTimeout(() => {
          onSuccess();
          onClose();
        }, 2000);
      }
    } catch (err) {
      setError(getErrorMessage(err));
      setSubmitting(false);
    }
  };

  const hasSuperapFields = campaign.campaign_code && (
    dailyLimit !== String(campaign.daily_limit) ||
    (totalLimit ? Number(totalLimit) : null) !== campaign.total_limit ||
    endDate !== campaign.end_date ||
    (keywordsLoaded && keywords.trim())
  );

  const handleSync = async () => {
    setSyncing(true);
    setError(null);
    setResult(null);
    try {
      const res = await syncCampaignToSuperap(campaign.id);
      if (res.superap_synced) {
        setResult(res.message);
        setTimeout(() => {
          onSuccess();
          onClose();
        }, 1500);
      } else {
        setError(res.message);
        setSyncing(false);
      }
    } catch (err) {
      setError(getErrorMessage(err));
      setSyncing(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`설정 수정 - ${campaign.place_name}`}>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            캠페인 번호
          </label>
          <input
            type="text"
            value={campaignCode}
            onChange={(e) => setCampaignCode(e.target.value)}
            className="w-full border rounded-md px-3 py-2 text-sm font-mono"
            placeholder="superap.io 캠페인 번호"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              상호명
            </label>
            <input
              type="text"
              value={placeName}
              onChange={(e) => setPlaceName(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="플레이스 상호명"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              대행사
            </label>
            <input
              type="text"
              value={agencyName}
              onChange={(e) => setAgencyName(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="대행사명"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              일일한도 (타수)
            </label>
            <input
              type="number"
              value={dailyLimit}
              onChange={(e) => setDailyLimit(e.target.value)}
              min={1}
              className="w-full border rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              전체한도
            </label>
            <input
              type="number"
              value={totalLimit}
              onChange={(e) => setTotalLimit(e.target.value)}
              min={1}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="자동 계산"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              시작일
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              종료일
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* 키워드 */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-sm font-medium text-gray-700">
              키워드
            </label>
            {!keywordsLoaded && (
              <button
                onClick={loadKeywords}
                disabled={loadingKeywords}
                className="text-xs text-blue-500 hover:text-blue-700"
              >
                {loadingKeywords ? '로딩 중...' : '키워드 불러오기'}
              </button>
            )}
          </div>
          {keywordsLoaded ? (
            <textarea
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              rows={3}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="콤마(,)로 구분하여 입력"
            />
          ) : (
            <div className="text-xs text-gray-400 border rounded-md px-3 py-2">
              키워드를 수정하려면 &quot;키워드 불러오기&quot;를 클릭하세요
            </div>
          )}
        </div>

        {/* superap.io 동기화 옵션 */}
        {campaign.campaign_code && (
          <div className="flex items-center gap-2 p-3 bg-blue-50 rounded-md">
            <input
              type="checkbox"
              id="syncSuperap"
              checked={syncSuperap}
              onChange={(e) => setSyncSuperap(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="syncSuperap" className="text-sm text-blue-700">
              superap.io에 실시간 반영
              {hasSuperapFields && syncSuperap && (
                <span className="text-xs text-blue-500 ml-1">
                  (일타수/총타수/종료일/키워드 변경 시 자동 반영)
                </span>
              )}
            </label>
          </div>
        )}

        {/* 연장 이력 */}
        {campaign.extension_history && campaign.extension_history.length > 0 && (
          <div className="p-3 bg-gray-50 rounded-md">
            <div className="text-sm font-medium text-gray-700 mb-2">연장 이력</div>
            <div className="space-y-1">
              {campaign.extension_history.map((ext) => (
                <div key={ext.round} className="text-xs text-gray-600">
                  연장 {ext.round}회: {ext.start_date} ~ {ext.end_date} / 일 {ext.daily_limit}타
                </div>
              ))}
            </div>
          </div>
        )}

        {error && <div className="text-sm text-red-600">{error}</div>}
        {result && (
          <div className={`text-sm ${result.includes('실패') ? 'text-orange-600' : 'text-green-600'}`}>
            {result}
          </div>
        )}

        <div className="flex justify-between items-center">
          {campaign.campaign_code ? (
            <button
              onClick={handleSync}
              disabled={submitting || syncing}
              className="px-3 py-2 text-sm bg-green-50 text-green-700 border border-green-300 rounded-md hover:bg-green-100 disabled:opacity-50"
            >
              {syncing ? 'superap.io 동기화 중...' : 'superap.io 동기화'}
            </button>
          ) : (
            <div />
          )}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              disabled={submitting || syncing}
              className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
            >
              취소
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting || syncing}
              className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
            >
              {submitting
                ? syncSuperap && hasSuperapFields
                  ? 'superap.io 반영 중...'
                  : '저장 중...'
                : '저장'}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
