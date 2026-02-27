import apiClient from './client';
import type {
  Settlement,
  SettlementSummary,
  SettlementSecretItem,
} from '@/types';

interface SettlementListResponse {
  items: Settlement[];
  summary: SettlementSummary;
  total: number;
  page: number;
  size: number;
  pages: number;
}

interface SettlementSecretResponse {
  items: SettlementSecretItem[];
  summary: SettlementSummary;
}

export const settlementsApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    start_date?: string;
    end_date?: string;
    status?: string;
  }): Promise<SettlementListResponse> => {
    // Backend uses date_from/date_to parameter names
    const { start_date, end_date, ...rest } = params ?? {};
    const response = await apiClient.get('/settlements', {
      params: {
        ...rest,
        date_from: start_date,
        date_to: end_date,
      },
    });
    return response.data;
  },

  getSecret: async (data: { password: string; start_date?: string; end_date?: string }): Promise<SettlementSecretResponse> => {
    // Backend expects date_from/date_to in request body
    const response = await apiClient.post('/settlements/secret', {
      password: data.password,
      date_from: data.start_date,
      date_to: data.end_date,
    });
    return response.data;
  },

  export: async (params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<Blob> => {
    const { start_date, end_date } = params ?? {};
    const response = await apiClient.get('/settlements/export', {
      params: {
        date_from: start_date,
        date_to: end_date,
      },
      responseType: 'blob',
    });
    return response.data;
  },
};
