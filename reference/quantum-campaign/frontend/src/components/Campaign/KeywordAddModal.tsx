import { useState } from 'react';
import Modal from '../common/Modal';
import { addKeywords } from '../../services/api';

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
      const res = await addKeywords(campaignId, keywords);
      setResult(res.message);
      onSuccess();
    } catch {
      setError('키워드 추가에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`키워드 추가 - ${campaignName}`}>
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            키워드 (쉼표로 구분)
          </label>
          <textarea
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            rows={4}
            className="w-full border rounded-md px-3 py-2 text-sm"
            placeholder="키워드1, 키워드2, 키워드3"
          />
        </div>

        {error && <div className="text-sm text-red-600">{error}</div>}
        {result && <div className="text-sm text-green-600">{result}</div>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
          >
            닫기
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !keywords.trim()}
            className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
          >
            {submitting ? '추가 중...' : '추가'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
