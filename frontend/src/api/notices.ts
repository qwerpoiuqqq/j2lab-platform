import apiClient from './client';
import type {
  Notice,
  CreateNoticeRequest,
  UpdateNoticeRequest,
  PaginatedResponse,
} from '@/types';

export const noticesApi = {
  list: async (params?: {
    page?: number;
    size?: number;
  }): Promise<PaginatedResponse<Notice>> => {
    const response = await apiClient.get('/notices', { params });
    return response.data;
  },

  create: async (data: CreateNoticeRequest): Promise<Notice> => {
    const response = await apiClient.post('/notices', data);
    return response.data;
  },

  update: async (id: number, data: UpdateNoticeRequest): Promise<Notice> => {
    const response = await apiClient.put(`/notices/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/notices/${id}`);
  },
};
