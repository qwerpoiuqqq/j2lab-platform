import apiClient from './client';
import type {
  NetworkPreset,
  CreateNetworkPresetRequest,
  UpdateNetworkPresetRequest,
  PaginatedResponse,
} from '@/types';

export const networkPresetsApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    company_id?: number;
    campaign_type?: string;
    is_active?: boolean;
  }): Promise<PaginatedResponse<NetworkPreset>> => {
    const response = await apiClient.get('/network-presets', { params });
    return response.data;
  },

  create: async (data: CreateNetworkPresetRequest): Promise<NetworkPreset> => {
    const response = await apiClient.post('/network-presets', data);
    return response.data;
  },

  update: async (id: number, data: UpdateNetworkPresetRequest): Promise<NetworkPreset> => {
    const response = await apiClient.patch(`/network-presets/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/network-presets/${id}`);
  },
};
