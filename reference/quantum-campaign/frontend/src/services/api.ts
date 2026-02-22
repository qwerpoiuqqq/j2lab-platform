import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import type {
  Account,
  AccountListResponse,
  AccountCreate,
  AccountUpdate,
  AccountDeleteResponse,
  AgencyListResponse,
  DashboardStats,
  CampaignListResponse,
  CampaignDetail,
  CampaignDeleteResponse,
  BatchDeleteResponse,
  CampaignSettingsUpdate,
  CampaignSettingsResponse,
  ManualCampaignInput,
  ManualCampaignResponse,
  VerifyCampaignResponse,
  AddKeywordsResponse,
  RegistrationProgressResponse,
  PreviewResponse,
  CampaignConfirmItem,
  ConfirmResponse,
  TemplateListResponse,
  TemplateDetail,
  TemplateCreate,
  TemplateUpdate,
  TemplateDeleteResponse,
  ModuleListResponse,
  SchedulerStatus,
  SchedulerDiagnostic,
  SchedulerTriggerResponse,
} from '../types';

const MAX_RETRIES = 2;
const RETRY_DELAY = 1000;

interface RetryConfig extends InternalAxiosRequestConfig {
  _retryCount?: number;
}

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

// 네트워크 오류 시 재시도 인터셉터
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined;
    if (!config) return Promise.reject(error);

    config._retryCount = config._retryCount ?? 0;

    // 네트워크 오류 또는 5xx 에러에 대해서만 재시도
    const isNetworkError = !error.response;
    const isServerError = error.response && error.response.status >= 500;

    if ((isNetworkError || isServerError) && config._retryCount < MAX_RETRIES) {
      config._retryCount += 1;
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY * config._retryCount!));
      return api(config);
    }

    return Promise.reject(error);
  },
);

/** API 에러에서 사용자 친화적 메시지 추출 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.data?.detail) {
      return error.response.data.detail;
    }
    if (!error.response) {
      return '네트워크 연결을 확인해주세요.';
    }
    if (error.response.status >= 500) {
      return '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
    }
  }
  return '알 수 없는 오류가 발생했습니다.';
}

// ============================================================
// 계정 관리
// ============================================================
export const fetchAccounts = () =>
  api.get<AccountListResponse>('/accounts').then((r) => r.data);

export const createAccount = (data: AccountCreate) =>
  api.post<Account>('/accounts', data).then((r) => r.data);

export const updateAccount = (id: number, data: AccountUpdate) =>
  api.put<Account>(`/accounts/${id}`, data).then((r) => r.data);

export const deleteAccount = (id: number) =>
  api.delete<AccountDeleteResponse>(`/accounts/${id}`).then((r) => r.data);

// ============================================================
// 대시보드
// ============================================================
export const fetchAgencies = () =>
  api.get<AgencyListResponse>('/agencies').then((r) => r.data);

export const fetchDashboardStats = (accountId?: number) =>
  api
    .get<DashboardStats>('/dashboard/stats', {
      params: accountId ? { account_id: accountId } : {},
    })
    .then((r) => r.data);

// ============================================================
// 캠페인
// ============================================================
export const fetchCampaigns = (params: {
  account_id?: number;
  agency_name?: string;
  status?: string;
  page?: number;
  limit?: number;
}) =>
  api.get<CampaignListResponse>('/campaigns', { params }).then((r) => r.data);

export const fetchCampaignDetail = (id: number) =>
  api.get<CampaignDetail>(`/campaigns/${id}`).then((r) => r.data);

export const addManualCampaign = (data: ManualCampaignInput) =>
  api.post<ManualCampaignResponse>('/campaigns/manual', data).then((r) => r.data);

export const verifyCampaign = (code: string, accountId?: number) =>
  api
    .get<VerifyCampaignResponse>(`/campaigns/manual/verify/${code}`, {
      params: accountId ? { account_id: accountId } : {},
    })
    .then((r) => r.data);

export const addKeywords = (campaignId: number, keywords: string) =>
  api
    .post<AddKeywordsResponse>(`/campaigns/${campaignId}/keywords`, { keywords })
    .then((r) => r.data);

export const deleteCampaign = (id: number) =>
  api.delete<CampaignDeleteResponse>(`/campaigns/${id}`).then((r) => r.data);

export const batchDeleteCampaigns = (campaignIds: number[]) =>
  api
    .post<BatchDeleteResponse>('/campaigns/batch/delete', { campaign_ids: campaignIds })
    .then((r) => r.data);

export const updateCampaignSettings = (id: number, data: CampaignSettingsUpdate) =>
  api.put<CampaignSettingsResponse>(`/campaigns/${id}/settings`, data, { timeout: 120000 }).then((r) => r.data);

export const syncCampaignToSuperap = (id: number) =>
  api.post<CampaignSettingsResponse>(`/campaigns/${id}/sync`, {}, { timeout: 120000 }).then((r) => r.data);

export const fetchRegistrationProgress = (campaignIds: number[]) =>
  api
    .get<RegistrationProgressResponse>('/campaigns/registration/progress', {
      params: { campaign_ids: campaignIds.join(',') },
    })
    .then((r) => r.data);

export const retryRegistration = (campaignIds: number[]) =>
  api
    .post<{ success: boolean; message: string; retried_count: number; skipped: string[] }>(
      '/campaigns/registration/retry',
      { campaign_ids: campaignIds },
    )
    .then((r) => r.data);

// ============================================================
// 엑셀 업로드
// ============================================================
export const uploadPreview = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return api
    .post<PreviewResponse>('/upload/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data);
};

export const confirmUpload = (campaigns: CampaignConfirmItem[]) =>
  api.post<ConfirmResponse>('/upload/confirm', { campaigns }).then((r) => r.data);

export const downloadTemplate = async () => {
  const response = await api.get('/upload/template', { responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'campaign_upload_template.xlsx');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// ============================================================
// 템플릿
// ============================================================
export const fetchTemplates = () =>
  api.get<TemplateListResponse>('/templates').then((r) => r.data);

export const fetchTemplateDetail = (id: number) =>
  api.get<TemplateDetail>(`/templates/${id}`).then((r) => r.data);

export const createTemplate = (data: TemplateCreate) =>
  api.post<TemplateDetail>('/templates', data).then((r) => r.data);

export const updateTemplate = (id: number, data: TemplateUpdate) =>
  api.put<TemplateDetail>(`/templates/${id}`, data).then((r) => r.data);

export const deleteTemplate = (id: number) =>
  api.delete<TemplateDeleteResponse>(`/templates/${id}`).then((r) => r.data);

// ============================================================
// 모듈
// ============================================================
export const fetchModules = () =>
  api.get<ModuleListResponse>('/modules').then((r) => r.data);

// ============================================================
// 스케줄러
// ============================================================
export const fetchSchedulerStatus = () =>
  api.get<SchedulerStatus>('/scheduler/status').then((r) => r.data);

export const fetchSchedulerDiagnostic = () =>
  api.get<SchedulerDiagnostic>('/scheduler/diagnostic').then((r) => r.data);

export const triggerScheduler = () =>
  api.post<SchedulerTriggerResponse>('/scheduler/trigger').then((r) => r.data);
