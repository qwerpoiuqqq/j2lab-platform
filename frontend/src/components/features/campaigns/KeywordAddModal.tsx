import { useState } from 'react';
import Modal from '@/components/common/Modal';
import Button from '@/components/common/Button';
import { campaignsApi } from '@/api/campaigns';

interface KeywordAddModalProps {
  campaignId: number;
  campaignName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export default function KeywordAddModal({
  campaignId,
  campaignName,
  onClose,
  onSuccess,
}: KeywordAddModalProps) {
  const [keywords, setKeywords] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!keywords.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const keywordList = keywords.split(',').map((k) => k.trim()).filter(Boolean);
      const res = await campaignsApi.addKeywords(campaignId, keywordList);
      const added = res.detail?.added ?? keywordList.length;
      setResult(`${added}개 키워드가 추가되었습니다.`);
      onSuccess();
    } catch {
      setError('키워드 추가에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`키워드 추가 - ${campaignName}`}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            닫기
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit}
            loading={submitting}
            disabled={!keywords.trim()}
          >
            추가
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            키워드 (쉼표로 구분)
          </label>
          <textarea
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            rows={4}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            placeholder="키워드1, 키워드2, 키워드3"
          />
        </div>

        {error && <div className="text-sm text-red-600">{error}</div>}
        {result && <div className="text-sm text-green-600">{result}</div>}
      </div>
    </Modal>
  );
}
