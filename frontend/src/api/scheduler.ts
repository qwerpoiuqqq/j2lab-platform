import apiClient from './client';
import type { SchedulerStatus } from '@/types';

export const schedulerApi = {
  getStatus: async (): Promise<SchedulerStatus> => {
    const response = await apiClient.get('/scheduler/status');
    return response.data;
  },

  trigger: async (): Promise<{ message: string }> => {
    const response = await apiClient.post('/scheduler/trigger');
    return response.data;
  },
};
