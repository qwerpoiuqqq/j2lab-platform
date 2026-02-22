// ============================================================
// 계정 (Account)
// ============================================================
export interface Account {
  id: number;
  user_id: string;
  agency_name: string | null;
  is_active: boolean;
  campaign_count: number;
  created_at: string | null;
}

export interface AccountListResponse {
  accounts: Account[];
  total: number;
}

export interface AccountCreate {
  user_id: string;
  password: string;
  agency_name?: string;
}

export interface AccountUpdate {
  user_id?: string;
  password?: string;
  agency_name?: string;
  is_active?: boolean;
}

export interface AccountDeleteResponse {
  success: boolean;
  message: string;
  deleted_type: 'hard' | 'soft';
}

// ============================================================
// 대행사 (Agency)
// ============================================================
export interface Agency {
  agency_name: string;
  campaign_count: number;
}

export interface AgencyListResponse {
  agencies: Agency[];
}

// ============================================================
// 대시보드 통계
// ============================================================
export interface DashboardStats {
  total_campaigns: number;
  active_campaigns: number;
  exhausted_today: number;
  keyword_warnings: number;
}

// ============================================================
// 캠페인 (Campaign)
// ============================================================
export interface ExtensionHistoryItem {
  round: number;
  start_date: string;
  end_date: string;
  daily_limit: number;
  total_limit_added: number;
  keywords_added: number;
  extended_at: string;
}

export interface CampaignListItem {
  id: number;
  campaign_code: string | null;
  account_id: number | null;
  agency_name: string | null;
  place_name: string;
  campaign_type: string;
  status: string;
  current_conversions: number;
  total_limit: number | null;
  daily_limit: number;
  start_date: string;
  end_date: string;
  days_running: number;
  keyword_status: 'normal' | 'warning' | 'critical';
  keyword_remaining: number;
  keyword_total: number;
  last_keyword_change: string | null;
  registration_step: string | null;
  registration_message: string | null;
  extension_history: ExtensionHistoryItem[] | null;
}

export interface CampaignListResponse {
  campaigns: CampaignListItem[];
  total: number;
  page: number;
  pages: number;
}

export interface KeywordInfo {
  id: number;
  keyword: string;
  is_used: boolean;
  used_at: string | null;
}

export interface CampaignDetail {
  id: number;
  campaign_code: string | null;
  account_id: number | null;
  agency_name: string | null;
  place_name: string;
  place_url: string;
  place_id: string | null;
  campaign_type: string;
  status: string;
  start_date: string;
  end_date: string;
  daily_limit: number;
  total_limit: number | null;
  current_conversions: number;
  landmark_name: string | null;
  step_count: number | null;
  days_running: number;
  keyword_status: 'normal' | 'warning' | 'critical';
  keyword_remaining: number;
  keyword_total: number;
  keyword_used: number;
  last_keyword_change: string | null;
  keywords: KeywordInfo[];
  registered_at: string | null;
  created_at: string | null;
  extension_history: ExtensionHistoryItem[] | null;
}

export interface CampaignDeleteResponse {
  success: boolean;
  message: string;
}

export interface BatchDeleteResponse {
  success: boolean;
  deleted_count: number;
  message: string;
}

// ============================================================
// 캠페인 설정 수정
// ============================================================
export interface CampaignSettingsUpdate {
  campaign_code?: string;
  place_name?: string;
  agency_name?: string | null;
  daily_limit?: number;
  total_limit?: number;
  start_date?: string;
  end_date?: string;
  keywords?: string;
  sync_superap?: boolean;
}

export interface CampaignSettingsResponse {
  success: boolean;
  message: string;
  campaign_id: number;
  superap_synced: boolean;
}

// ============================================================
// 수기 캠페인 추가
// ============================================================
export interface ManualCampaignInput {
  campaign_code: string;
  account_id: number;
  agency_name?: string;
  place_name?: string;
  place_url: string;
  campaign_type: string;
  start_date: string;
  end_date: string;
  daily_limit: number;
  keywords: string;
}

export interface ManualCampaignResponse {
  success: boolean;
  message: string;
  campaign_id: number | null;
  campaign_code: string | null;
  place_id: string | null;
  keyword_count: number;
}

export interface VerifyCampaignResponse {
  campaign_code: string;
  exists_in_db: boolean;
  db_campaign_id: number | null;
  db_status: string | null;
  message: string;
}

// ============================================================
// 키워드
// ============================================================
export interface AddKeywordsResponse {
  success: boolean;
  message: string;
  added_count: number;
  duplicates: string[];
  total_keywords: number;
  unused_keywords: number;
}

export interface KeywordStatusResponse {
  campaign_id: number;
  remaining_keywords: number;
  remaining_days: number;
  status: 'normal' | 'warning' | 'critical';
  message: string;
}

// ============================================================
// 상태 라벨 (DB 영문 → 한글 표시)
// ============================================================
export const STATUS_LABELS: Record<string, string> = {
  active: '진행중',
  daily_exhausted: '일일소진',
  campaign_exhausted: '전체소진',
  deactivated: '중단',
  paused: '일시정지',
  pending: '대기중',
  pending_extend: '연장 대기',
  completed: '종료',
};

