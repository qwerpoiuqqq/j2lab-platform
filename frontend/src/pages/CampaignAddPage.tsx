import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { campaignsApi } from '@/api/campaigns';
import { campaignAccountsApi } from '@/api/campaignAccounts';
import { campaignTemplatesApi } from '@/api/campaignTemplates';
import Button from '@/components/common/Button';
import type { SuperapAccount, CampaignTemplate } from '@/types';

interface FormData {
  campaign_code: string;
  account_id: string;
  agency_name: string;
  place_name: string;
  place_url: string;
  template_id: string;
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
  template_id: '',
  start_date: '',
  end_date: '',
  daily_limit: '',
  keywords: '',
};

export default function CampaignAddPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormData>(INITIAL);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);
  const [verifyOk, setVerifyOk] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  // Fetch accounts
  const { data: accountsData } = useQuery({
    queryKey: ['superap-accounts'],
    queryFn: () => campaignAccountsApi.list({ size: 100 }),
  });
  const accounts: SuperapAccount[] = accountsData?.items ?? [];

  // Fetch templates
  const { data: templatesData } = useQuery({
    queryKey: ['campaign-templates'],
    queryFn: () => campaignTemplatesApi.list({ size: 100, is_active: true }),
  });
  const templates: CampaignTemplate[] = templatesData?.items ?? [];

  const set = (key: keyof FormData, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleVerify = async () => {
    if (!form.campaign_code.trim()) return;
    try {
      const res = await campaignsApi.verifyCode(form.campaign_code);
      if (res.exists) {
        setVerifyMsg('이미 등록된 캠페인 번호입니다.');
        setVerifyOk(false);
      } else {
        setVerifyMsg('사용 가능한 캠페인 번호입니다.');
        setVerifyOk(true);
      }
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
      await campaignsApi.createManual({
        campaign_code: form.campaign_code,
        account_id: Number(form.account_id),
        place_url: form.place_url,
        place_name: form.place_name || undefined,
        agency_name: form.agency_name || undefined,
        template_id: Number(form.template_id),
        start_date: form.start_date,
        end_date: form.end_date,
        daily_limit: Number(form.daily_limit),
        keywords: form.keywords,
      });
      setResult({ success: true, message: '캠페인이 등록되었습니다.' });
      setForm(INITIAL);
      setVerifyMsg(null);
      setVerifyOk(false);
      navigate('/campaigns');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '등록에 실패했습니다.';
      setResult({ success: false, message: typeof msg === 'string' ? msg : '등록에 실패했습니다.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">캠페인 직접 추가</h1>
        <p className="mt-1 text-sm text-gray-500">
          수동으로 캠페인을 등록합니다.
        </p>
      </div>

      {result && (
        <div
          className={`rounded-xl p-4 text-sm ${
            result.success
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {result.message}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
        {/* Campaign code */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            캠페인 번호
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={form.campaign_code}
              onChange={(e) => {
                set('campaign_code', e.target.value);
                setVerifyMsg(null);
                setVerifyOk(false);
              }}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="superap 캠페인 번호"
              required
            />
            <Button type="button" variant="secondary" size="sm" onClick={handleVerify}>
              확인
            </Button>
          </div>
          {verifyMsg && (
            <p className={`text-xs mt-1 ${verifyOk ? 'text-green-600' : 'text-red-600'}`}>
              {verifyMsg}
            </p>
          )}
        </div>

        {/* Account + Agency */}
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
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            >
              <option value="">선택</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.user_id_superap} {a.agency_name ? `(${a.agency_name})` : ''}
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
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="대행사명"
            />
          </div>
        </div>

        {/* Place info */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">플레이스 URL</label>
            <input
              type="text"
              value={form.place_url}
              onChange={(e) => set('place_url', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
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
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="비워두면 자동 추출"
            />
          </div>
        </div>

        {/* Template selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">캠페인 템플릿</label>
          <select
            value={form.template_id}
            onChange={(e) => set('template_id', e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            required
          >
            <option value="">선택</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.type_name} {t.campaign_type_selection ? `(${t.campaign_type_selection})` : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Date + daily limit */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">시작일</label>
            <input
              type="date"
              value={form.start_date}
              onChange={(e) => set('start_date', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">종료일</label>
            <input
              type="date"
              value={form.end_date}
              onChange={(e) => set('end_date', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">일일 한도</label>
            <input
              type="number"
              value={form.daily_limit}
              onChange={(e) => set('daily_limit', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              min="1"
              required
            />
          </div>
        </div>

        {/* Keywords */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">키워드 (쉼표 구분)</label>
          <textarea
            value={form.keywords}
            onChange={(e) => set('keywords', e.target.value)}
            rows={3}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            placeholder="키워드1, 키워드2, 키워드3"
            required
          />
        </div>

        {/* Buttons */}
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={() => setForm(INITIAL)}>
            초기화
          </Button>
          <Button type="submit" variant="primary" loading={submitting}>
            추가
          </Button>
        </div>
      </form>
    </div>
  );
}
