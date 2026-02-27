import apiClient from './client';
import type { DashboardSummary, EnhancedDashboard } from '@/types';

export const dashboardApi = {
  getSummary: async (): Promise<DashboardSummary> => {
    const response = await apiClient.get<DashboardSummary>('/dashboard/summary');
    return response.data;
  },

  getEnhanced: async (): Promise<EnhancedDashboard> => {
    const response = await apiClient.get<EnhancedDashboard>('/dashboard/enhanced');
    return response.data;
  },
};
