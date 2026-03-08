import apiClient from './client';

export interface AssignmentQueueItem {
  order_item_id: number;
  order_id: number;
  order_number: string;
  company_name: string;
  place_name: string;
  place_id: number | null;
  campaign_type: string;
  assignment_status: string;
  assigned_account_id: number | null;
  assigned_account_name: string | null;
  // PHASE 4: AI recommendation info
  ai_recommendation: 'new' | 'extend';
  extend_target_campaign_id: number | null;
  extend_target_info: {
    campaign_id: number;
    campaign_type: string;
    status: string;
    total_limit: number | null;
    start_date: string | null;
    end_date: string | null;
  } | null;
}

export interface AssignmentQueueResponse {
  items: AssignmentQueueItem[];
}

export const assignmentsApi = {
  getQueue: async (params?: {
    assignment_status?: string;
    order_item_id?: number;
    skip?: number;
    limit?: number;
  }): Promise<AssignmentQueueResponse> => {
    const response = await apiClient.get<AssignmentQueueResponse>('/assignment/queue', { params });
    return response.data;
  },

  confirm: async (itemId: number): Promise<any> => {
    const response = await apiClient.post(`/assignment/${itemId}/confirm`);
    return response.data;
  },

  choose: async (itemId: number, action: 'new' | 'extend'): Promise<any> => {
    const response = await apiClient.post(`/assignment/${itemId}/choose`, { action });
    return response.data;
  },

  override: async (itemId: number, accountId: number, networkPresetId?: number): Promise<any> => {
    const response = await apiClient.patch(`/assignment/${itemId}/account`, {
      account_id: accountId,
      network_preset_id: networkPresetId,
    });
    return response.data;
  },

  bulkConfirm: async (itemIds: number[]): Promise<any> => {
    const response = await apiClient.post('/assignment/bulk-confirm', { item_ids: itemIds });
    return response.data;
  },
};
