import { useEffect, useState } from 'react';
import Modal from '../common/Modal';
import FormSection from '../common/FormSection';
import RequiredLabel from '../common/RequiredLabel';
import VariableGuideBox from './VariableGuideBox';
import type { TemplateCreate, TemplateUpdate, ModuleInfo } from '../../types';
import { fetchTemplateDetail, createTemplate, updateTemplate, getErrorMessage } from '../../services/api';

// superap.io 캠페인 타입 옵션
const CAMPAIGN_TYPE_OPTIONS = [
  { group: '플레이스', options: [
    '기본 플레이스 저장하기',
    '플레이스 URL 공유하기',
    '컵페 클릭 후 저장',
    '플레이스 방문 & 저장',
    'keep 공유',
    '알림받기',
    '검색 후 정답 입력',
    '서치 커스텀 미션(스크린샷 제출 타입)',
  ]},
  { group: '퀴즈 맞추기', options: [
    '대표자명 맞추기',
    '상품 클릭 후 태그 단어 맞추기',
    '상품 클릭 후 대표자명 맞추기',
    '플레이스 퀴즈',
    '서치 플레이스 퀴즈',
  ]},
  { group: '상품클릭', options: [
    '기본 상품클릭',
    '상품 클릭 후 상품평',
    '무신사 상품 평하기',
    '카카오톡 선물하기 평하기',
  ]},
  { group: '알림받기', options: [
    '기본 알림받기',
    '상품 클릭 후 알림받기',
  ]},
  { group: '유튜브', options: [
    '시청하기',
    '구독하기',
    '쇼츠 좋아요',
    '영상 좋아요',
    '영상 좋아요 & 채널 구독',
  ]},
  { group: 'SNS', options: [
    '인스타그램 팔로우',
    '인스타그램 게시물 좋아요',
  ]},
];

const HASHTAG_OPTIONS = [
  '#cpc_detail_place',
  '#cpc_detail_place_quiz',
  '#cpc_detail_ceo_name',
  '#cpc_detail_click_tag',
  '#cpc_detail_click_ceo_name',
  '#place_save_tab',
  '#place_save_search',
  '#place_save_default',
  '#place_save_share',
  '#place_save_click',
  '#place_save_home',
  '#place_save_keep',
  '#place_save_noti',
];

type ConversionMode = 'steps' | 'text';

interface TemplateEditModalProps {
  templateId: number | null;
  modules: ModuleInfo[];
  onClose: () => void;
  onSaved: () => void;
}

