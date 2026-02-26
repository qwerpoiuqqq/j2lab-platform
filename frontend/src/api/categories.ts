import apiClient from './client';
import type {
  Category,
  CreateCategoryRequest,
  UpdateCategoryRequest,
  CategoryReorderRequest,
  PaginatedResponse,
} from '@/types';

export const categoriesApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    is_active?: boolean;
  }): Promise<PaginatedResponse<Category>> => {
    const response = await apiClient.get('/categories', { params });
    return response.data;
  },

  create: async (data: CreateCategoryRequest): Promise<Category> => {
    const response = await apiClient.post('/categories', data);
    return response.data;
  },

  update: async (id: number, data: UpdateCategoryRequest): Promise<Category> => {
    const response = await apiClient.put(`/categories/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/categories/${id}`);
  },

  reorder: async (data: CategoryReorderRequest): Promise<void> => {
    await apiClient.post('/categories/reorder', data);
  },
};
