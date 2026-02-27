import apiClient from './client';
import type { Company, CreateCompanyRequest, PaginatedResponse } from '@/types';

export const companiesApi = {
  list: async (page = 1, size = 20): Promise<PaginatedResponse<Company>> => {
    const response = await apiClient.get<PaginatedResponse<Company>>('/companies', {
      params: { page, size },
    });
    return response.data;
  },

  get: async (id: number): Promise<Company> => {
    const response = await apiClient.get<Company>(`/companies/${id}`);
    return response.data;
  },

  create: async (data: CreateCompanyRequest): Promise<Company> => {
    const response = await apiClient.post<Company>('/companies', data);
    return response.data;
  },

  update: async (id: number, data: Partial<CreateCompanyRequest> & { is_active?: boolean }): Promise<Company> => {
    const response = await apiClient.patch<Company>(`/companies/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/companies/${id}`);
  },
};
