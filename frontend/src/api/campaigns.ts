import apiClient from './client';
import type {
  Campaign,
  CampaignKeyword,
  CampaignListItem,
  CampaignDashboardStats,
  CampaignSettings,
  CampaignManualCreate,
  PaginatedResponse,
} from '@/types';

export const campaignsApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    status?: string;
    account_id?: number;
    search?: string;
  }): Promise<PaginatedResponse<CampaignListItem>> => {
    const response = await apiClient.get<PaginatedResponse<CampaignListItem>>('/campaigns', { params });
    return response.data;
  },

  get: async (id: number): Promise<Campaign> => {
    const response = await apiClient.get<Campaign>(`/campaigns/${id}`);
    return response.data;
  },

  getKeywords: async (id: number, params?: { page?: number; size?: number }): Promise<PaginatedResponse<CampaignKeyword>> => {
    const response = await apiClient.get<PaginatedResponse<CampaignKeyword>>(`/campaigns/${id}/keywords`, {
      params: { size: 500, ...params },
    });
    return response.data;
  },

  getStats: async (params?: { account_id?: number }): Promise<CampaignDashboardStats> => {
    const response = await apiClient.get('/dashboard/campaign-stats', { params });
    return response.data;
  },

  createManual: async (data: CampaignManualCreate): Promise<Campaign> => {
    const response = await apiClient.post<Campaign>('/campaigns/manual', data);
    return response.data;
  },

  updateSettings: async (id: number, data: CampaignSettings): Promise<Campaign> => {
    const response = await apiClient.patch<Campaign>(`/campaigns/${id}`, data);
    return response.data;
  },

  addKeywords: async (id: number, keywords: string[]): Promise<{ message: string; detail?: { added: number; total_requested: number } }> => {
    const response = await apiClient.post(`/campaigns/${id}/keywords`, { keywords });
    return response.data;
  },

  verifyCode: async (code: string): Promise<{ exists: boolean; campaign_id?: number }> => {
    const response = await apiClient.get(`/campaigns/manual/verify/${code}`);
    return response.data;
  },

  syncToSuperap: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.post(`/campaigns/${id}/sync`);
    return response.data;
  },

  pause: async (id: number): Promise<Campaign> => {
    const response = await apiClient.patch<Campaign>(`/campaigns/${id}`, { status: 'paused' });
    return response.data;
  },

  resume: async (id: number): Promise<Campaign> => {
    const response = await apiClient.patch<Campaign>(`/campaigns/${id}`, { status: 'active' });
    return response.data;
  },

  register: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(`/campaigns/${id}/register`);
    return response.data;
  },

  extend: async (id: number, data: { new_end_date: string; additional_total: number; new_daily_limit?: number }): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(`/campaigns/${id}/extend`, data);
    return response.data;
  },

  rotateKeywords: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(`/campaigns/${id}/rotate-keywords`);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/campaigns/${id}`);
  },

  batchDelete: async (ids: number[]): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>('/campaigns/batch/delete', { ids });
    return response.data;
  },

  retryRegistration: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(`/campaigns/registration/retry`, { campaign_id: id });
    return response.data;
  },
};
