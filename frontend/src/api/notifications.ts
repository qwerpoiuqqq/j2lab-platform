import apiClient from './client';
import type { NotificationListResponse } from '@/types';

export const notificationsApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    is_read?: boolean;
  }): Promise<NotificationListResponse> => {
    const response = await apiClient.get('/notifications', { params });
    return response.data;
  },

  markRead: async (id: number): Promise<void> => {
    await apiClient.post(`/notifications/${id}/read`);
  },

  markAllRead: async (): Promise<void> => {
    await apiClient.post('/notifications/read-all');
  },
};
