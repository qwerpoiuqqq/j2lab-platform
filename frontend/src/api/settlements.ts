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

export interface SettlementByHandlerRow {
  handler_id: string;
  handler_name: string;
  handler_role: string;
  order_count: number;
  item_count: number;
  total_revenue: number;
  total_cost: number;
  total_profit: number;
  avg_margin_pct: number;
}

export interface SettlementByCompanyRow {
  company_id: number | null;
  company_name: string;
  order_count: number;
  item_count: number;
  total_revenue: number;
  total_cost: number;
  total_profit: number;
  avg_margin_pct: number;
}

export interface SettlementByDateRow {
  date: string;
  order_count: number;
  item_count: number;
  total_revenue: number;
  total_cost: number;
  total_profit: number;
}

export const settlementsApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    start_date?: string;
    end_date?: string;
    status?: string;
  }): Promise<SettlementListResponse> => {
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

  byHandler: async (params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<SettlementByHandlerRow[]> => {
    const { start_date, end_date } = params ?? {};
    const response = await apiClient.get('/settlements/by-handler', {
      params: { date_from: start_date, date_to: end_date },
    });
    return response.data;
  },

  byCompany: async (params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<SettlementByCompanyRow[]> => {
    const { start_date, end_date } = params ?? {};
    const response = await apiClient.get('/settlements/by-company', {
      params: { date_from: start_date, date_to: end_date },
    });
    return response.data;
  },

  byDate: async (params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<SettlementByDateRow[]> => {
    const { start_date, end_date } = params ?? {};
    const response = await apiClient.get('/settlements/by-date', {
      params: { date_from: start_date, date_to: end_date },
    });
    return response.data;
  },

  getSecret: async (data: { password: string; start_date?: string; end_date?: string }): Promise<SettlementSecretResponse> => {
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
