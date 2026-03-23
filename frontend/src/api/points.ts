import apiClient from './client';

export interface ChargeRequest {
  id: number;
  user_id: string;
  user_name?: string | null;
  user_login_id?: string | null;
  request_type?: 'charge' | 'refund';
  amount: number;
  payment_amount?: number | null;
  vat_amount?: number | null;
  status: 'pending' | 'approved' | 'rejected';
  approved_by?: string | null;
  approved_at?: string | null;
  rejected_reason?: string | null;
  reason?: string | null;
  created_at: string;
}

export interface ChargeRequestListResponse {
  items: ChargeRequest[];
  total: number;
}

export interface ChargeSummary {
  pending_count: number;
  pending_total: number;
}

export interface UserBalance {
  balance: number;
}

export interface EffectiveUserBalance {
  requested_user_id: string;
  effective_user_id: string;
  effective_user_name: string;
  effective_user_role: string;
  balance: number;
}

export const pointsApi = {
  createChargeRequest: async (amount: number): Promise<ChargeRequest> => {
    const response = await apiClient.post<ChargeRequest>('/charge-requests/', { amount });
    return response.data;
  },

  createRefundRequest: async (amount: number, reason: string): Promise<ChargeRequest> => {
    const response = await apiClient.post<ChargeRequest>('/charge-requests/', {
      amount, request_type: 'refund', reason,
    });
    return response.data;
  },

  listChargeRequests: async (params?: { status?: string; skip?: number; limit?: number }): Promise<ChargeRequestListResponse> => {
    const queryParams: Record<string, any> = {};
    if (params?.status) queryParams.status = params.status;
    if (params?.skip !== undefined) queryParams.skip = params.skip;
    if (params?.limit !== undefined) queryParams.limit = params.limit;
    const response = await apiClient.get<ChargeRequestListResponse>('/charge-requests/', { params: queryParams });
    return response.data;
  },

  approveChargeRequest: async (id: number): Promise<ChargeRequest> => {
    const response = await apiClient.post<ChargeRequest>(`/charge-requests/${id}/approve`);
    return response.data;
  },

  rejectChargeRequest: async (id: number, reason?: string): Promise<ChargeRequest> => {
    const response = await apiClient.post<ChargeRequest>(`/charge-requests/${id}/reject`, { reason: reason || null });
    return response.data;
  },

  getChargeSummary: async (): Promise<ChargeSummary> => {
    const response = await apiClient.get<ChargeSummary>('/charge-requests/summary');
    return response.data;
  },

  getMyBalance: async (userId: string): Promise<UserBalance> => {
    const response = await apiClient.get<UserBalance>(`/balance/${userId}`);
    return response.data;
  },

  getEffectiveMyBalance: async (): Promise<EffectiveUserBalance> => {
    const response = await apiClient.get<EffectiveUserBalance>('/balance/effective/me');
    return response.data;
  },

  grantPoints: async (userId: string, amount: number, description?: string): Promise<any> => {
    if (amount < 0) {
      const response = await apiClient.post('/balance/withdraw', {
        user_id: userId, amount: Math.abs(amount), description: description || '관리자 포인트 차감',
      });
      return response.data;
    }
    const response = await apiClient.post('/balance/deposit', {
      user_id: userId, amount, description: description || '관리자 포인트 지급',
    });
    return response.data;
  },

  getGrantableUsers: async (): Promise<Array<{id: string; name: string; role: string; login_id: string; balance?: number}>> => {
    const response = await apiClient.get('/users', { params: { role: 'distributor', size: 100 } });
    const distributors = response.data.items || [];
    const response2 = await apiClient.get('/users', { params: { role: 'order_handler', size: 100 } });
    const handlers = response2.data.items || [];
    return [...distributors, ...handlers];
  },
};
