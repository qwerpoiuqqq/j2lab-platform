import { useState } from 'react';
import Modal from '@/components/common/Modal';
import Button from '@/components/common/Button';
import { campaignsApi } from '@/api/campaigns';
import type { CampaignListItem, CampaignSettings } from '@/types';

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
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const loadKeywords = async () => {
    setLoadingKeywords(true);
    try {
      const kws = await campaignsApi.getKeywords(campaign.id);
      const allKeywords = kws.items.map((k) => k.keyword);
      setKeywords(allKeywords.join(', '));
      setKeywordsLoaded(true);
    } catch {
      setError('키워드 로딩 실패');
    } finally {
      setLoadingKeywords(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    setResult(null);

    const data: CampaignSettings = {};
    if (campaignCode !== (campaign.campaign_code || '')) data.campaign_code = campaignCode;
    if (placeName !== (campaign.place_name || '')) data.place_name = placeName;
    if (agencyName !== (campaign.agency_name || '')) data.agency_name = agencyName || undefined;
    const newDaily = Number(dailyLimit);
    const newTotal = totalLimit ? Number(totalLimit) : undefined;
    if (newDaily !== campaign.daily_limit) data.daily_limit = newDaily;
    if (newTotal !== campaign.total_limit) data.total_limit = newTotal;
    if (startDate !== campaign.start_date) data.start_date = startDate;
    if (endDate !== campaign.end_date) data.end_date = endDate;
    if (keywordsLoaded && keywords.trim()) data.keywords = keywords;

    if (Object.keys(data).length === 0) {
      onClose();
      return;
    }

    try {
      await campaignsApi.updateSettings(campaign.id, data);
      setResult('저장되었습니다.');
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '저장 실패');
      setSubmitting(false);
    }
  };

  const handleSync = async () => {
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await campaignsApi.syncToSuperap(campaign.id);
      setResult(res.message);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '동기화 실패');
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`설정 수정 - ${campaign.place_name || campaign.campaign_code || ''}`}
      size="lg"
      footer={
        <div className="flex w-full justify-between">
          {campaign.campaign_code ? (
            <Button variant="success" size="sm" onClick={handleSync} loading={submitting}>
              superap.io 동기화
            </Button>
          ) : (
            <div />
          )}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose} disabled={submitting}>
              취소
            </Button>
            <Button variant="primary" onClick={handleSubmit} loading={submitting}>
              저장
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">캠페인 번호</label>
          <input
            type="text"
            value={campaignCode}
            onChange={(e) => setCampaignCode(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500"
            placeholder="superap.io 캠페인 번호"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">상호명</label>
            <input
              type="text"
              value={placeName}
              onChange={(e) => setPlaceName(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">대행사</label>
            <input
              type="text"
              value={agencyName}
              onChange={(e) => setAgencyName(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">일일한도 (타수)</label>
            <input
              type="number"
              value={dailyLimit}
              onChange={(e) => setDailyLimit(e.target.value)}
              min={1}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">전체한도</label>
            <input
              type="number"
              value={totalLimit}
              onChange={(e) => setTotalLimit(e.target.value)}
              min={1}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="자동 계산"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">시작일</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">종료일</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {/* Keywords */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-sm font-medium text-gray-700">키워드</label>
            {!keywordsLoaded && (
              <button
                onClick={loadKeywords}
                disabled={loadingKeywords}
                className="text-xs text-primary-600 hover:text-primary-700"
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
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="콤마(,)로 구분하여 입력"
            />
          ) : (
            <div className="text-xs text-gray-400 border border-gray-200 rounded-lg px-3 py-2">
              키워드를 수정하려면 &quot;키워드 불러오기&quot;를 클릭하세요
            </div>
          )}
        </div>

        {/* Extension history */}
        {campaign.extension_history && campaign.extension_history.length > 0 && (
          <div className="p-3 bg-gray-50 rounded-lg">
            <div className="text-sm font-medium text-gray-700 mb-2">연장 이력</div>
            <div className="space-y-1">
              {campaign.extension_history.map((ext, idx) => (
                <div key={idx} className="text-xs text-gray-600">
                  연장 {idx + 1}회: {ext.previous_end_date} → {ext.new_end_date} / +{ext.added_quantity}개 (총 {ext.new_total_limit})
                </div>
              ))}
            </div>
          </div>
        )}

        {error && <div className="text-sm text-red-600">{error}</div>}
        {result && <div className="text-sm text-green-600">{result}</div>}
      </div>
    </Modal>
  );
}
