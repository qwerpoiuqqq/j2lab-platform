import apiClient from './client';
import type { Campaign, CampaignKeyword, PaginatedResponse } from '@/types';

export const campaignsApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    status?: string;
  }): Promise<PaginatedResponse<Campaign>> => {
    const response = await apiClient.get<PaginatedResponse<Campaign>>('/campaigns', { params });
    return response.data;
  },

  get: async (id: number): Promise<Campaign> => {
    const response = await apiClient.get<Campaign>(`/campaigns/${id}`);
    return response.data;
  },

  getKeywords: async (id: number): Promise<PaginatedResponse<CampaignKeyword>> => {
    const response = await apiClient.get<PaginatedResponse<CampaignKeyword>>(`/campaigns/${id}/keywords`);
    return response.data;
  },

  pause: async (id: number): Promise<Campaign> => {
    const response = await apiClient.patch<Campaign>(`/campaigns/${id}`, { status: 'paused' });
    return response.data;
  },

  resume: async (id: number): Promise<Campaign> => {
    const response = await apiClient.patch<Campaign>(`/campaigns/${id}`, { status: 'active' });
    return response.data;
  },

  register: async (id: number): Promise<Campaign> => {
    const response = await apiClient.post<Campaign>(`/campaigns/${id}/register`);
    return response.data;
  },

  extend: async (id: number): Promise<Campaign> => {
    const response = await apiClient.post<Campaign>(`/campaigns/${id}/extend`);
    return response.data;
  },

  rotateKeywords: async (id: number): Promise<Campaign> => {
    const response = await apiClient.post<Campaign>(`/campaigns/${id}/rotate-keywords`);
    return response.data;
  },
};
