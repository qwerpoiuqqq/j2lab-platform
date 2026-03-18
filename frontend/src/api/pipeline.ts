import apiClient from './client';
import type { PipelineState, PaginatedResponse } from '@/types';

export interface PipelineLogItem {
  id: number;
  pipeline_state_id: number;
  from_stage: string | null;
  to_stage: string;
  trigger_type: string | null;
  message: string | null;
  actor_id: string | null;
  actor_name: string | null;
  created_at: string;
}

export const pipelineApi = {
  getState: async (orderItemId: number): Promise<PipelineState> => {
    const response = await apiClient.get<PipelineState>(`/pipeline/${orderItemId}`);
    return response.data;
  },

  getLogs: async (orderItemId: number, page = 1, size = 50): Promise<PaginatedResponse<PipelineLogItem>> => {
    const response = await apiClient.get<PaginatedResponse<PipelineLogItem>>(
      `/pipeline/${orderItemId}/logs`,
      { params: { page, size } }
    );
    return response.data;
  },

  startExtraction: async (orderItemId: number): Promise<{ message: string }> => {
    const response = await apiClient.post<{ message: string }>(
      `/pipeline/${orderItemId}/start-extraction`
    );
    return response.data;
  },
};
