import { useState } from 'react';
import Modal from '@/components/common/Modal';
import Button from '@/components/common/Button';
import { campaignsApi } from '@/api/campaigns';
import type { CampaignListItem } from '@/types';

interface CampaignExtendModalProps {
  campaign: CampaignListItem;
  onClose: () => void;
  onSuccess: () => void;
}

export default function CampaignExtendModal({
  campaign,
  onClose,
  onSuccess,
}: CampaignExtendModalProps) {
  const [newEndDate, setNewEndDate] = useState('');
  const [additionalTotal, setAdditionalTotal] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const handleSubmit = async () => {
    setError(null);
    setResult(null);

    if (!newEndDate) {
      setError('새 종료일을 입력해주세요.');
      return;
    }
    if (!additionalTotal || Number(additionalTotal) < 1) {
      setError('추가 총 타수를 1 이상 입력해주세요.');
      return;
    }
    if (newEndDate <= campaign.end_date) {
      setError('새 종료일은 현재 종료일 이후여야 합니다.');
      return;
    }

    setSubmitting(true);
    try {
      await campaignsApi.extend(campaign.id, {
        new_end_date: newEndDate,
        additional_total: Number(additionalTotal),
      });
      setResult('연장 요청이 전송되었습니다.');
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || '연장 요청 실패');
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`캠페인 연장 - ${campaign.place_name || campaign.campaign_code || ''}`}
      size="md"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            취소
          </Button>
          <Button variant="primary" onClick={handleSubmit} loading={submitting}>
            연장 요청
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600">
          <div>현재 종료일: <span className="font-medium text-gray-900">{campaign.end_date}</span></div>
          <div>현재 일일한도: <span className="font-medium text-gray-900">{campaign.daily_limit}타</span></div>
          {campaign.total_limit && (
            <div>현재 전체한도: <span className="font-medium text-gray-900">{campaign.total_limit}타</span></div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">새 종료일</label>
          <input
            type="date"
            value={newEndDate}
            onChange={(e) => setNewEndDate(e.target.value)}
            min={campaign.end_date}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">추가 총 타수</label>
          <input
            type="number"
            value={additionalTotal}
            onChange={(e) => setAdditionalTotal(e.target.value)}
            min={1}
            placeholder="연장 기간에 추가할 총 전환수"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {error && <div className="text-sm text-red-600">{error}</div>}
        {result && <div className="text-sm text-green-600">{result}</div>}
      </div>
    </Modal>
  );
}