export function getStatusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
}

// ============================================================
// 엑셀 업로드
// ============================================================
export interface CampaignPreviewItem {
  row_number: number;
  agency_name: string;
  user_id: string;
  start_date: string;
  end_date: string;
  daily_limit: number;
  keywords: string[];
  keyword_count: number;
  place_name: string | null;
  place_url: string;
  campaign_type: string;
  is_valid: boolean;
  errors: string[];
  extension_eligible: boolean;
  existing_campaign_code: string | null;
  existing_campaign_id: number | null;
  existing_total_count: number | null;
}

export interface PreviewResponse {
  success: boolean;
  total_count: number;
  valid_count: number;
  invalid_count: number;
  campaigns: CampaignPreviewItem[];
  file_errors: string[];
}

export interface CampaignConfirmItem {
  agency_name: string;
  user_id: string;
  start_date: string;
  end_date: string;
  daily_limit: number;
  keywords: string[];
  place_name: string | null;
  place_url: string;
  campaign_type: string;
  action: 'new' | 'extend';
  existing_campaign_id: number | null;
}

export interface ConfirmResponse {
  success: boolean;
  message: string;
  created_count: number;
  new_count: number;
  extend_count: number;
  skipped: string[];
  campaign_ids: number[];
}

// ============================================================
// 템플릿 (Template)
// ============================================================
export interface TemplateListItem {
  id: number;
  type_name: string;
  campaign_type_selection: string | null;
  modules: string[];
  module_descriptions: string[];
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface TemplateDetail {
  id: number;
  type_name: string;
  description_template: string;
  hint_text: string;
  campaign_type_selection: string | null;
  links: string[];
  hashtag: string | null;
  image_url_200x600: string | null;
  image_url_720x780: string | null;
  conversion_text_template: string | null;
  steps_start: string | null;
  modules: string[];
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface TemplateCreate {
  type_name: string;
  description_template: string;
  hint_text: string;
  campaign_type_selection?: string;
  links: string[];
  hashtag?: string;
  image_url_200x600?: string;
  image_url_720x780?: string;
  conversion_text_template?: string;
  steps_start?: string;
  modules: string[];
}

export interface TemplateUpdate {
  type_name?: string;
  description_template?: string;
  hint_text?: string;
  campaign_type_selection?: string;
  links?: string[];
  hashtag?: string;
  image_url_200x600?: string;
  image_url_720x780?: string;
  conversion_text_template?: string | null;
  steps_start?: string | null;
  modules?: string[];
  is_active?: boolean;
}

export interface TemplateDeleteResponse {
  message: string;
}

export interface TemplateListResponse {
  templates: TemplateListItem[];
  total: number;
}

// ============================================================
// 모듈 (Module)
// ============================================================
export interface ModuleInfo {
  module_id: string;
  description: string;
  output_variables: string[];
  dependencies: string[];
}

export interface ModuleListResponse {
  modules: ModuleInfo[];
  total: number;
}

// ============================================================
// 등록 진행 상태
// ============================================================
export type RegistrationStep =
  | 'queued'
  | 'logging_in'
  | 'running_modules'
  | 'filling_form'
  | 'submitting'
  | 'extracting_code'
  | 'completed'
  | 'failed';

export interface RegistrationProgressItem {
  campaign_id: number;
  place_name: string | null;
  status: string;
  registration_step: RegistrationStep | null;
  registration_message: string | null;
  campaign_code: string | null;
}

export interface RegistrationProgressResponse {
  campaigns: RegistrationProgressItem[];
  all_completed: boolean;
}

export const REGISTRATION_STEP_LABELS: Record<RegistrationStep, string> = {
  queued: '대기',
  logging_in: '로그인 중',
  running_modules: '모듈 실행 중',
  filling_form: '폼 입력 중',
  submitting: '제출 중',
  extracting_code: '번호 추출 중',
  completed: '완료',
  failed: '실패',
};

export const REGISTRATION_STEP_ORDER: RegistrationStep[] = [
  'queued',
  'logging_in',
  'running_modules',
  'filling_form',
  'submitting',
  'extracting_code',
  'completed',
];

// ============================================================
// 스케줄러 상태
// ============================================================
export interface SchedulerStatus {
  is_running: boolean;
  scheduler_active: boolean;
  last_run: string | null;
  last_result: Record<string, unknown> | null;
  last_error: string | null;
  run_count: number;
  recent_logs: string[];
}

export interface SchedulerTriggerResponse {
  success: boolean;
  message: string;
  result: Record<string, unknown> | null;
}

export interface SchedulerDiagnosticCampaign {
  id: number;
  place_name: string;
  campaign_code: string | null;
  status: string | null;
  registration_step: string | null;
  last_keyword_change: string | null;
  keyword_total: number;
  keyword_unused: number;
  account_user_id: string | null;
}

export interface SchedulerDiagnostic {
  scheduler: SchedulerStatus;
  campaigns: SchedulerDiagnosticCampaign[];
  summary: Record<string, unknown>;
}
