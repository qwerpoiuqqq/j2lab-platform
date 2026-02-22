import { useState } from 'react';
import { useAccounts } from '../hooks/useAccounts';
import { useTemplates } from '../hooks/useTemplates';
import { verifyCampaign, addManualCampaign } from '../services/api';

interface FormData {
  campaign_code: string;
  account_id: string;
  agency_name: string;
  place_name: string;
  place_url: string;
  campaign_type: string;
  start_date: string;
  end_date: string;
  daily_limit: string;
  keywords: string;
}

const INITIAL: FormData = {
  campaign_code: '',
  account_id: '',
  agency_name: '',
  place_name: '',
  place_url: '',
  campaign_type: '',
  start_date: '',
  end_date: '',
  daily_limit: '',
  keywords: '',
};

export default function CampaignAddPage() {
  const { accounts } = useAccounts();
  const { templates } = useTemplates();
  const activeTemplates = templates.filter((t) => t.is_active);
  const [form, setForm] = useState<FormData>(INITIAL);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);
  const [verifyOk, setVerifyOk] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  const set = (key: keyof FormData, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleVerify = async () => {
    if (!form.campaign_code.trim()) return;
    try {
      const res = await verifyCampaign(
        form.campaign_code,
        form.account_id ? Number(form.account_id) : undefined,
      );
      setVerifyMsg(res.message);
      setVerifyOk(!res.exists_in_db);
    } catch {
      setVerifyMsg('확인에 실패했습니다.');
      setVerifyOk(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setResult(null);
    try {
      const res = await addManualCampaign({
        campaign_code: form.campaign_code,
        account_id: Number(form.account_id),
        agency_name: form.agency_name || undefined,
        place_name: form.place_name,
        place_url: form.place_url,
        campaign_type: form.campaign_type,
        start_date: form.start_date,
        end_date: form.end_date,
        daily_limit: Number(form.daily_limit),
        keywords: form.keywords,
      });
      setResult({ success: res.success, message: res.message });
      if (res.success) setForm(INITIAL);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? String((err as { response: { data: { detail: string } } }).response?.data?.detail || '등록에 실패했습니다.')
          : '등록에 실패했습니다.';
      setResult({ success: false, message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-bold mb-6">캠페인 직접 추가</h1>

      {result && (
        <div
          className={`rounded-lg p-4 text-sm mb-4 ${
            result.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}
        >
          {result.message}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm p-6 space-y-4">
        {/* 캠페인 번호 확인 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">캠페인 번호</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={form.campaign_code}
              onChange={(e) => { set('campaign_code', e.target.value); setVerifyMsg(null); setVerifyOk(false); }}
              className="flex-1 border rounded-md px-3 py-2 text-sm"
              placeholder="superap 캠페인 번호"
              required
            />
            <button
              type="button"
              onClick={handleVerify}
              className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
            >
              확인
            </button>
          </div>
          {verifyMsg && (
            <p className={`text-xs mt-1 ${verifyOk ? 'text-green-600' : 'text-red-600'}`}>
              {verifyMsg}
            </p>
          )}
        </div>

        {/* 계정 + 대행사 */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">계정</label>
            <select
              value={form.account_id}
              onChange={(e) => {
                const id = e.target.value;
                set('account_id', id);
                const acc = accounts.find((a) => String(a.id) === id);
                if (acc?.agency_name && !form.agency_name) {
                  set('agency_name', acc.agency_name);
                }
              }}
              className="w-full border rounded-md px-3 py-2 text-sm"
              required
            >
              <option value="">선택</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.user_id} {a.agency_name ? `(${a.agency_name})` : ''}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              대행사 <span className="text-xs text-gray-400">(계정에서 자동 입력)</span>
            </label>
            <input
              type="text"
              value={form.agency_name}
              onChange={(e) => set('agency_name', e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="대행사명"
            />
          </div>
        </div>

        {/* 플레이스 정보 */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">플레이스 URL</label>
            <input
              type="text"
              value={form.place_url}
              onChange={(e) => set('place_url', e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="https://m.place.naver.com/..."
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              플레이스명 <span className="text-xs text-gray-400">(비우면 URL에서 자동 추출)</span>
            </label>
            <input
              type="text"
              value={form.place_name}
              onChange={(e) => set('place_name', e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="비워두면 자동 추출"
            />
          </div>
        </div>

        {/* 캠페인 이름 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">캠페인 이름</label>
          <select
            value={form.campaign_type}
            onChange={(e) => set('campaign_type', e.target.value)}
            className="w-full border rounded-md px-3 py-2 text-sm"
            required
          >
            <option value="">선택</option>
            {activeTemplates.map((t) => (
              <option key={t.id} value={t.type_name}>
                {t.type_name}
              </option>
            ))}
          </select>
        </div>

        {/* 날짜 + 일일 한도 */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">시작일</label>
            <input
              type="date"
              value={form.start_date}
              onChange={(e) => set('start_date', e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">종료일</label>
            <input
              type="date"
              value={form.end_date}
              onChange={(e) => set('end_date', e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">일일 한도</label>
            <input
              type="number"
              value={form.daily_limit}
              onChange={(e) => set('daily_limit', e.target.value)}
              className="w-full border rounded-md px-3 py-2 text-sm"
              min="1"
              required
            />
          </div>
        </div>

        {/* 키워드 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">키워드 (쉼표 구분)</label>
          <textarea
            value={form.keywords}
            onChange={(e) => set('keywords', e.target.value)}
            rows={3}
            className="w-full border rounded-md px-3 py-2 text-sm"
            placeholder="키워드1, 키워드2, 키워드3"
            required
          />
        </div>

        {/* 버튼 */}
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={() => setForm(INITIAL)}
            className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
          >
            초기화
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
          >
            {submitting ? '등록 중...' : '추가'}
          </button>
        </div>
      </form>
    </div>
  );
}
