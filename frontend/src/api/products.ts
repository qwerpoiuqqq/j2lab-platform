import apiClient from './client';
import type { Product, PaginatedResponse } from '@/types';

export const productsApi = {
  list: async (params?: {
    page?: number;
    page_size?: number;
    is_active?: boolean;
  }): Promise<PaginatedResponse<Product>> => {
    const response = await apiClient.get<PaginatedResponse<Product>>('/products', { params });
    return response.data;
  },

  get: async (id: number): Promise<Product> => {
    const response = await apiClient.get<Product>(`/products/${id}`);
    return response.data;
  },

  create: async (data: Partial<Product>): Promise<Product> => {
    const response = await apiClient.post<Product>('/products', data);
    return response.data;
  },

  update: async (id: number, data: Partial<Product>): Promise<Product> => {
    const response = await apiClient.patch<Product>(`/products/${id}`, data);
    return response.data;
  },
};
