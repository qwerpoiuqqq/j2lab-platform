import apiClient from './client';
import type {
  Settlement,
  SettlementSummary,
  SettlementSecretItem,
  SettlementSecretRequest,
  PaginatedResponse,
} from '@/types';

export const settlementsApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    start_date?: string;
    end_date?: string;
    status?: string;
  }): Promise<PaginatedResponse<Settlement> & { summary: SettlementSummary }> => {
    const response = await apiClient.get('/settlements', { params });
    return response.data;
  },

  getSecret: async (data: SettlementSecretRequest): Promise<{ items: SettlementSecretItem[] }> => {
    const response = await apiClient.post('/settlements/secret', data);
    return response.data;
  },

  export: async (params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<Blob> => {
    const response = await apiClient.get('/settlements/export', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },
};
