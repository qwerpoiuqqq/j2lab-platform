import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { campaignTemplatesApi } from '@/api/campaignTemplates';
import Button from '@/components/common/Button';
import Modal from '@/components/common/Modal';
import { getCampaignTypeLabel } from '@/utils/format';
import type { CampaignTemplate, ModuleInfo } from '@/types';

// superap.io campaign type options
const CAMPAIGN_TYPE_OPTIONS = [
  { group: '플레이스', options: [
    '기본 플레이스 저장하기', '플레이스 URL 공유하기', '컵페 클릭 후 저장',
    '플레이스 방문 & 저장', 'keep 공유', '알림받기',
    '검색 후 정답 입력', '서치 커스텀 미션(스크린샷 제출 타입)',
  ]},
  { group: '퀴즈 맞추기', options: [
    '대표자명 맞추기', '상품 클릭 후 태그 단어 맞추기',
    '상품 클릭 후 대표자명 맞추기', '플레이스 퀴즈', '서치 플레이스 퀴즈',
  ]},
  { group: '상품클릭', options: [
    '기본 상품클릭', '상품 클릭 후 상품평',
    '무신사 상품 평하기', '카카오톡 선물하기 평하기',
  ]},
  { group: '유튜브', options: [
    '시청하기', '구독하기', '쇼츠 좋아요', '영상 좋아요', '영상 좋아요 & 채널 구독',
  ]},
  { group: 'SNS', options: [
    '인스타그램 팔로우', '인스타그램 게시물 좋아요',
  ]},
];

const HASHTAG_OPTIONS = [
  '#cpc_detail_place', '#cpc_detail_place_quiz', '#cpc_detail_ceo_name',
  '#cpc_detail_click_tag', '#cpc_detail_click_ceo_name',
  '#place_save_tab', '#place_save_search', '#place_save_default',
  '#place_save_share', '#place_save_click', '#place_save_home',
  '#place_save_keep', '#place_save_noti',
];

