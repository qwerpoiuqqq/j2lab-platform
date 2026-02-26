import apiClient from './client';
import type { SystemSetting } from '@/types';

export const settingsApi = {
  list: async (): Promise<SystemSetting[]> => {
    const response = await apiClient.get<SystemSetting[]>('/settings');
    return response.data;
  },

  get: async (key: string): Promise<SystemSetting> => {
    const response = await apiClient.get<SystemSetting>(`/settings/${key}`);
    return response.data;
  },

  update: async (key: string, data: { value: any; description?: string }): Promise<SystemSetting> => {
    const response = await apiClient.put<SystemSetting>(`/settings/${key}`, data);
    return response.data;
  },

  delete: async (key: string): Promise<void> => {
    await apiClient.delete(`/settings/${key}`);
  },
};
