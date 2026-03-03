import apiClient from './client';
import type {
  Order,
  OrderItem,
  CreateOrderRequest,
  BulkStatusRequest,
  CalendarDeadlines,
  DeadlineUpdateRequest,
  ExcelUploadResponse,
  ExcelUploadPreviewResponse,
  ExcelUploadConfirmRequest,
  PaginatedResponse,
} from '@/types';

export const ordersApi = {
  list: async (params?: {
    page?: number;
    size?: number;
    status?: string;
    company_id?: number;
    search?: string;
  }): Promise<PaginatedResponse<Order>> => {
    const response = await apiClient.get<PaginatedResponse<Order>>('/orders', { params });
    return response.data;
  },

  get: async (id: number): Promise<Order> => {
    const response = await apiClient.get<Order>(`/orders/${id}`);
    return response.data;
  },

  getItems: async (orderId: number): Promise<OrderItem[]> => {
    const response = await apiClient.get<OrderItem[]>(`/orders/${orderId}/items`);
    return response.data;
  },

  create: async (data: CreateOrderRequest): Promise<Order> => {
    const response = await apiClient.post<Order>('/orders', data);
    return response.data;
  },

  update: async (id: number, data: Partial<Order>): Promise<Order> => {
    const response = await apiClient.patch<Order>(`/orders/${id}`, data);
    return response.data;
  },

  submit: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/submit`);
    return response.data;
  },

  confirmPayment: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/confirm-payment`);
    return response.data;
  },

  reject: async (id: number, reason: string): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/reject`, { reason });
    return response.data;
  },

  cancel: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/cancel`);
    return response.data;
  },

  getDeadlines: async (year: number, month: number): Promise<CalendarDeadlines> => {
    const response = await apiClient.get<CalendarDeadlines>('/orders/deadlines', {
      params: { year, month },
    });
    return response.data;
  },

  approve: async (id: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${id}/approve`);
    return response.data;
  },

  bulkStatus: async (data: BulkStatusRequest): Promise<{ updated: number }> => {
    const response = await apiClient.post('/orders/bulk-status', data);
    return response.data;
  },

  updateDeadline: async (id: number, data: DeadlineUpdateRequest): Promise<Order> => {
    const response = await apiClient.patch<Order>(`/orders/${id}/deadline`, data);
    return response.data;
  },

  downloadExcelTemplate: async (productId: number): Promise<Blob> => {
    const response = await apiClient.get(`/orders/excel-template/${productId}`, {
      responseType: 'blob',
    });
    return response.data;
  },

  uploadExcel: async (file: File): Promise<ExcelUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/orders/excel-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  },

  uploadExcelPreview: async (file: File, productId: number): Promise<ExcelUploadPreviewResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post(`/orders/excel-upload?product_id=${productId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  },

  confirmExcelUpload: async (data: ExcelUploadConfirmRequest): Promise<Order> => {
    const response = await apiClient.post<Order>('/orders/excel-upload/confirm', data);
    return response.data;
  },

  exportItems: async (orderId: number): Promise<Blob> => {
    const response = await apiClient.get(`/orders/${orderId}/items/export`, {
      responseType: 'blob',
    });
    return response.data;
  },

  exportList: async (params?: {
    status?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<Blob> => {
    const response = await apiClient.get('/orders/export', {
      params,
      responseType: 'blob',
    });
    return response.data;
  },

  // Simplified order
  createSimplified: async (data: {
    items: {
      place_url: string;
      start_date: string;
      daily_limit: number;
      duration_days: number;
      target_keyword?: string;
      campaign_type?: string;
    }[];
    notes?: string;
    source?: string;
  }): Promise<Order> => {
    const response = await apiClient.post<Order>('/orders/simplified', data);
    return response.data;
  },

  // Distributor order selection
  getSubAccountPending: async (params?: {
    skip?: number;
    limit?: number;
  }): Promise<{ items: any[] }> => {
    const response = await apiClient.get('/orders/sub-account-pending', { params });
    return response.data;
  },

  includeOrder: async (orderId: number): Promise<any> => {
    const response = await apiClient.post(`/orders/${orderId}/include`);
    return response.data;
  },

  excludeOrder: async (orderId: number): Promise<any> => {
    const response = await apiClient.post(`/orders/${orderId}/exclude`);
    return response.data;
  },

  bulkInclude: async (orderIds: number[]): Promise<any> => {
    const response = await apiClient.post('/orders/bulk-include', {
      order_ids: orderIds,
      status: 'included',
    });
    return response.data;
  },

  holdOrder: async (orderId: number, reason: string): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${orderId}/hold`, { reason });
    return response.data;
  },

  releaseHold: async (orderId: number): Promise<Order> => {
    const response = await apiClient.post<Order>(`/orders/${orderId}/release-hold`);
    return response.data;
  },

  bulkPaymentConfirm: async (orderIds: number[]): Promise<{ message: string }> => {
    const response = await apiClient.post('/orders/bulk-payment-confirm', {
      order_ids: orderIds,
    });
    return response.data;
  },

  bulkHold: async (orderIds: number[], reason: string): Promise<{ message: string }> => {
    const response = await apiClient.post('/orders/bulk-hold', {
      order_ids: orderIds,
      reason,
    });
    return response.data;
  },
};