export default function CampaignTemplatesPage() {
  const queryClient = useQueryClient();
  const [editId, setEditId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const { data, isLoading: loading } = useQuery({
    queryKey: ['campaign-templates'],
    queryFn: () => campaignTemplatesApi.list({ size: 100 }),
  });
  const templates: CampaignTemplate[] = data?.items ?? [];

  const { data: modulesData } = useQuery({
    queryKey: ['modules'],
    queryFn: () => campaignTemplatesApi.getModules(),
  });
  const modules: ModuleInfo[] = modulesData?.modules ?? [];

  const deleteMutation = useMutation({
    mutationFn: (id: number) => campaignTemplatesApi.delete(id),
    onSuccess: () => {
      setMessage({ type: 'success', text: '삭제되었습니다.' });
      queryClient.invalidateQueries({ queryKey: ['campaign-templates'] });
    },
    onError: (err: any) => {
      setMessage({ type: 'error', text: err?.response?.data?.detail || '삭제 실패' });
    },
  });

  const handleDelete = (id: number, typeName: string) => {
    if (!confirm(`템플릿 '${typeName}'을(를) 삭제하시겠습니까?`)) return;
    setMessage(null);
    deleteMutation.mutate(id);
  };

  const handleSaved = () => {
    setMessage({ type: 'success', text: '저장되었습니다.' });
    queryClient.invalidateQueries({ queryKey: ['campaign-templates'] });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">템플릿 관리</h1>
          <p className="mt-1 text-sm text-gray-400">
            캠페인 등록 시 사용할 템플릿을 관리합니다.
            {templates.length > 0 && ` (총 ${templates.length}개)`}
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => { setShowCreate(true); setMessage(null); }}
        >
          템플릿 추가
        </Button>
      </div>

      {message && (
        <div
          className={`rounded-xl p-3 text-sm ${
            message.type === 'success'
              ? 'bg-green-900/20 text-green-400 border border-green-800'
              : 'bg-red-900/20 text-red-400 border border-red-800'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="bg-surface rounded-xl border border-border shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-400">로딩 중...</div>
        ) : templates.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-400 mb-2">등록된 템플릿이 없습니다.</p>
            <p className="text-sm text-gray-400 mb-4">
              템플릿을 생성하여 캠페인 자동화를 시작하세요.
            </p>
            <Button variant="primary" onClick={() => setShowCreate(true)}>
              첫 템플릿 만들기
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-raised">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">캠페인 이름</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">코드</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">캠페인 타입</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">모듈</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">상태</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase">작업</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {templates.map((t) => (
                  <tr key={t.id} className="hover:bg-surface-raised transition-colors">
                    <td className="px-6 py-4 font-medium text-gray-100">{t.type_name}</td>
                    <td className="px-6 py-4">
                      <code className="text-xs bg-surface-raised px-2 py-0.5 rounded text-primary-400">{t.code}</code>
                    </td>
                    <td className="px-6 py-4 text-gray-400">
                      {t.campaign_type_selection ? getCampaignTypeLabel(t.campaign_type_selection) : '-'}
                    </td>
                    <td className="px-6 py-4 text-gray-400 text-xs">
                      {t.modules.length > 0 ? t.modules.join(', ') : '-'}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          t.is_active
                            ? 'bg-green-900/30 text-green-400'
                            : 'bg-surface-raised text-gray-400'
                        }`}
                      >
                        {t.is_active ? '활성' : '비활성'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-2">
                        <button
                          onClick={() => { setEditId(t.id); setMessage(null); }}
                          className="text-sm text-primary-400 hover:text-primary-300 font-medium"
                        >
                          편집
                        </button>
                        <button
                          onClick={() => handleDelete(t.id, t.type_name)}
                          disabled={deleteMutation.isPending}
                          className="text-sm text-red-500 hover:text-red-400 font-medium disabled:opacity-50"
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
        )}
      </div>

      {showCreate && (
        <TemplateEditModal
          templateId={null}
          modules={modules}
          onClose={() => setShowCreate(false)}
          onSaved={handleSaved}
        />
      )}

      {editId !== null && (
        <TemplateEditModal
          templateId={editId}
          modules={modules}
          onClose={() => setEditId(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}

// ---- Inline TemplateEditModal ----

interface TemplateEditModalProps {
  templateId: number | null;
  modules: ModuleInfo[];
  onClose: () => void;
  onSaved: () => void;
}

function TemplateEditModal({ templateId, modules, onClose, onSaved }: TemplateEditModalProps) {
  const isCreate = templateId === null;

  const [loading, setLoading] = useState(!isCreate);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [typeName, setTypeName] = useState('');
  const [code, setCode] = useState('');
  const [campaignType, setCampaignType] = useState('');
  const [enabledModules, setEnabledModules] = useState<Set<string>>(new Set());
  const [conversionText, setConversionText] = useState('');
  const [descTemplate, setDescTemplate] = useState('');
  const [hintText, setHintText] = useState('');
  const [links, setLinks] = useState<string[]>(['']);
  const [hashtag, setHashtag] = useState('');
  const [imageUrl200, setImageUrl200] = useState('');
  const [imageUrl720, setImageUrl720] = useState('');
  const [stepsStart, setStepsStart] = useState('');
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    if (isCreate || !templateId) return;
    campaignTemplatesApi
      .get(templateId)
      .then((d) => {
        setTypeName(d.type_name);
        setCode(d.code || '');
        setCampaignType(d.campaign_type_selection || '');
        setEnabledModules(new Set(d.modules));
        setDescTemplate(d.description_template);
        setHintText(d.hint_text);
        setLinks(d.links.length > 0 ? d.links : ['']);
        setHashtag(d.hashtag || '');
        setImageUrl200(d.image_url_200x600 || '');
        setImageUrl720(d.image_url_720x780 || '');
        setConversionText(d.conversion_text_template || '');
        setStepsStart(d.steps_start || '');
        setIsActive(d.is_active);
      })
      .catch(() => setError('템플릿 정보를 불러올 수 없습니다.'))
      .finally(() => setLoading(false));
  }, [templateId, isCreate]);

  const toggleModule = (name: string) => {
    setEnabledModules((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const addLink = () => setLinks((prev) => [...prev, '']);
  const updateLink = (i: number, val: string) =>
    setLinks((prev) => prev.map((l, idx) => (idx === i ? val : l)));
  const removeLink = (i: number) => setLinks((prev) => prev.filter((_, idx) => idx !== i));

  const handleSave = async () => {
    if (!typeName.trim()) { setError('캠페인 이름을 입력해주세요.'); return; }
    if (!descTemplate.trim()) { setError('참여 방법 설명을 입력해주세요.'); return; }
    if (!hintText.trim()) { setError('정답 힌트를 입력해주세요.'); return; }

    setSaving(true);
    setError(null);

    const filteredLinks = links.filter((l) => l.trim());
    const payload = {
      type_name: typeName.trim(),
      code: code.trim() || undefined,
      description_template: descTemplate,
      hint_text: hintText,
      campaign_type_selection: campaignType || undefined,
      links: filteredLinks,
      hashtag: hashtag || undefined,
      image_url_200x600: imageUrl200 || undefined,
      image_url_720x780: imageUrl720 || undefined,
      conversion_text_template: conversionText.trim() || undefined,
      steps_start: stepsStart.trim() || undefined,
      modules: Array.from(enabledModules),
      ...(!isCreate ? { is_active: isActive } : {}),
    };

    try {
      if (isCreate) {
        await campaignTemplatesApi.create(payload);
      } else {
        await campaignTemplatesApi.update(templateId!, payload);
      }
      onSaved();
      onClose();
    } catch (e: any) {
      setError(e?.response?.data?.detail || '저장에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  // Variable guide - which variables are available
  const activeModules = modules.filter((m) => enabledModules.has(m.name));

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={isCreate ? '템플릿 추가' : '템플릿 편집'}
      size="xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>취소</Button>
          <Button variant="primary" onClick={handleSave} loading={saving}>
            {isCreate ? '추가' : '저장'}
          </Button>
        </>
      }
    >
      {loading ? (
        <div className="text-center py-8 text-gray-400">로딩 중...</div>
      ) : (
        <div className="flex gap-6">
          {/* Main form */}
          <div className="flex-1 min-w-0 space-y-5">
            {/* Section: Basic info */}
            <FormSection title="기본 정보">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  캠페인 이름 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={typeName}
                  onChange={(e) => setTypeName(e.target.value)}
                  className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                  placeholder="예: 트래픽, 저장하기, 명소"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  코드 <span className="text-xs text-gray-400 font-normal">(캠페인 타입 매칭용, 미입력 시 자동 생성)</span>
                </label>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                  placeholder="예: traffic, save, landmark, traffic1"
                />
                <p className="text-xs text-gray-400 mt-1">
                  파이프라인에서 캠페인 타입과 매칭됩니다. 예: traffic, save, landmark, traffic1, share_directions_traffic
                </p>
              </div>
              {!isCreate && (
                <div className="flex items-center gap-3">
                  <label className="text-sm font-medium text-gray-300">활성 상태</label>
                  <button
                    type="button"
                    onClick={() => setIsActive(!isActive)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      isActive ? 'bg-primary-500' : 'bg-gray-300'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-surface transition-transform ${
                        isActive ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                  <span className={`text-xs ${isActive ? 'text-green-600' : 'text-gray-400'}`}>
                    {isActive ? '활성' : '비활성'}
                  </span>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  superap.io 캠페인 타입
                </label>
                <select
                  value={campaignType}
                  onChange={(e) => setCampaignType(e.target.value)}
                  className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm bg-surface focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                >
                  <option value="">-- 선택 --</option>
                  {CAMPAIGN_TYPE_OPTIONS.map((group) => (
                    <optgroup key={group.group} label={group.group}>
                      {group.options.map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            </FormSection>

            {/* Section: Module settings */}
            <FormSection title="모듈 & 변수 설정">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">사용할 모듈</label>
                <div className="space-y-2">
                  {modules.map((m) => {
                    const isActive = enabledModules.has(m.name);
                    return (
                      <div
                        key={m.name}
                        onClick={() => toggleModule(m.name)}
                        className={`cursor-pointer border rounded-lg p-3 transition-all ${
                          isActive
                            ? 'border-primary-500 bg-primary-900/20'
                            : 'border-border hover:border-border-strong'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                              isActive ? 'bg-primary-500 border-primary-500' : 'border-border-strong'
                            }`}
                          >
                            {isActive && (
                              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </div>
                          <div>
                            <span className="text-sm font-medium text-gray-200">{m.description}</span>
                            <span className="text-xs text-gray-400 ml-2">
                              변수: {m.variables.map((v) => `&${v}&`).join(', ')}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">전환 인식 텍스트 (선택)</label>
                <input
                  type="text"
                  value={conversionText}
                  onChange={(e) => setConversionText(e.target.value)}
                  className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                  placeholder="예: &명소명& ㄱㄱ"
                />
                <p className="text-xs text-gray-400 mt-1">
                  변수를 사용하면 캠페인 등록 시 자동 치환됩니다. 비워두면 걸음수 기반 전환을 사용합니다.
                </p>
              </div>

              {enabledModules.has('steps') && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">걸음수 출발지 (선택)</label>
                  <input
                    type="text"
                    value={stepsStart}
                    onChange={(e) => setStepsStart(e.target.value)}
                    className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                    placeholder="예: &명소명& 입구 (비워두면 명소를 출발지로 사용)"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    걸음수 계산 시 출발지를 지정합니다. 변수 사용 가능. 비워두면 선택된 명소가 출발지가 됩니다.
                  </p>
                </div>
              )}
            </FormSection>

            {/* Section: Participation settings */}
            <FormSection title="참여 설정">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  참여 방법 설명 <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={descTemplate}
                  onChange={(e) => setDescTemplate(e.target.value)}
                  rows={5}
                  className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                  placeholder="예: &상호명& 근처 &명소명&에서 출발하여 &걸음수& 걸음을 걸으세요."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  정답 힌트 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={hintText}
                  onChange={(e) => setHintText(e.target.value)}
                  className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                  placeholder="예: 참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수 맞추기"
                />
              </div>
            </FormSection>

            {/* Section: Media & Links */}
            <FormSection title="미디어 & 링크 (선택)">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">링크</label>
                {links.map((link, i) => (
                  <div key={i} className="flex gap-2 mb-1.5">
                    <input
                      type="text"
                      value={link}
                      onChange={(e) => updateLink(i, e.target.value)}
                      className="flex-1 border border-border-strong rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                      placeholder={`링크 ${i + 1}`}
                    />
                    {links.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeLink(i)}
                        className="text-red-400 hover:text-red-400 text-sm px-2"
                      >
                        삭제
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addLink}
                  className="text-sm text-primary-400 hover:text-primary-300"
                >
                  + 링크 추가
                </button>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">해시태그</label>
                <select
                  value={hashtag}
                  onChange={(e) => setHashtag(e.target.value)}
                  className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm bg-surface focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                >
                  <option value="">-- 선택 안 함 --</option>
                  {HASHTAG_OPTIONS.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">이미지 URL (200x600)</label>
                  <input
                    type="text"
                    value={imageUrl200}
                    onChange={(e) => setImageUrl200(e.target.value)}
                    className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                    placeholder="선택사항"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1">이미지 URL (720x780)</label>
                  <input
                    type="text"
                    value={imageUrl720}
                    onChange={(e) => setImageUrl720(e.target.value)}
                    className="w-full border border-border-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400/40 bg-surface text-gray-200"
                    placeholder="선택사항"
                  />
                </div>
              </div>
            </FormSection>

            {error && <div className="text-sm text-red-600">{error}</div>}
          </div>

          {/* Sidebar: Variable guide */}
          <div className="w-56 flex-shrink-0 hidden lg:block">
            <div className="bg-blue-900/20 border border-blue-800 rounded-xl p-4 sticky top-0">
              <h3 className="text-sm font-semibold text-blue-400 mb-3">
                사용 가능한 변수
              </h3>

              <div className="mb-3">
                <div className="text-xs font-medium text-primary-300 mb-1.5">기본 제공</div>
                <VariableItem variable="&상호명&" description="마스킹된 상호명" />
              </div>

              {activeModules.length > 0 ? (
                <div className="mb-3">
                  <div className="text-xs font-medium text-primary-300 mb-1.5">선택된 모듈</div>
                  <div className="space-y-2.5">
                    {activeModules.map((m) => (
                      <div key={m.name}>
                        <div className="text-xs text-blue-400 font-medium mb-1">{m.description}</div>
                        <div className="ml-2 space-y-1">
                          {m.variables.map((v) => (
                            <VariableItem key={v} variable={`&${v}&`} description={v} />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="text-xs text-blue-500 italic mb-3">
                  모듈을 선택하면 추가 변수가 표시됩니다
                </div>
              )}

              <div className="border-t border-blue-800 pt-3 mt-3">
                <div className="text-xs text-blue-400 leading-relaxed">
                  참여 방법 설명, 정답 힌트, 전환 인식 텍스트에서 사용할 수 있습니다.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ---- Helper components ----

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold text-gray-200 pb-1 border-b border-border">{title}</h4>
      {children}
    </div>
  );
}

function VariableItem({ variable, description }: { variable: string; description: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <code className="bg-blue-900/30 px-1.5 py-0.5 rounded text-blue-400 font-mono whitespace-nowrap">
        {variable}
      </code>
      <span className="text-primary-300">{description}</span>
    </div>
  );
}
