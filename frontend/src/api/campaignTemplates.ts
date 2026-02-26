import apiClient from './client';
import type {
  CampaignTemplate,
  CreateCampaignTemplateRequest,
  UpdateCampaignTemplateRequest,
  ModuleInfo,
  PaginatedResponse,
} from '@/types';

export const campaignTemplatesApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    is_active?: boolean;
  }): Promise<PaginatedResponse<CampaignTemplate>> => {
    const response = await apiClient.get('/templates', { params });
    return response.data;
  },

  get: async (id: number): Promise<CampaignTemplate> => {
    const response = await apiClient.get(`/templates/${id}`);
    return response.data;
  },

  create: async (data: CreateCampaignTemplateRequest): Promise<CampaignTemplate> => {
    const response = await apiClient.post('/templates', data);
    return response.data;
  },

  update: async (id: number, data: UpdateCampaignTemplateRequest): Promise<CampaignTemplate> => {
    const response = await apiClient.patch(`/templates/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/templates/${id}`);
  },

  getModules: async (): Promise<{ modules: ModuleInfo[] }> => {
    const response = await apiClient.get('/templates/modules');
    return response.data;
  },
};