export default function TemplateEditModal({
  templateId,
  modules,
  onClose,
  onSaved,
}: TemplateEditModalProps) {
  const isCreate = templateId === null;

  const [loading, setLoading] = useState(!isCreate);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [typeName, setTypeName] = useState('');
  const [campaignType, setCampaignType] = useState('');
  const [enabledModules, setEnabledModules] = useState<Set<string>>(new Set());
  const [conversionMode, setConversionMode] = useState<ConversionMode>('steps');
  const [conversionText, setConversionText] = useState('');
  const [descTemplate, setDescTemplate] = useState('');
  const [hintText, setHintText] = useState('');
  const [links, setLinks] = useState<string[]>(['']);
  const [hashtag, setHashtag] = useState('');
  const [stepsStart, setStepsStart] = useState('');
  const [imageUrl200, setImageUrl200] = useState('');
  const [imageUrl720, setImageUrl720] = useState('');

  useEffect(() => {
    if (isCreate) return;
    fetchTemplateDetail(templateId)
      .then((d) => {
        setTypeName(d.type_name);
        setCampaignType(d.campaign_type_selection || '');
        setEnabledModules(new Set(d.modules));
        setDescTemplate(d.description_template);
        setHintText(d.hint_text);
        setLinks(d.links.length > 0 ? d.links : ['']);
        setHashtag(d.hashtag || '');
        setStepsStart(d.steps_start || '');
        setImageUrl200(d.image_url_200x600 || '');
        setImageUrl720(d.image_url_720x780 || '');
        if (d.conversion_text_template) {
          setConversionMode('text');
          setConversionText(d.conversion_text_template);
        } else {
          setConversionMode('steps');
          setConversionText('');
        }
      })
      .catch(() => setError('템플릿 정보를 불러올 수 없습니다.'))
      .finally(() => setLoading(false));
  }, [templateId, isCreate]);

  const toggleModule = (moduleId: string) => {
    setEnabledModules((prev) => {
      const next = new Set(prev);
      if (next.has(moduleId)) next.delete(moduleId);
      else next.add(moduleId);
      return next;
    });
  };

  const handleConversionModeChange = (mode: ConversionMode) => {
    setConversionMode(mode);
    if (mode === 'steps') {
      setConversionText('');
      setEnabledModules((prev) => {
        const next = new Set(prev);
        next.add('steps');
        return next;
      });
    }
  };

  const addLink = () => setLinks((prev) => [...prev, '']);
  const updateLink = (i: number, val: string) =>
    setLinks((prev) => prev.map((l, idx) => (idx === i ? val : l)));
  const removeLink = (i: number) => setLinks((prev) => prev.filter((_, idx) => idx !== i));

  const handleSave = async () => {
    if (!typeName.trim()) {
      setError('캠페인 이름을 입력해주세요.');
      return;
    }
    if (!descTemplate.trim()) {
      setError('참여 방법 설명을 입력해주세요.');
      return;
    }
    if (!hintText.trim()) {
      setError('정답 힌트를 입력해주세요.');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const filteredLinks = links.filter((l) => l.trim());
      const convTextValue = conversionMode === 'text' && conversionText.trim()
        ? conversionText.trim()
        : undefined;

      const stepsStartValue = stepsStart.trim() || undefined;

      if (isCreate) {
        const data: TemplateCreate = {
          type_name: typeName.trim(),
          description_template: descTemplate,
          hint_text: hintText,
          campaign_type_selection: campaignType || undefined,
          links: filteredLinks,
          hashtag: hashtag || undefined,
          image_url_200x600: imageUrl200 || undefined,
          image_url_720x780: imageUrl720 || undefined,
          conversion_text_template: convTextValue,
          steps_start: stepsStartValue,
          modules: Array.from(enabledModules),
        };
        await createTemplate(data);
      } else {
        const data: TemplateUpdate = {
          type_name: typeName.trim(),
          description_template: descTemplate,
          hint_text: hintText,
          campaign_type_selection: campaignType || undefined,
          links: filteredLinks,
          hashtag: hashtag || undefined,
          image_url_200x600: imageUrl200 || undefined,
          image_url_720x780: imageUrl720 || undefined,
          conversion_text_template: convTextValue ?? null,
          steps_start: stepsStartValue ?? null,
          modules: Array.from(enabledModules),
        };
        await updateTemplate(templateId, data);
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  // 미디어 & 링크 섹션에 값이 있는지 확인 (편집 모드에서 기본 열림)
  const hasMediaValues = !isCreate && !!(
    links.some((l) => l.trim()) || hashtag || imageUrl200 || imageUrl720
  );

  return (
    <Modal open onClose={onClose} title={isCreate ? '템플릿 추가' : '템플릿 편집'} extraWide>
      {loading ? (
        <div className="text-center py-8 text-gray-500">로딩 중...</div>
      ) : (
        <div className="flex gap-6">
          {/* 메인 폼 */}
          <div className="flex-1 min-w-0 space-y-4">

            {/* 섹션 1: 기본 정보 */}
            <FormSection title="기본 정보" badge="필수">
              <div>
                <RequiredLabel required>캠페인 이름 (엑셀 업로드 시 사용하는 타입명)</RequiredLabel>
                <input
                  type="text"
                  value={typeName}
                  onChange={(e) => setTypeName(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  placeholder="예: 트래픽, 저장하기, 명소"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  superap.io 캠페인 타입
                </label>
                <select
                  value={campaignType}
                  onChange={(e) => setCampaignType(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm bg-white"
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

            {/* 섹션 2: 모듈 & 변수 설정 */}
            <FormSection title="모듈 & 변수 설정" badge="필수">
              {/* 모듈 선택 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">사용할 모듈</label>
                <div className="space-y-2">
                  {modules.map((m) => {
                    const isActive = enabledModules.has(m.module_id);
                    return (
                      <div
                        key={m.module_id}
                        onClick={() => toggleModule(m.module_id)}
                        className={`cursor-pointer border rounded-lg p-3 transition-all ${
                          isActive
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                              isActive ? 'bg-blue-500 border-blue-500' : 'border-gray-300'
                            }`}
                          >
                            {isActive && (
                              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </div>
                          <div>
                            <span className="text-sm font-medium text-gray-800">{m.description}</span>
                            <span className="text-xs text-gray-400 ml-2">
                              출력: {m.output_variables.map((v) => `&${v}&`).join(', ')}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 걸음수 출발지 설정 (steps 모듈 활성 시) */}
              {enabledModules.has('steps') && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    걸음수 출발지
                  </label>
                  <input
                    type="text"
                    value={stepsStart}
                    onChange={(e) => setStepsStart(e.target.value)}
                    className="w-full border rounded-md px-3 py-2 text-sm"
                    placeholder="비워두면 명소명을 출발지로 사용"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    특정 장소를 출발지로 지정할 수 있습니다. 비워두면 명소 모듈에서 선택한 명소가 출발지가 됩니다.
                  </p>
                </div>
              )}

              {/* 전환 인식 방식 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">전환 인식 방식</label>
                <div className="flex gap-4 border rounded-md p-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="conversion_mode"
                      checked={conversionMode === 'steps'}
                      onChange={() => handleConversionModeChange('steps')}
                    />
                    <span className="text-sm">걸음수 (steps 모듈 필요)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="conversion_mode"
                      checked={conversionMode === 'text'}
                      onChange={() => handleConversionModeChange('text')}
                    />
                    <span className="text-sm">텍스트 입력</span>
                  </label>
                </div>
                {conversionMode === 'text' && (
                  <div className="mt-2">
                    <input
                      type="text"
                      value={conversionText}
                      onChange={(e) => setConversionText(e.target.value)}
                      className="w-full border rounded-md px-3 py-2 text-sm"
                      placeholder="예: &명소명& ㄱㄱ"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      변수를 사용하면 캠페인 등록 시 자동 치환됩니다.
                    </p>
                  </div>
                )}
              </div>
            </FormSection>

            {/* 섹션 3: 참여 설정 */}
            <FormSection title="참여 설정" badge="필수">
              <div>
                <RequiredLabel required>참여 방법 설명</RequiredLabel>
                <textarea
                  value={descTemplate}
                  onChange={(e) => setDescTemplate(e.target.value)}
                  rows={6}
                  className="w-full border rounded-md px-3 py-2 text-sm font-mono"
                  placeholder="예: &상호명& 근처 &명소명&에서 출발하여 &걸음수& 걸음을 걸으세요."
                />
                <p className="text-xs text-gray-400 mt-1">
                  {'{{image|URL}}'} 형식으로 이미지 삽입 가능. 변수는 오른쪽 가이드를 참고하세요.
                </p>
              </div>
              <div>
                <RequiredLabel required>정답 힌트</RequiredLabel>
                <input
                  type="text"
                  value={hintText}
                  onChange={(e) => setHintText(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm"
                  placeholder="예: 참여 방법에 있는 출발지에서 목적지까지 [가장 빠른] 걸음 수 맞추기"
                />
                <p className="text-xs text-gray-400 mt-1">
                  변수 사용 가능 - 캠페인 등록 시 실제 값으로 자동 치환됩니다.
                </p>
              </div>
            </FormSection>

            {/* 섹션 4: 미디어 & 링크 (선택, 접기 가능) */}
            <FormSection title="미디어 & 링크" badge="선택" collapsible defaultOpen={hasMediaValues}>
              {/* 링크 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">링크</label>
                {links.map((link, i) => (
                  <div key={i} className="flex gap-2 mb-1">
                    <input
                      type="text"
                      value={link}
                      onChange={(e) => updateLink(i, e.target.value)}
                      className="flex-1 border rounded-md px-3 py-1.5 text-sm"
                      placeholder={`링크 ${i + 1}`}
                    />
                    {links.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeLink(i)}
                        className="text-red-400 hover:text-red-600 text-sm px-2"
                      >
                        삭제
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addLink}
                  className="text-sm text-blue-500 hover:text-blue-700"
                >
                  + 링크 추가
                </button>
              </div>

              {/* 해시태그 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">해시태그</label>
                <select
                  value={hashtag}
                  onChange={(e) => setHashtag(e.target.value)}
                  className="w-full border rounded-md px-3 py-2 text-sm bg-white"
                >
                  <option value="">-- 선택 안 함 --</option>
                  {HASHTAG_OPTIONS.map((h) => (
                    <option key={h} value={h}>{h}</option>
                  ))}
                </select>
              </div>

              {/* 이미지 URL */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    이미지 URL (200x600)
                  </label>
                  <input
                    type="text"
                    value={imageUrl200}
                    onChange={(e) => setImageUrl200(e.target.value)}
                    className="w-full border rounded-md px-3 py-2 text-sm"
                    placeholder="선택사항"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    이미지 URL (720x780)
                  </label>
                  <input
                    type="text"
                    value={imageUrl720}
                    onChange={(e) => setImageUrl720(e.target.value)}
                    className="w-full border rounded-md px-3 py-2 text-sm"
                    placeholder="선택사항"
                  />
                </div>
              </div>
            </FormSection>

            {/* 에러 메시지 + 저장 버튼 */}
            {error && <div className="text-sm text-red-600">{error}</div>}

            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm border rounded-md hover:bg-gray-50"
              >
                취소
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
              >
                {saving ? '저장 중...' : isCreate ? '추가' : '저장'}
              </button>
            </div>
          </div>

          {/* 사이드바: 변수 가이드 */}
          <div className="w-56 flex-shrink-0 hidden md:block">
            <VariableGuideBox enabledModules={enabledModules} modules={modules} />
          </div>
        </div>
      )}
    </Modal>
  );
}
