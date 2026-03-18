import apiClient from './client';
import type {
  SuperapAccount,
  CreateSuperapAccountRequest,
  UpdateSuperapAccountRequest,
  PaginatedResponse,
} from '@/types';

export const campaignAccountsApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    company_id?: number;
    network_preset_id?: number;
    is_active?: boolean;
  }): Promise<PaginatedResponse<SuperapAccount>> => {
    const response = await apiClient.get('/superap-accounts', { params });
    return response.data;
  },

  create: async (data: CreateSuperapAccountRequest): Promise<SuperapAccount> => {
    const response = await apiClient.post('/superap-accounts', data);
    return response.data;
  },

  update: async (id: number, data: UpdateSuperapAccountRequest): Promise<SuperapAccount> => {
    const response = await apiClient.patch(`/superap-accounts/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/superap-accounts/${id}`);
  },

};
