import apiClient from './client';
import type {
  CampaignUploadPreviewResponse,
  CampaignUploadConfirmRequest,
  RegistrationProgressItem,
} from '@/types';

export const campaignUploadApi = {
  preview: async (file: File): Promise<CampaignUploadPreviewResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/campaigns/upload/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  },

  confirm: async (data: CampaignUploadConfirmRequest): Promise<{ message: string }> => {
    const response = await apiClient.post('/campaigns/upload/confirm', data);
    return response.data;
  },

  downloadTemplate: async (): Promise<Blob> => {
    const response = await apiClient.get('/campaigns/upload/template', {
      responseType: 'blob',
    });
    return response.data;
  },

  getProgress: async (): Promise<{ items: RegistrationProgressItem[] }> => {
    const response = await apiClient.get('/campaigns/registration/progress');
    return response.data;
  },
};
